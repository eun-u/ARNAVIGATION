package kr.co.navi.mobility.data

import kr.co.navi.mobility.data.model.CoordinateDto
import kr.co.navi.mobility.data.model.NaviBootstrap
import kr.co.navi.mobility.data.model.ObservationCandidateDto
import kr.co.navi.mobility.data.model.RouteComparisonDto
import kr.co.navi.mobility.data.model.RouteResultDto
import kr.co.navi.mobility.data.model.SessionRerouteResponseDto
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

data class NaviSessionState(
    val bootstrap: NaviBootstrap? = null,
    val origin: CoordinateDto? = null,
    val destination: CoordinateDto? = null,
    val profile: String = "wheelchair",
    val comparison: RouteComparisonDto? = null,
    val activeRoute: RouteResultDto? = null,
    val reroute: SessionRerouteResponseDto? = null,
    val observation: ObservationCandidateDto? = null,
)

class NaviSessionStore {
    private val mutableState = MutableStateFlow(NaviSessionState())
    val state: StateFlow<NaviSessionState> = mutableState.asStateFlow()

    fun setBootstrap(bootstrap: NaviBootstrap) {
        mutableState.value = mutableState.value.copy(
            bootstrap = bootstrap,
            origin = bootstrap.origin.coordinate,
            destination = bootstrap.destination.coordinate,
        )
    }

    fun setOrigin(origin: CoordinateDto) {
        mutableState.value = mutableState.value.copy(origin = origin)
    }

    fun setProfile(profile: String) {
        mutableState.value = mutableState.value.copy(profile = profile)
    }

    fun setComparison(comparison: RouteComparisonDto) {
        mutableState.value = mutableState.value.copy(
            comparison = comparison,
            activeRoute = comparison.accessible,
            reroute = null,
            observation = null,
        )
    }

    fun applyReroute(result: SessionRerouteResponseDto) {
        mutableState.value = mutableState.value.copy(
            comparison = result.comparison ?: mutableState.value.comparison,
            activeRoute = result.recalculatedRoute,
            reroute = result,
        )
    }

    fun setObservation(observation: ObservationCandidateDto) {
        mutableState.value = mutableState.value.copy(observation = observation)
    }

    fun clearJourney() {
        val bootstrap = mutableState.value.bootstrap
        mutableState.value = NaviSessionState(
            bootstrap = bootstrap,
            origin = bootstrap?.origin?.coordinate,
            destination = bootstrap?.destination?.coordinate,
        )
    }
}
