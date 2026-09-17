package kr.co.navi.mobility.ui

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import kr.co.navi.mobility.data.NaviSessionState
import kr.co.navi.mobility.data.NaviSessionStore
import kr.co.navi.mobility.data.model.CoordinateDto
import kr.co.navi.mobility.data.model.ObservationCandidateDto
import kr.co.navi.mobility.data.model.SessionRerouteResponseDto
import kr.co.navi.mobility.data.repository.NaviRepository
import kr.co.navi.mobility.location.LocationState
import kr.co.navi.mobility.location.LocationTracker
import kr.co.navi.mobility.sensors.HeadingState
import kr.co.navi.mobility.sensors.HeadingTracker
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

data class PlanUiState(
    val loading: Boolean = true,
    val submitting: Boolean = false,
    val error: String? = null,
    val errorCanRetry: Boolean = false,
)

class PlanViewModel(
    private val repository: NaviRepository,
    private val sessionStore: NaviSessionStore,
    private val locationTracker: LocationTracker,
) : ViewModel() {
    private val mutableUiState = MutableStateFlow(PlanUiState())
    val uiState: StateFlow<PlanUiState> = mutableUiState.asStateFlow()
    val sessionState: StateFlow<NaviSessionState> = sessionStore.state
    val locationState: StateFlow<LocationState> = locationTracker.state

    private val mutableRouteReady = MutableSharedFlow<Unit>(extraBufferCapacity = 1)
    val routeReady: SharedFlow<Unit> = mutableRouteReady.asSharedFlow()

    init {
        loadBootstrap()
    }

    fun loadBootstrap() {
        viewModelScope.launch {
            mutableUiState.value = PlanUiState(loading = true)
            runCatching { repository.bootstrap() }
                .onSuccess {
                    sessionStore.setBootstrap(it)
                    mutableUiState.value = PlanUiState(loading = false)
                }
                .onFailure {
                    mutableUiState.value = PlanUiState(
                        loading = false,
                        error = it.userMessage("경로 데이터를 불러오지 못했습니다."),
                        errorCanRetry = true,
                    )
                }
        }
    }

    fun setProfile(profile: String) = sessionStore.setProfile(profile)

    fun startLocation() = locationTracker.start()

    fun useLatestLocation(): Boolean {
        val available = locationTracker.state.value as? LocationState.Available ?: return false
        val bootstrap = sessionStore.state.value.bootstrap ?: return false
        if (!bootstrap.coverageBounds.contains(available.coordinate)) {
            mutableUiState.value = mutableUiState.value.copy(
                error = "현재 위치는 ${bootstrap.areaName} 실증 Graph 범위 밖입니다. 카메라 기능은 확인할 수 있지만, 이 위치의 실제 경로 계산에는 해당 지역 Graph가 필요합니다.",
                errorCanRetry = false,
            )
            return false
        }
        sessionStore.setOrigin(available.coordinate)
        mutableUiState.value = mutableUiState.value.copy(error = null, errorCanRetry = false)
        return true
    }

    fun findRoute() {
        val state = sessionStore.state.value
        val origin = state.origin ?: return
        val destination = state.destination ?: return
        viewModelScope.launch {
            mutableUiState.value = mutableUiState.value.copy(submitting = true, error = null)
            runCatching {
                repository.compareRoute(origin, destination, state.profile)
            }.onSuccess {
                sessionStore.setComparison(it)
                mutableUiState.value = mutableUiState.value.copy(submitting = false)
                mutableRouteReady.tryEmit(Unit)
            }.onFailure {
                mutableUiState.value = mutableUiState.value.copy(
                    submitting = false,
                    error = it.userMessage("경로를 계산하지 못했습니다."),
                )
            }
        }
    }

    override fun onCleared() {
        locationTracker.stop()
        super.onCleared()
    }
}

class RouteViewModel(
    sessionStore: NaviSessionStore,
) : ViewModel() {
    val sessionState: StateFlow<NaviSessionState> = sessionStore.state
}

data class ReportUiState(
    val submitting: Boolean = false,
    val reroute: SessionRerouteResponseDto? = null,
    val candidate: ObservationCandidateDto? = null,
    val error: String? = null,
    val message: String? = null,
)

class NavigationViewModel(
    private val repository: NaviRepository,
    private val sessionStore: NaviSessionStore,
    private val locationTracker: LocationTracker,
    private val headingTracker: HeadingTracker,
) : ViewModel() {
    val sessionState: StateFlow<NaviSessionState> = sessionStore.state
    val locationState: StateFlow<LocationState> = locationTracker.state
    val headingState: StateFlow<HeadingState> = headingTracker.state

    private val mutableReportState = MutableStateFlow(ReportUiState())
    val reportState: StateFlow<ReportUiState> = mutableReportState.asStateFlow()

    fun startSensors() {
        locationTracker.start()
        headingTracker.start()
    }

    fun stopSensors() {
        locationTracker.stop()
        headingTracker.stop()
    }

    fun reportObstacle(type: String, note: String?) {
        if (mutableReportState.value.submitting) return
        val state = sessionStore.state.value
        val sessionId = state.comparison?.sessionId
        val edgeId = state.bootstrap?.blockEdgeId
        if (sessionId == null || edgeId == null) {
            mutableReportState.value = ReportUiState(error = "활성 경로 세션을 찾을 수 없습니다.")
            return
        }
        val coordinate = (locationTracker.state.value as? LocationState.Available)?.coordinate
        viewModelScope.launch {
            mutableReportState.value = ReportUiState(submitting = true)
            val reroute = runCatching {
                repository.rerouteSession(sessionId, edgeId, type)
            }.getOrElse {
                mutableReportState.value = ReportUiState(
                    error = it.userMessage("안전한 우회 경로를 계산하지 못했습니다."),
                )
                return@launch
            }
            sessionStore.applyReroute(reroute)

            val candidateResult = runCatching {
                repository.createObservation(
                    sessionId = sessionId,
                    edgeId = edgeId,
                    type = type,
                    note = note,
                    coordinate = coordinate,
                )
            }
            candidateResult.onSuccess(sessionStore::setObservation)
            mutableReportState.value = ReportUiState(
                reroute = reroute,
                candidate = candidateResult.getOrNull(),
                error = candidateResult.exceptionOrNull()?.userMessage("우회는 완료됐지만 현장 후보 저장에 실패했습니다."),
                message = if (candidateResult.isSuccess) {
                    "현재 세션은 즉시 우회했고, 제보는 검수 대기로 저장했습니다."
                } else {
                    "현재 세션의 우회는 완료했습니다."
                },
            )
        }
    }

    fun resetReportState() {
        mutableReportState.value = ReportUiState()
    }

    override fun onCleared() {
        stopSensors()
        super.onCleared()
    }
}

class NaviViewModelFactory<T : ViewModel>(
    private val create: () -> T,
) : ViewModelProvider.Factory {
    @Suppress("UNCHECKED_CAST")
    override fun <VM : ViewModel> create(modelClass: Class<VM>): VM = create() as VM
}

private fun Throwable.userMessage(fallback: String): String =
    message?.takeIf { it.isNotBlank() } ?: fallback
