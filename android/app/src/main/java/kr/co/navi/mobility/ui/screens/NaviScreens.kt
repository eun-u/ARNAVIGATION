package kr.co.navi.mobility.ui.screens

import android.Manifest
import android.content.pm.PackageManager
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawing
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.FilterChip
import androidx.compose.material3.FilterChipDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import kr.co.navi.mobility.ar.ArDatasetController
import kr.co.navi.mobility.ar.ArDatasetMode
import kr.co.navi.mobility.ar.ArRuntimeMode
import kr.co.navi.mobility.ar.ArRuntimeState
import kr.co.navi.mobility.ar.sensors.HeadingState
import kr.co.navi.mobility.ar.ui.CameraHud
import kr.co.navi.mobility.data.NaviSessionState
import kr.co.navi.mobility.data.model.CoordinateDto
import kr.co.navi.mobility.data.model.RouteComparisonDto
import kr.co.navi.mobility.data.model.RouteResultDto
import kr.co.navi.mobility.location.LocationState
import kr.co.navi.mobility.guidance.contract.GeoCoordinate
import kr.co.navi.mobility.guidance.contract.normalizeHeadingDelta
import kr.co.navi.mobility.guidance.contract.reasonLabel
import kr.co.navi.mobility.guidance.contract.routeBearing
import kr.co.navi.mobility.ui.NavigationViewModel
import kr.co.navi.mobility.ui.PlanViewModel
import kr.co.navi.mobility.ui.RouteViewModel
import kr.co.navi.mobility.ui.components.NaviBrandLockup
import kr.co.navi.mobility.ui.components.NaviTopBar
import kr.co.navi.mobility.ui.components.PrimaryActionButton
import kr.co.navi.mobility.ui.components.PrismDivider
import kr.co.navi.mobility.ui.components.RouteMap
import kr.co.navi.mobility.ui.components.SecondaryActionButton
import kr.co.navi.mobility.ui.components.SectionCard
import kr.co.navi.mobility.ui.components.StatusPill
import kr.co.navi.mobility.ui.components.TrustBanner
import kr.co.navi.mobility.ui.theme.NaviBlock
import kr.co.navi.mobility.ui.theme.NaviBlockSoft
import kr.co.navi.mobility.ui.theme.NaviBlue
import kr.co.navi.mobility.ui.theme.NaviBlueSoft
import kr.co.navi.mobility.ui.theme.NaviCaution
import kr.co.navi.mobility.ui.theme.NaviCautionSoft
import kr.co.navi.mobility.ui.theme.NaviDimens
import kr.co.navi.mobility.ui.theme.NaviInk
import kr.co.navi.mobility.ui.theme.NaviInkMuted
import kr.co.navi.mobility.ui.theme.NaviLine
import kr.co.navi.mobility.ui.theme.NaviMetricTextStyle
import kr.co.navi.mobility.ui.theme.NaviOnDark
import kr.co.navi.mobility.ui.theme.NaviPass
import kr.co.navi.mobility.ui.theme.NaviPassSoft
import kr.co.navi.mobility.ui.theme.NaviSurfaceRaised
import kr.co.navi.mobility.ui.theme.NaviViolet
import kr.co.navi.mobility.ui.theme.NaviVioletSoft
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import kotlin.math.abs

@Composable
fun PlanScreen(
    viewModel: PlanViewModel,
    onRouteReady: () -> Unit,
) {
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()
    val session by viewModel.sessionState.collectAsStateWithLifecycle()
    val location by viewModel.locationState.collectAsStateWithLifecycle()
    val context = LocalContext.current
    val locationPermissionLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions(),
    ) { viewModel.startLocation() }

    LaunchedEffect(viewModel) {
        viewModel.routeReady.collect { onRouteReady() }
    }
    LaunchedEffect(location) {
        if (location is LocationState.Available) viewModel.useLatestLocation()
    }

    Scaffold(
        contentWindowInsets = WindowInsets.safeDrawing,
        bottomBar = {
            Surface(color = MaterialTheme.colorScheme.surface) {
                PrimaryActionButton(
                    text = "접근 가능한 길 찾기",
                    onClick = viewModel::findRoute,
                    enabled = session.origin != null && session.destination != null && !uiState.loading,
                    loading = uiState.submitting,
                    modifier = Modifier
                        .navigationBarsPadding()
                        .padding(horizontal = NaviDimens.Space20, vertical = NaviDimens.Space12),
                )
            }
        },
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .verticalScroll(rememberScrollState())
                .padding(horizontal = NaviDimens.Space20),
        ) {
            Spacer(Modifier.height(NaviDimens.Space24))
            NaviBrandLockup()
            Spacer(Modifier.height(NaviDimens.Space24))
            Text(
                text = "갈 수 있는 길을\n먼저 확인하세요.",
                style = MaterialTheme.typography.headlineLarge,
                color = NaviInk,
                modifier = Modifier.semantics { heading() },
            )
            Spacer(Modifier.height(NaviDimens.Space8))
            Text(
                text = "거리뿐 아니라 계단·턱·폭·현장 차단 상태를 함께 확인합니다.",
                style = MaterialTheme.typography.bodyLarge,
                color = NaviInkMuted,
            )
            Spacer(Modifier.height(NaviDimens.Space20))

            if (uiState.loading) {
                LoadingPanel("실증 구역 데이터를 불러오는 중입니다")
            } else if (session.bootstrap != null) {
                val bootstrap = requireNotNull(session.bootstrap)
                TrustBanner(
                    text = "${bootstrap.areaName} PoC · OSM 보행망과 synthetic 접근성 속성을 사용합니다. 현장 실측·검증 데이터가 아닙니다.",
                )
                Spacer(Modifier.height(NaviDimens.Space20))
                Text(
                    text = "이동 조건",
                    style = MaterialTheme.typography.titleMedium,
                    color = NaviInk,
                )
                Spacer(Modifier.height(NaviDimens.Space8))
                Row(horizontalArrangement = Arrangement.spacedBy(NaviDimens.Space8)) {
                    ProfileChip(
                        label = "휠체어",
                        selected = session.profile == "wheelchair",
                        onClick = { viewModel.setProfile("wheelchair") },
                    )
                    ProfileChip(
                        label = "일반 보행",
                        selected = session.profile == "default",
                        onClick = { viewModel.setProfile("default") },
                    )
                }
                Spacer(Modifier.height(NaviDimens.Space20))
                JourneyPointCard(
                    marker = "A",
                    label = "출발",
                    name = originLabel(session),
                    coordinate = session.origin,
                    markerColor = NaviBlue,
                )
                Spacer(Modifier.height(NaviDimens.Space8))
                JourneyPointCard(
                    marker = "B",
                    label = "도착",
                    name = bootstrap.destination.name,
                    coordinate = session.destination,
                    markerColor = NaviViolet,
                )
                Spacer(Modifier.height(NaviDimens.Space12))
                SecondaryActionButton(
                    text = when (location) {
                        is LocationState.Available -> "현재 위치를 출발지로 사용 중"
                        LocationState.PermissionMissing -> "현재 위치 권한 다시 확인"
                        LocationState.ProviderUnavailable -> "위치 서비스를 켜주세요"
                        LocationState.Waiting -> "현재 위치를 출발지로 사용"
                    },
                    onClick = {
                        val fineGranted = ContextCompat.checkSelfPermission(
                            context,
                            Manifest.permission.ACCESS_FINE_LOCATION,
                        ) == PackageManager.PERMISSION_GRANTED
                        val coarseGranted = ContextCompat.checkSelfPermission(
                            context,
                            Manifest.permission.ACCESS_COARSE_LOCATION,
                        ) == PackageManager.PERMISSION_GRANTED
                        if (fineGranted || coarseGranted) {
                            viewModel.startLocation()
                        } else {
                            locationPermissionLauncher.launch(
                                arrayOf(
                                    Manifest.permission.ACCESS_FINE_LOCATION,
                                    Manifest.permission.ACCESS_COARSE_LOCATION,
                                ),
                            )
                        }
                    },
                )
            }

            uiState.error?.let { error ->
                Spacer(Modifier.height(NaviDimens.Space12))
                ErrorPanel(
                    error,
                    onRetry = (viewModel::loadBootstrap).takeIf { uiState.errorCanRetry },
                )
            }
            Spacer(Modifier.height(104.dp))
        }
    }
}

@Composable
fun RouteScreen(
    viewModel: RouteViewModel,
    onBack: () -> Unit,
    onExplain: () -> Unit,
    onStart: () -> Unit,
) {
    val session by viewModel.sessionState.collectAsStateWithLifecycle()
    val comparison = session.comparison
    if (comparison == null) {
        MissingJourneyScreen(onBack)
        return
    }
    val rerouted = session.reroute != null
    val accessible = session.activeRoute ?: comparison.accessible
    Scaffold(
        contentWindowInsets = WindowInsets.safeDrawing,
        topBar = {
            NaviTopBar(
                title = if (rerouted) "새 접근 가능 경로" else "경로 비교",
                onBack = onBack,
            )
        },
        bottomBar = {
            Surface(color = MaterialTheme.colorScheme.surface) {
                Column(
                    Modifier
                        .navigationBarsPadding()
                        .padding(horizontal = NaviDimens.Space20, vertical = NaviDimens.Space12),
                    verticalArrangement = Arrangement.spacedBy(NaviDimens.Space8),
                ) {
                    PrimaryActionButton("이 경로로 안내 시작", onStart)
                    SecondaryActionButton("왜 이 경로인가요?", onExplain)
                }
            }
        },
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .verticalScroll(rememberScrollState()),
        ) {
            RouteMap(
                standard = comparison.standard,
                accessible = accessible,
                blockGeometry = if (rerouted) session.bootstrap?.blockEdgeGeometry.orEmpty() else emptyList(),
                rerouted = rerouted,
                modifier = Modifier
                    .fillMaxWidth()
                    .height(310.dp),
            )
            PrismDivider()
            Column(
                Modifier.padding(horizontal = NaviDimens.Space20, vertical = NaviDimens.Space20),
            ) {
                if (rerouted) {
                    StatusPill(
                        symbol = "↻",
                        text = "현장 장애를 피해 다시 계산됨",
                        foreground = NaviViolet,
                        background = NaviVioletSoft,
                    )
                    Spacer(Modifier.height(NaviDimens.Space16))
                }
                Text(
                    text = if (rerouted) "지금 통과 가능한 경로" else "두 경로를 비교했어요",
                    style = MaterialTheme.typography.headlineSmall,
                    color = NaviInk,
                    modifier = Modifier.semantics { heading() },
                )
                Spacer(Modifier.height(NaviDimens.Space12))
                TrustBanner("PoC · synthetic 속성 포함 · 현장 미검증 경로")
                Spacer(Modifier.height(NaviDimens.Space16))
                RouteMetricRow(
                    standard = comparison.standard,
                    accessible = accessible,
                )
                Spacer(Modifier.height(NaviDimens.Space12))
                DifferencePanel(comparison, accessible)
                val reasons = (comparison.reasons + accessible.reasons).distinct()
                if (reasons.isNotEmpty()) {
                    Spacer(Modifier.height(NaviDimens.Space16))
                    Text("우회한 이유", style = MaterialTheme.typography.titleMedium, color = NaviInk)
                    Spacer(Modifier.height(NaviDimens.Space8))
                    reasons.take(4).forEach { reason ->
                        ReasonRow(reasonLabel(reason))
                    }
                }
                Spacer(Modifier.height(160.dp))
            }
        }
    }
}

@Composable
fun ExplainScreen(
    viewModel: RouteViewModel,
    onBack: () -> Unit,
) {
    val session by viewModel.sessionState.collectAsStateWithLifecycle()
    val route = session.activeRoute
    Scaffold(
        contentWindowInsets = WindowInsets.safeDrawing,
        topBar = { NaviTopBar(title = "경로 판단 근거", onBack = onBack) },
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .verticalScroll(rememberScrollState())
                .padding(NaviDimens.Space20),
            verticalArrangement = Arrangement.spacedBy(NaviDimens.Space16),
        ) {
            Text(
                "NaVi는 접근 조건을 통과한 구간 중 짧은 경로를 선택합니다.",
                style = MaterialTheme.typography.headlineSmall,
                color = NaviInk,
                modifier = Modifier.semantics { heading() },
            )
            SectionCard {
                Column(verticalArrangement = Arrangement.spacedBy(NaviDimens.Space12)) {
                    Text("적용한 이동 조건", style = MaterialTheme.typography.titleMedium, color = NaviInk)
                    ConstraintRow("계단", "통과하지 않음")
                    ConstraintRow("차단 구간", "통과하지 않음")
                    ConstraintRow("경사·폭·턱", "실험용 프로필 기준 적용")
                }
            }
            SectionCard {
                Column(verticalArrangement = Arrangement.spacedBy(NaviDimens.Space12)) {
                    Text("제외된 구간", style = MaterialTheme.typography.titleMedium, color = NaviInk)
                    val reasons = route?.reasons.orEmpty().distinct()
                    if (reasons.isEmpty()) {
                        Text("현재 경로에서 별도 제외 사유가 없습니다.", color = NaviInkMuted)
                    } else {
                        reasons.forEach { ReasonRow(reasonLabel(it)) }
                    }
                }
            }
            SectionCard {
                Column(verticalArrangement = Arrangement.spacedBy(NaviDimens.Space12)) {
                    Text("데이터 신뢰도", style = MaterialTheme.typography.titleMedium, color = NaviInk)
                    val provenance = route?.provenance
                    KeyValueRow("출처", provenance?.sources?.joinToString().orEmpty().ifBlank { "미상" })
                    KeyValueRow("검증 구간", "${provenance?.verifiedEdges ?: 0}개")
                    KeyValueRow("미검증 구간", "${provenance?.unverifiedEdges ?: 0}개")
                    if (provenance?.containsSynthetic == true) {
                        TrustBanner("일부 접근성 속성은 synthetic 실험 데이터이며 실제 현장 정보로 확정할 수 없습니다.")
                    }
                }
            }
            route?.warnings.orEmpty().forEach { warning ->
                TrustBanner(warning)
            }
        }
    }
}

@Composable
fun NavigationScreen(
    viewModel: NavigationViewModel,
    onBack: () -> Unit,
    onCamera: () -> Unit,
    onReport: () -> Unit,
    onFinish: () -> Unit,
) {
    val session by viewModel.sessionState.collectAsStateWithLifecycle()
    val location by viewModel.locationState.collectAsStateWithLifecycle()
    val route = session.activeRoute
    DisposableEffect(viewModel) {
        viewModel.startSensors()
        onDispose(viewModel::stopSensors)
    }
    if (route == null || session.comparison == null) {
        MissingJourneyScreen(onBack)
        return
    }
    Scaffold(
        contentWindowInsets = WindowInsets.safeDrawing,
        topBar = {
            NaviTopBar(
                title = if (session.reroute == null) "접근 경로 안내" else "우회 경로 안내",
                onBack = onBack,
                trailing = {
                    OutlinedButton(onClick = onFinish) { Text("종료") }
                },
            )
        },
        bottomBar = {
            Surface(color = MaterialTheme.colorScheme.surface) {
                Column(
                    Modifier
                        .navigationBarsPadding()
                        .padding(horizontal = NaviDimens.Space20, vertical = NaviDimens.Space12),
                    verticalArrangement = Arrangement.spacedBy(NaviDimens.Space8),
                ) {
                    PrimaryActionButton("카메라 안내 보기", onCamera)
                    OutlinedButton(
                        onClick = onReport,
                        modifier = Modifier
                            .fillMaxWidth()
                            .height(56.dp),
                        shape = MaterialTheme.shapes.small,
                    ) {
                        Text("앞 구간 통과 불가 제보", color = NaviBlock, fontWeight = FontWeight.Bold)
                    }
                }
            }
        },
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .verticalScroll(rememberScrollState()),
        ) {
            Box {
                RouteMap(
                    standard = session.comparison!!.standard,
                    accessible = route,
                    blockGeometry = if (session.reroute != null) session.bootstrap?.blockEdgeGeometry.orEmpty() else emptyList(),
                    rerouted = session.reroute != null,
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(360.dp),
                )
                StatusPill(
                    symbol = if (session.reroute == null) "◇" else "↻",
                    text = if (session.reroute == null) "설정 조건 통과 · 데모" else "세션 우회 · 미검증",
                    foreground = if (session.reroute == null) NaviCaution else NaviViolet,
                    background = if (session.reroute == null) NaviCautionSoft else NaviVioletSoft,
                    modifier = Modifier
                        .align(Alignment.TopStart)
                        .padding(NaviDimens.Space12),
                )
            }
            PrismDivider()
            Column(
                Modifier.padding(horizontal = NaviDimens.Space20, vertical = NaviDimens.Space20),
                verticalArrangement = Arrangement.spacedBy(NaviDimens.Space16),
            ) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Column {
                        Text("남은 경로", style = MaterialTheme.typography.labelMedium, color = NaviInkMuted)
                        Text(formatDistance(route.distanceM), style = NaviMetricTextStyle, color = NaviInk)
                    }
                    Column(horizontalAlignment = Alignment.End) {
                        Text("예상 시간", style = MaterialTheme.typography.labelMedium, color = NaviInkMuted)
                        Text("약 ${route.estimatedMinutes}분", style = NaviMetricTextStyle, color = NaviInk)
                    }
                }
                if (session.reroute != null) {
                    val previousRoute = session.comparison!!.accessible
                    RerouteDeltaPanel(previousRoute, route)
                }
                LocationStatus(location)
                TrustBanner("카메라 안내는 PoC 오버레이입니다. 이동 중에는 화면보다 주변 환경을 먼저 확인하세요.")
                Spacer(Modifier.height(140.dp))
            }
        }
    }
}

@Composable
fun CameraScreen(
    viewModel: NavigationViewModel,
    onBack: () -> Unit,
    onMap: () -> Unit,
    onReport: () -> Unit,
) {
    val session by viewModel.sessionState.collectAsStateWithLifecycle()
    val heading by viewModel.headingState.collectAsStateWithLifecycle()
    val location by viewModel.locationState.collectAsStateWithLifecycle()
    val context = LocalContext.current
    var arState by remember { mutableStateOf(ArRuntimeState()) }
    val datasetController = remember { ArDatasetController() }
    var cameraGranted by remember {
        mutableStateOf(
            ContextCompat.checkSelfPermission(context, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED,
        )
    }
    val permissionLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission(),
    ) { cameraGranted = it }
    DisposableEffect(viewModel) {
        viewModel.startSensors()
        onDispose(viewModel::stopSensors)
    }
    val route = session.activeRoute
    if (route == null) {
        MissingJourneyScreen(onBack)
        return
    }
    val targetBearing = routeBearing(route.geometry)
    val headingDegrees = (heading as? HeadingState.Available)?.degrees
    val availableLocation = location as? LocationState.Available
    val routeCoordinates = remember(route.geometry) {
        route.geometry.mapNotNull { point ->
            if (point.size < 2) null else GeoCoordinate(
                latitude = point[1],
                longitude = point[0],
            )
        }
    }
    val delta = if (targetBearing != null && headingDegrees != null) {
        normalizeHeadingDelta(targetBearing, headingDegrees)
    } else {
        0f
    }

    Box(Modifier.fillMaxSize().background(Color.Black)) {
        CameraHud(
            cameraGranted = cameraGranted,
            headingDelta = delta,
            datasetController = datasetController,
            routeCoordinates = routeCoordinates,
            userCoordinate = availableLocation?.coordinate?.let {
                GeoCoordinate(latitude = it.lat, longitude = it.lon)
            },
            locationAccuracyMeters = availableLocation?.accuracyMeters,
            headingDegrees = headingDegrees,
            onArStateChanged = { arState = it },
            modifier = Modifier.fillMaxSize(),
        )
        Column(
            modifier = Modifier
                .fillMaxSize()
                .background(Color.Black.copy(alpha = 0.12f))
                .statusBarsPadding()
                .navigationBarsPadding()
                .padding(NaviDimens.Space16),
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                CameraRoundButton("←", "지도 화면으로 돌아가기", onBack)
                StatusPill(
                    symbol = if (arState.mode == ArRuntimeMode.TRACKING && arState.routeAligned) "◎" else "◇",
                    text = arStatusLabel(cameraGranted, arState),
                    foreground = NaviOnDark,
                    background = Color.Black.copy(alpha = 0.52f),
                )
                Spacer(Modifier.size(48.dp))
            }
            Spacer(Modifier.height(NaviDimens.Space20))
            Surface(
                modifier = Modifier.fillMaxWidth(),
                color = Color(0xE6122550),
                shape = MaterialTheme.shapes.medium,
                border = androidx.compose.foundation.BorderStroke(1.dp, Color.White.copy(alpha = 0.28f)),
            ) {
                Row(
                    Modifier.padding(NaviDimens.Space16),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(NaviDimens.Space16),
                ) {
                    Text(
                        text = directionArrow(delta),
                        style = MaterialTheme.typography.displaySmall,
                        color = Color.White,
                    )
                    Column(Modifier.weight(1f)) {
                        Text(
                            text = directionText(delta),
                            style = MaterialTheme.typography.titleLarge,
                            color = Color.White,
                        )
                        Text(
                            text = arGuidanceDetail(arState),
                            style = MaterialTheme.typography.bodySmall,
                            color = Color.White.copy(alpha = 0.75f),
                        )
                    }
                }
            }
            Spacer(Modifier.height(NaviDimens.Space8))
            Surface(
                modifier = Modifier.fillMaxWidth(),
                color = Color.Black.copy(alpha = 0.58f),
                shape = MaterialTheme.shapes.small,
                border = androidx.compose.foundation.BorderStroke(1.dp, Color.White.copy(alpha = 0.24f)),
            ) {
                Text(
                    text = arSafetyNotice(arState),
                    modifier = Modifier.padding(horizontal = NaviDimens.Space12, vertical = NaviDimens.Space8),
                    style = MaterialTheme.typography.bodySmall,
                    color = Color.White.copy(alpha = 0.88f),
                    textAlign = TextAlign.Center,
                )
            }
            Spacer(Modifier.weight(1f))
            if (!cameraGranted) {
                Surface(
                    color = Color(0xE6122550),
                    shape = MaterialTheme.shapes.medium,
                ) {
                    Column(Modifier.padding(NaviDimens.Space16)) {
                        Text("카메라 권한이 필요합니다", color = Color.White, fontWeight = FontWeight.Bold)
                        Spacer(Modifier.height(NaviDimens.Space4))
                        Text(
                            "영상은 서버로 전송하거나 저장하지 않고 화면 미리보기에만 사용합니다.",
                            color = Color.White.copy(alpha = 0.8f),
                            style = MaterialTheme.typography.bodySmall,
                        )
                        Spacer(Modifier.height(NaviDimens.Space12))
                        PrimaryActionButton("카메라 켜기", { permissionLauncher.launch(Manifest.permission.CAMERA) })
                    }
                }
                Spacer(Modifier.height(NaviDimens.Space12))
            }
            if (cameraGranted) {
                ArDatasetControls(
                    state = arState,
                    controller = datasetController,
                )
                Spacer(Modifier.height(NaviDimens.Space8))
            }
            Row(horizontalArrangement = Arrangement.spacedBy(NaviDimens.Space8)) {
                OutlinedButton(
                    onClick = onMap,
                    modifier = Modifier.weight(1f).height(56.dp),
                    colors = androidx.compose.material3.ButtonDefaults.outlinedButtonColors(contentColor = Color.White),
                    border = androidx.compose.foundation.BorderStroke(1.dp, Color.White.copy(alpha = 0.7f)),
                ) { Text("지도 보기") }
                androidx.compose.material3.Button(
                    onClick = onReport,
                    modifier = Modifier.weight(1f).height(56.dp),
                    colors = androidx.compose.material3.ButtonDefaults.buttonColors(containerColor = NaviBlock),
                ) { Text("통과 불가", fontWeight = FontWeight.Bold) }
            }
        }
    }
}

@Composable
private fun ArDatasetControls(
    state: ArRuntimeState,
    controller: ArDatasetController,
) {
    Surface(
        modifier = Modifier.fillMaxWidth(),
        color = Color.Black.copy(alpha = 0.62f),
        shape = MaterialTheme.shapes.small,
        border = androidx.compose.foundation.BorderStroke(1.dp, Color.White.copy(alpha = 0.24f)),
    ) {
        Column(
            modifier = Modifier.padding(NaviDimens.Space12),
            verticalArrangement = Arrangement.spacedBy(NaviDimens.Space8),
        ) {
            Text(
                text = state.datasetMessage ?: "ARCore MP4와 tracking telemetry를 기기에만 저장합니다.",
                style = MaterialTheme.typography.bodySmall,
                color = Color.White.copy(alpha = 0.82f),
                maxLines = 2,
                overflow = TextOverflow.Ellipsis,
            )
            Row(horizontalArrangement = Arrangement.spacedBy(NaviDimens.Space8)) {
                androidx.compose.material3.Button(
                    onClick = when (state.datasetMode) {
                        ArDatasetMode.RECORDING -> controller::stopRecording
                        ArDatasetMode.PLAYBACK,
                        ArDatasetMode.PLAYBACK_FINISHED,
                        -> controller::returnToLive
                        else -> controller::startRecording
                    },
                    modifier = Modifier.weight(1f).height(48.dp),
                    colors = androidx.compose.material3.ButtonDefaults.buttonColors(
                        containerColor = if (state.datasetMode == ArDatasetMode.RECORDING) NaviBlock else NaviBlue,
                    ),
                ) {
                    Text(
                        when (state.datasetMode) {
                            ArDatasetMode.RECORDING -> "녹화 중지"
                            ArDatasetMode.PLAYBACK,
                            ArDatasetMode.PLAYBACK_FINISHED,
                            -> "실시간 전환"
                            else -> "세션 녹화"
                        },
                        fontWeight = FontWeight.Bold,
                    )
                }
                OutlinedButton(
                    onClick = controller::playLatest,
                    enabled = state.latestDatasetName != null && state.datasetMode != ArDatasetMode.RECORDING,
                    modifier = Modifier.weight(1f).height(48.dp),
                    colors = androidx.compose.material3.ButtonDefaults.outlinedButtonColors(contentColor = Color.White),
                    border = androidx.compose.foundation.BorderStroke(1.dp, Color.White.copy(alpha = 0.7f)),
                ) { Text("최근 기록 재생") }
            }
        }
    }
}

private fun arStatusLabel(cameraGranted: Boolean, state: ArRuntimeState): String = when {
    !cameraGranted -> "2D 안내 · 카메라 권한 필요"
    state.datasetMode == ArDatasetMode.RECORDING -> "● AR dataset 기록 중"
    state.datasetMode == ArDatasetMode.PLAYBACK -> "▶ AR dataset 재생"
    state.datasetMode == ArDatasetMode.PLAYBACK_FINISHED -> "AR replay 완료"
    state.mode == ArRuntimeMode.TRACKING && state.routeAligned -> {
        if (state.depthActive) "ARCore · Depth 활성" else "ARCore · 공간 추적"
    }
    state.mode == ArRuntimeMode.TRACKING -> "ARCore 추적 · 2D 경로 폴백"
    state.mode == ArRuntimeMode.CHECKING -> "ARCore · 초기화 중"
    state.mode == ArRuntimeMode.INSTALL_REQUIRED -> "ARCore · 설치 확인"
    else -> "2D 폴백 · ${state.message ?: "정합 대기"}"
}

private fun arGuidanceDetail(state: ArRuntimeState): String = when {
    state.mode == ArRuntimeMode.TRACKING && state.routeAligned -> buildString {
        append("공간 고정 경로")
        state.frameTimeMillis?.let { append(" · %.1f ms".format(Locale.US, it)) }
        append(" · 추적 손실 ${state.trackingLossCount}회")
    }
    state.mode == ArRuntimeMode.TRACKING -> buildString {
        append("경로 정합 대기")
        append(if (state.depthActive) " · Depth 활성" else " · Depth 준비 중")
        state.frameTimeMillis?.let { append(" · %.1f ms".format(Locale.US, it)) }
        append(" · 손실 ${state.trackingLossCount}회")
    }
    else -> "경로 방향과 기기 나침반을 기준으로 안전하게 폴백 표시"
}

private fun arSafetyNotice(state: ArRuntimeState): String =
    if (state.datasetMode == ArDatasetMode.RECORDING) {
        "카메라·IMU dataset을 기기에 저장 중입니다. 민감한 사람·장소가 촬영되지 않게 주의하세요."
    } else if (state.mode == ArRuntimeMode.TRACKING && state.routeAligned) {
        "AR 기술 스파이크 · 현장 보정 전입니다. 이동 중에는 주변 환경을 먼저 확인하세요."
    } else {
        "2D HUD 폴백 · 실제 보도 위치·거리와 공간 정합된 표시가 아닙니다."
    }

@OptIn(ExperimentalLayoutApi::class)
@Composable
fun ReportScreen(
    viewModel: NavigationViewModel,
    onBack: () -> Unit,
    onShowReroute: () -> Unit,
) {
    val session by viewModel.sessionState.collectAsStateWithLifecycle()
    val reportState by viewModel.reportState.collectAsStateWithLifecycle()
    var selectedType by remember { mutableStateOf("blocked_path") }
    var note by remember { mutableStateOf("") }

    LaunchedEffect(Unit) { viewModel.resetReportState() }
    Scaffold(
        contentWindowInsets = WindowInsets.safeDrawing,
        topBar = { NaviTopBar(title = "앞 구간 통과 불가", onBack = onBack) },
        bottomBar = {
            Surface(color = MaterialTheme.colorScheme.surface) {
                Column(
                    Modifier
                        .navigationBarsPadding()
                        .padding(horizontal = NaviDimens.Space20, vertical = NaviDimens.Space12),
                ) {
                    if (reportState.reroute != null) {
                        PrimaryActionButton("변경된 경로 확인", onShowReroute)
                    } else {
                        PrimaryActionButton(
                            text = "이 구간을 피해 다시 찾기",
                            onClick = { viewModel.reportObstacle(selectedType, note.ifBlank { null }) },
                            loading = reportState.submitting,
                        )
                    }
                }
            }
        },
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .verticalScroll(rememberScrollState())
                .padding(horizontal = NaviDimens.Space20),
        ) {
            Spacer(Modifier.height(NaviDimens.Space12))
            if (reportState.reroute != null) {
                RerouteResultPanel(
                    routeChanged = reportState.reroute?.routeChanged == true,
                    candidateCreated = reportState.candidate != null,
                    message = reportState.message,
                )
            } else {
                Text(
                    "무엇 때문에 지나갈 수 없나요?",
                    style = MaterialTheme.typography.headlineSmall,
                    color = NaviInk,
                    modifier = Modifier.semantics { heading() },
                )
                Spacer(Modifier.height(NaviDimens.Space8))
                Text(
                    "선택하면 현재 안내 세션에서만 해당 구간을 즉시 피합니다.",
                    style = MaterialTheme.typography.bodyLarge,
                    color = NaviInkMuted,
                )
                Spacer(Modifier.height(NaviDimens.Space20))
                FlowRow(
                    horizontalArrangement = Arrangement.spacedBy(NaviDimens.Space8),
                    verticalArrangement = Arrangement.spacedBy(NaviDimens.Space8),
                ) {
                    reportTypes.forEach { item ->
                        FilterChip(
                            selected = selectedType == item.first,
                            onClick = { selectedType = item.first },
                            label = { Text(item.second) },
                            leadingIcon = { Text(item.third) },
                            colors = FilterChipDefaults.filterChipColors(
                                selectedContainerColor = NaviBlockSoft,
                                selectedLabelColor = NaviBlock,
                                selectedLeadingIconColor = NaviBlock,
                            ),
                        )
                    }
                }
                Spacer(Modifier.height(NaviDimens.Space20))
                OutlinedTextField(
                    value = note,
                    onValueChange = { if (it.length <= 180) note = it },
                    modifier = Modifier.fillMaxWidth(),
                    label = { Text("상황 메모 (선택)") },
                    supportingText = { Text("${note.length}/180 · 사진·영상은 저장하지 않음") },
                    minLines = 3,
                )
                Spacer(Modifier.height(NaviDimens.Space16))
                TrustBanner(
                    "제보는 검수 대기(pending)로 저장됩니다. 담당자가 승인하기 전에는 다른 사용자의 공용 경로 데이터가 바뀌지 않습니다.",
                )
                Spacer(Modifier.height(NaviDimens.Space12))
                KeyValueRow("적용 구간", "현재 경로의 PoC 실험 구간")
                KeyValueRow("신뢰도", "현장 사용자 입력 · AI 추정값 없음")
            }
            reportState.error?.let {
                Spacer(Modifier.height(NaviDimens.Space12))
                ErrorPanel(it)
            }
            Spacer(Modifier.height(104.dp))
        }
    }
}

@Composable
fun ArrivalScreen(
    viewModel: RouteViewModel,
    onNewRoute: () -> Unit,
) {
    val session by viewModel.sessionState.collectAsStateWithLifecycle()
    val route = session.activeRoute
    Scaffold(
        contentWindowInsets = WindowInsets.safeDrawing,
        bottomBar = {
            Surface(color = MaterialTheme.colorScheme.surface) {
                PrimaryActionButton(
                    "새 경로 찾기",
                    onNewRoute,
                    Modifier.navigationBarsPadding().padding(NaviDimens.Space20),
                )
            }
        },
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(NaviDimens.Space24),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.Center,
        ) {
            Box(
                Modifier
                    .size(84.dp)
                    .background(NaviPassSoft, CircleShape),
                contentAlignment = Alignment.Center,
            ) {
                Text("✓", style = MaterialTheme.typography.displaySmall, color = NaviPass)
            }
            Spacer(Modifier.height(NaviDimens.Space24))
            Text("안내를 마쳤습니다", style = MaterialTheme.typography.headlineMedium, color = NaviInk)
            Spacer(Modifier.height(NaviDimens.Space8))
            Text(
                "실제 도착 여부는 사용자가 확인해야 합니다.",
                style = MaterialTheme.typography.bodyLarge,
                color = NaviInkMuted,
                textAlign = TextAlign.Center,
            )
            route?.let {
                Spacer(Modifier.height(NaviDimens.Space24))
                SectionCard {
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceAround) {
                        Metric("안내 거리", formatDistance(it.distanceM))
                        Metric("예상 시간", "${it.estimatedMinutes}분")
                        Metric("재탐색", if (session.reroute == null) "없음" else "1회")
                    }
                }
            }
        }
    }
}

@Composable
private fun ProfileChip(label: String, selected: Boolean, onClick: () -> Unit) {
    FilterChip(
        selected = selected,
        onClick = onClick,
        label = { Text(label) },
        leadingIcon = { Text(if (label == "휠체어") "♿" else "●") },
        colors = FilterChipDefaults.filterChipColors(
            selectedContainerColor = NaviBlueSoft,
            selectedLabelColor = NaviBlue,
            selectedLeadingIconColor = NaviBlue,
        ),
    )
}

@Composable
private fun JourneyPointCard(
    marker: String,
    label: String,
    name: String,
    coordinate: CoordinateDto?,
    markerColor: Color,
) {
    SectionCard {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Box(
                Modifier.size(42.dp).background(markerColor, CircleShape),
                contentAlignment = Alignment.Center,
            ) {
                Text(marker, color = Color.White, fontWeight = FontWeight.Bold)
            }
            Spacer(Modifier.width(NaviDimens.Space12))
            Column(Modifier.weight(1f)) {
                Text(label, style = MaterialTheme.typography.labelMedium, color = NaviInkMuted)
                Text(
                    name,
                    style = MaterialTheme.typography.titleMedium,
                    color = NaviInk,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
                coordinate?.let {
                    Text(
                        String.format(Locale.US, "%.5f, %.5f", it.lat, it.lon),
                        style = MaterialTheme.typography.bodySmall,
                        color = NaviInkMuted,
                    )
                }
            }
        }
    }
}

@Composable
private fun LoadingPanel(text: String) {
    SectionCard {
        Row(verticalAlignment = Alignment.CenterVertically) {
            CircularProgressIndicator(Modifier.size(24.dp), strokeWidth = 2.dp)
            Spacer(Modifier.width(NaviDimens.Space12))
            Text(text, color = NaviInk)
        }
    }
}

@Composable
private fun ErrorPanel(message: String, onRetry: (() -> Unit)? = null) {
    Surface(
        color = NaviBlockSoft,
        shape = MaterialTheme.shapes.small,
        border = androidx.compose.foundation.BorderStroke(1.dp, NaviBlock.copy(alpha = 0.22f)),
    ) {
        Column(Modifier.fillMaxWidth().padding(NaviDimens.Space16)) {
            Text("연결을 확인해주세요", fontWeight = FontWeight.Bold, color = NaviBlock)
            Spacer(Modifier.height(NaviDimens.Space4))
            Text(message, style = MaterialTheme.typography.bodySmall, color = NaviInk)
            if (onRetry != null) {
                Spacer(Modifier.height(NaviDimens.Space8))
                OutlinedButton(onClick = onRetry) { Text("다시 시도") }
            }
        }
    }
}

@Composable
private fun RouteMetricRow(standard: RouteResultDto, accessible: RouteResultDto) {
    Row(
        Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(NaviDimens.Space8),
    ) {
        RouteMetricCard(
            title = "일반 최단 경로",
            distance = formatDistance(standard.distanceM),
            minutes = standard.estimatedMinutes,
            color = NaviInkMuted,
            modifier = Modifier.weight(1f),
        )
        RouteMetricCard(
            title = "접근 가능 경로",
            distance = formatDistance(accessible.distanceM),
            minutes = accessible.estimatedMinutes,
            color = NaviBlue,
            modifier = Modifier.weight(1f),
        )
    }
}

@Composable
private fun RouteMetricCard(
    title: String,
    distance: String,
    minutes: Int,
    color: Color,
    modifier: Modifier = Modifier,
) {
    Surface(
        modifier = modifier,
        color = MaterialTheme.colorScheme.surface,
        shape = MaterialTheme.shapes.medium,
        border = androidx.compose.foundation.BorderStroke(1.dp, color.copy(alpha = 0.28f)),
    ) {
        Column(Modifier.padding(NaviDimens.Space16)) {
            Box(Modifier.size(10.dp).background(color, CircleShape))
            Spacer(Modifier.height(NaviDimens.Space12))
            Text(title, style = MaterialTheme.typography.labelMedium, color = NaviInkMuted)
            Spacer(Modifier.height(NaviDimens.Space4))
            Text(distance, style = NaviMetricTextStyle, color = NaviInk)
            Text("약 ${minutes}분", style = MaterialTheme.typography.bodySmall, color = NaviInkMuted)
        }
    }
}

@Composable
private fun DifferencePanel(comparison: RouteComparisonDto, active: RouteResultDto) {
    val difference = active.distanceM - comparison.standard.distanceM
    Row(
        Modifier
            .fillMaxWidth()
            .background(NaviSurfaceRaised, MaterialTheme.shapes.small)
            .padding(NaviDimens.Space16),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Column {
            Text("접근 조건으로 추가된 거리", style = MaterialTheme.typography.labelMedium, color = NaviInkMuted)
            Text(
                if (difference > 0) "+${formatDistance(difference)}" else "추가 거리 없음",
                style = NaviMetricTextStyle,
                color = NaviInk,
            )
        }
        StatusPill("◇", "설정 조건 우선 · 데모", NaviCaution, NaviCautionSoft)
    }
}

@Composable
private fun RerouteDeltaPanel(previous: RouteResultDto, current: RouteResultDto) {
    val distanceDelta = current.distanceM - previous.distanceM
    val minuteDelta = current.estimatedMinutes - previous.estimatedMinutes
    Surface(
        color = NaviVioletSoft,
        shape = MaterialTheme.shapes.small,
        border = androidx.compose.foundation.BorderStroke(1.dp, NaviViolet.copy(alpha = 0.2f)),
    ) {
        Row(
            modifier = Modifier.fillMaxWidth().padding(NaviDimens.Space12),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column {
                Text("재탐색 변화", style = MaterialTheme.typography.labelMedium, color = NaviInkMuted)
                Text("제보 전 접근 경로 대비", style = MaterialTheme.typography.bodySmall, color = NaviInk)
            }
            Text(
                text = "${signedDistance(distanceDelta)} · ${signedMinutes(minuteDelta)}",
                style = MaterialTheme.typography.titleMedium,
                color = NaviViolet,
                fontWeight = FontWeight.Bold,
            )
        }
    }
}

@Composable
private fun ReasonRow(text: String) {
    Row(
        Modifier.padding(vertical = NaviDimens.Space4),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(NaviDimens.Space8),
    ) {
        Box(Modifier.size(7.dp).background(NaviViolet, CircleShape))
        Text(text, style = MaterialTheme.typography.bodyMedium, color = NaviInk)
    }
}

@Composable
private fun ConstraintRow(label: String, value: String) {
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
        Text(label, color = NaviInk)
        Text(value, color = NaviPass, fontWeight = FontWeight.SemiBold)
    }
}

@Composable
private fun KeyValueRow(label: String, value: String) {
    Row(
        Modifier.fillMaxWidth().padding(vertical = NaviDimens.Space4),
        horizontalArrangement = Arrangement.SpaceBetween,
    ) {
        Text(label, style = MaterialTheme.typography.bodyMedium, color = NaviInkMuted)
        Text(
            value,
            modifier = Modifier.weight(1f).padding(start = NaviDimens.Space16),
            style = MaterialTheme.typography.bodyMedium,
            color = NaviInk,
            textAlign = TextAlign.End,
        )
    }
}

@Composable
private fun LocationStatus(location: LocationState) {
    val status = when (location) {
        is LocationState.Available -> LocationDisplay(
            "●",
            "추정 오차 약 ${location.accuracyMeters?.toInt() ?: "?"}m · ${formatObservationTime(location.observedAtMillis)} 갱신",
            NaviPass,
            NaviPassSoft,
        )
        LocationState.PermissionMissing -> LocationDisplay(
            "!",
            "위치 권한 없음 · 경로 미리보기",
            NaviCaution,
            NaviCautionSoft,
        )
        LocationState.ProviderUnavailable -> LocationDisplay(
            "!",
            "위치 서비스 꺼짐 · 경로 미리보기",
            NaviCaution,
            NaviCautionSoft,
        )
        LocationState.Waiting -> LocationDisplay(
            "…",
            "현재 위치 확인 중",
            NaviInkMuted,
            NaviSurfaceRaised,
        )
    }
    StatusPill(
        symbol = status.symbol,
        text = status.text,
        foreground = status.foreground,
        background = status.background,
    )
}

@Composable
private fun CameraRoundButton(text: String, description: String, onClick: () -> Unit) {
    Box(
        modifier = Modifier
            .size(48.dp)
            .background(Color.Black.copy(alpha = 0.52f), CircleShape)
            .border(1.dp, Color.White.copy(alpha = 0.38f), CircleShape)
            .clickable(onClick = onClick)
            .semantics { contentDescription = description },
        contentAlignment = Alignment.Center,
    ) {
        Text(text, color = Color.White, style = MaterialTheme.typography.titleLarge)
    }
}

@Composable
private fun RerouteResultPanel(
    routeChanged: Boolean,
    candidateCreated: Boolean,
    message: String?,
) {
    Column(verticalArrangement = Arrangement.spacedBy(NaviDimens.Space20)) {
        Box(
            Modifier.size(72.dp).background(NaviVioletSoft, CircleShape),
            contentAlignment = Alignment.Center,
        ) {
            Text("↻", style = MaterialTheme.typography.displaySmall, color = NaviViolet)
        }
        Text(
            if (routeChanged) "장애 구간을 피해\n새 경로를 찾았어요." else "현재 경로를 다시 확인했어요.",
            style = MaterialTheme.typography.headlineMedium,
            color = NaviInk,
        )
        message?.let { Text(it, style = MaterialTheme.typography.bodyLarge, color = NaviInkMuted) }
        SectionCard {
            Column(verticalArrangement = Arrangement.spacedBy(NaviDimens.Space12)) {
                StatusLine("현재 안내 세션", "즉시 우회 적용", NaviPass)
                StatusLine(
                    "현장 제보",
                    if (candidateCreated) "검수 대기 · pending" else "저장 재시도 필요",
                    if (candidateCreated) NaviCaution else NaviBlock,
                )
                StatusLine("공용 그래프", "아직 변경되지 않음", NaviInkMuted)
            }
        }
        TrustBanner("검수 승인 후에만 확인된 접근성 데이터로 전환할 수 있습니다.")
    }
}

@Composable
private fun StatusLine(label: String, value: String, color: Color) {
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
        Text(label, color = NaviInkMuted)
        Text(value, color = color, fontWeight = FontWeight.Bold)
    }
}

@Composable
private fun Metric(label: String, value: String) {
    Column(horizontalAlignment = Alignment.CenterHorizontally) {
        Text(value, style = NaviMetricTextStyle, color = NaviInk)
        Text(label, style = MaterialTheme.typography.bodySmall, color = NaviInkMuted)
    }
}

@Composable
private fun MissingJourneyScreen(onBack: () -> Unit) {
    Scaffold(
        contentWindowInsets = WindowInsets.safeDrawing,
        topBar = { NaviTopBar(title = "경로 없음", onBack = onBack) },
    ) { padding ->
        Column(
            Modifier.fillMaxSize().padding(padding).padding(NaviDimens.Space24),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.Center,
        ) {
            Text("계산된 경로가 없습니다.", style = MaterialTheme.typography.titleLarge, color = NaviInk)
            Spacer(Modifier.height(NaviDimens.Space8))
            Text("이전 화면에서 경로를 다시 찾아주세요.", color = NaviInkMuted)
        }
    }
}

private fun originLabel(session: NaviSessionState): String {
    val bootstrap = session.bootstrap ?: return "출발지"
    val origin = session.origin ?: return bootstrap.origin.name
    val isDemoOrigin = abs(origin.lat - bootstrap.origin.coordinate.lat) < 0.000001 &&
        abs(origin.lon - bootstrap.origin.coordinate.lon) < 0.000001
    return if (isDemoOrigin) bootstrap.origin.name else "현재 위치"
}

private fun formatDistance(value: Double): String = if (value >= 1_000) {
    String.format(Locale.KOREA, "%.1fkm", value / 1_000.0)
} else {
    String.format(Locale.KOREA, "%.0fm", value)
}

private fun signedDistance(value: Double): String = if (value >= 0) {
    "+${formatDistance(value)}"
} else {
    "-${formatDistance(-value)}"
}

private fun signedMinutes(value: Int): String = if (value >= 0) "+${value}분" else "${value}분"

private fun formatObservationTime(timestampMillis: Long): String =
    SimpleDateFormat("HH:mm", Locale.KOREA).format(Date(timestampMillis))

private fun directionArrow(delta: Float): String = when {
    delta < -22f -> "↖"
    delta > 22f -> "↗"
    else -> "↑"
}

private fun directionText(delta: Float): String = when {
    delta < -22f -> "왼쪽 방향으로 맞추세요"
    delta > 22f -> "오른쪽 방향으로 맞추세요"
    else -> "경로 방향으로 이동하세요"
}

private val reportTypes = listOf(
    Triple("blocked_path", "통행 불가", "⛔"),
    Triple("construction", "공사", "△"),
    Triple("high_curb", "높은 턱", "▰"),
    Triple("stairs", "계단", "▤"),
    Triple("elevator_outage", "엘리베이터 중단", "↕"),
    Triple("temporary_closure", "임시 폐쇄", "×"),
)

private data class LocationDisplay(
    val symbol: String,
    val text: String,
    val foreground: Color,
    val background: Color,
)
