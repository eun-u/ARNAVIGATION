package kr.co.navi.mobility.ui.screens

import android.Manifest
import android.content.pm.PackageManager
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import kr.co.navi.mobility.ar.ArDatasetController
import kr.co.navi.mobility.ar.ArRuntimeMode
import kr.co.navi.mobility.ar.ArRuntimeState
import kr.co.navi.mobility.ar.sensors.HeadingState
import kr.co.navi.mobility.ar.ui.CameraHud
import kr.co.navi.mobility.guidance.contract.ArrivalGateProgress
import kr.co.navi.mobility.guidance.contract.ArrivalGateStatus
import kr.co.navi.mobility.guidance.contract.GeoCoordinate
import kr.co.navi.mobility.guidance.contract.forwardRouteBearing
import kr.co.navi.mobility.guidance.contract.normalizeHeadingDelta
import kr.co.navi.mobility.guidance.contract.routeBearing
import kr.co.navi.mobility.location.LocationState
import kr.co.navi.mobility.ui.NavigationViewModel
import kr.co.navi.mobility.ui.components.DemoSymbol
import kr.co.navi.mobility.ui.components.DemoVectorIcon
import kr.co.navi.mobility.ui.components.PrimaryActionButton
import kr.co.navi.mobility.ui.components.RouteMap
import kr.co.navi.mobility.ui.components.SecondaryActionButton
import kr.co.navi.mobility.ui.theme.NaviBlue
import kr.co.navi.mobility.ui.theme.NaviCaution
import kr.co.navi.mobility.ui.theme.NaviCautionSoft
import kr.co.navi.mobility.ui.theme.NaviGlass
import kr.co.navi.mobility.ui.theme.NaviInk
import kr.co.navi.mobility.ui.theme.NaviInkMuted
import kr.co.navi.mobility.ui.theme.NaviLine
import kr.co.navi.mobility.ui.theme.NaviPass
import kr.co.navi.mobility.ui.theme.NaviPassSoft
import kr.co.navi.mobility.ui.theme.NaviViolet

@Composable
fun FrontendMapNavigationScreen(
    viewModel: NavigationViewModel,
    onBack: () -> Unit,
    onCamera: () -> Unit,
    onReport: () -> Unit,
    onStop: () -> Unit,
) {
    val session by viewModel.sessionState.collectAsStateWithLifecycle()
    val location by viewModel.locationState.collectAsStateWithLifecycle()
    val heading by viewModel.headingState.collectAsStateWithLifecycle()
    val arrival by viewModel.arrivalState.collectAsStateWithLifecycle()
    val route = session.activeRoute
    val direction = calculateGuidanceDirection(route?.geometry.orEmpty(), location, heading)
    DisposableEffect(viewModel) {
        viewModel.startSensors()
        onDispose(viewModel::stopSensors)
    }
    Box(Modifier.fillMaxSize().background(Color(0xFFE9EEF3))) {
        val comparison = session.comparison
        if (route != null && comparison != null) {
            RouteMap(
                standard = comparison.standard,
                accessible = route,
                blockGeometry = if (session.reroute != null) session.bootstrap?.blockEdgeGeometry.orEmpty() else emptyList(),
                rerouted = session.reroute != null,
                modifier = Modifier.fillMaxSize(),
            )
        } else {
            GuidanceMap(Modifier.fillMaxSize())
        }
        Column(Modifier.fillMaxSize()) {
            Surface(color = Color(0xFF11151D), shadowElevation = 8.dp) {
                Row(
                    Modifier
                        .fillMaxWidth()
                        .statusBarsPadding()
                        .height(88.dp)
                        .padding(horizontal = 14.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Text(
                        "×",
                        modifier = Modifier.clickable(onClick = onBack).padding(10.dp),
                        style = MaterialTheme.typography.titleLarge,
                        color = Color.White,
                    )
                    Spacer(Modifier.width(8.dp))
                    Text(direction?.let(::guidanceArrow) ?: "·", style = MaterialTheme.typography.headlineMedium, color = Color.White)
                    Spacer(Modifier.width(10.dp))
                    Column(Modifier.weight(1f)) {
                        Row(verticalAlignment = Alignment.Bottom) {
                            Text(route?.distanceM?.let(::formatGuidanceDistance) ?: "—", style = MaterialTheme.typography.headlineSmall, color = Color.White)
                            Spacer(Modifier.width(8.dp))
                            Text(direction?.let(::guidanceInstruction) ?: "위치·방향 확인 중", style = MaterialTheme.typography.titleLarge, color = Color.White)
                        }
                        Text("현재 위치에 가장 가까운 진행 선분 기준", style = MaterialTheme.typography.labelMedium, color = Color.White.copy(alpha = 0.72f))
                    }
                }
            }
            Row(
                Modifier
                    .fillMaxWidth()
                    .background(Color(0xFF11151D))
                    .padding(horizontal = 14.dp, vertical = 7.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text("⚠ 다음 구간은 미검증 정보예요. 실제 상태를 꼭 확인하세요.", style = MaterialTheme.typography.labelMedium, color = Color(0xFFFFD178))
            }
            Spacer(Modifier.weight(1f))
            Surface(
                color = NaviGlass.InteractiveFallback,
                shape = RoundedCornerShape(topStart = 26.dp, topEnd = 26.dp),
                shadowElevation = 14.dp,
            ) {
                Column(
                    Modifier
                        .fillMaxWidth()
                        .navigationBarsPadding()
                        .padding(horizontal = 20.dp, vertical = 12.dp),
                ) {
                    Box(Modifier.align(Alignment.CenterHorizontally).size(width = 40.dp, height = 4.dp).background(NaviInk.copy(alpha = 0.16f), CircleShape))
                    Spacer(Modifier.height(10.dp))
                    Row(verticalAlignment = Alignment.Bottom) {
                        Column(Modifier.weight(1f)) {
                            Text("남은 시간", style = MaterialTheme.typography.labelMedium, color = NaviInkMuted)
                            Row(verticalAlignment = Alignment.Bottom) {
                                Text(route?.estimatedMinutes?.toString() ?: "—", style = MaterialTheme.typography.displaySmall, color = NaviInk)
                                Text("분", modifier = Modifier.padding(bottom = 4.dp), style = MaterialTheme.typography.titleMedium, color = NaviInk)
                            }
                        }
                        Column(horizontalAlignment = Alignment.End) {
                            Text("남은 거리", style = MaterialTheme.typography.labelMedium, color = NaviInkMuted)
                            Text(route?.distanceM?.let(::formatGuidanceDistance) ?: "—", style = MaterialTheme.typography.titleLarge, color = NaviInk)
                        }
                        Spacer(Modifier.width(20.dp))
                        Column(horizontalAlignment = Alignment.End) {
                            Text("도착 판정", style = MaterialTheme.typography.labelMedium, color = NaviInkMuted)
                            Text(arrivalSummary(arrival, viewModel.arrivalGateConfig.requiredConsecutiveObservations), style = MaterialTheme.typography.titleMedium, color = NaviInk)
                        }
                    }
                    Spacer(Modifier.height(9.dp))
                    Box(
                        Modifier
                            .fillMaxWidth()
                            .height(5.dp)
                            .background(NaviLine, CircleShape),
                    ) {
                        Box(
                            Modifier
                                .fillMaxWidth(0.42f)
                                .height(5.dp)
                                .background(NaviBlue, CircleShape),
                        )
                    }
                    Spacer(Modifier.height(10.dp))
                    Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                        SecondaryActionButton("⚑  길이 막혔어요", onReport, Modifier.weight(1f))
                        PrimaryActionButton("안내 종료", onStop, Modifier.weight(1f))
                    }
                }
            }
        }
        Column(
            modifier = Modifier
                .align(Alignment.CenterEnd)
                .padding(end = 14.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            GuidanceRoundButton(DemoSymbol.Locate, "현재 위치", {})
            GuidanceRoundButton(DemoSymbol.Volume, "음성 안내", {})
            GuidanceRoundButton(DemoSymbol.Camera, "카메라 AR 안내", onCamera, active = true)
        }
    }
}

@Composable
private fun GuidanceRoundButton(
    symbol: DemoSymbol,
    description: String,
    onClick: () -> Unit,
    active: Boolean = false,
) {
    Box(
        Modifier
            .size(48.dp)
            .background(if (active) NaviBlue else NaviGlass.InteractiveFallback, CircleShape)
            .clickable(onClick = onClick),
        contentAlignment = Alignment.Center,
    ) {
        DemoVectorIcon(symbol, description, Modifier.size(23.dp), if (active) Color.White else NaviInk)
    }
}

@Composable
private fun GuidanceMap(modifier: Modifier = Modifier) {
    Canvas(modifier.background(Color(0xFFE8EDF2))) {
        val cellW = size.width / 3.4f
        val cellH = size.height / 5.1f
        for (row in 0..5) {
            for (col in 0..3) {
                drawRect(
                    if (col == 3 && row > 2) Color(0xFFDDEEDC) else Color(0xFFDCE3EA),
                    topLeft = Offset(col * cellW + 8f, row * cellH + 8f),
                    size = Size(cellW - 18f, cellH - 18f),
                )
            }
        }
        val route = Path().apply {
            moveTo(size.width * 0.26f, size.height * 0.78f)
            lineTo(size.width * 0.26f, size.height * 0.56f)
            lineTo(size.width * 0.58f, size.height * 0.56f)
            lineTo(size.width * 0.58f, size.height * 0.36f)
            lineTo(size.width * 0.82f, size.height * 0.36f)
            lineTo(size.width * 0.82f, size.height * 0.20f)
        }
        drawPath(route, NaviBlue.copy(alpha = 0.38f), style = Stroke(width = 18f, cap = StrokeCap.Round))
        drawPath(route, NaviBlue, style = Stroke(width = 9f, cap = StrokeCap.Round))
        drawCircle(Color.White, 17f, Offset(size.width * 0.26f, size.height * 0.78f))
        drawCircle(NaviBlue, 10f, Offset(size.width * 0.26f, size.height * 0.78f))
    }
}

@Composable
fun FrontendCameraScreen(
    viewModel: NavigationViewModel,
    onMap: () -> Unit,
    onReport: () -> Unit,
    onStop: () -> Unit,
) {
    val session by viewModel.sessionState.collectAsStateWithLifecycle()
    val location by viewModel.locationState.collectAsStateWithLifecycle()
    val heading by viewModel.headingState.collectAsStateWithLifecycle()
    val route = session.activeRoute
    val direction = calculateGuidanceDirection(route?.geometry.orEmpty(), location, heading)
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
    val availableLocation = location as? LocationState.Available
    val userCoordinate = availableLocation?.coordinate?.let {
        GeoCoordinate(latitude = it.lat, longitude = it.lon)
    }
    val headingDegrees = (heading as? HeadingState.Available)?.degrees
    val routeCoordinates = remember(route?.geometry) {
        route?.geometry.orEmpty().mapNotNull { point ->
            if (point.size < 2) null else GeoCoordinate(latitude = point[1], longitude = point[0])
        }
    }
    DisposableEffect(viewModel) {
        viewModel.startSensors()
        onDispose(viewModel::stopSensors)
    }
    Box(Modifier.fillMaxSize().background(Color(0xFF11151D))) {
        CameraHud(
            cameraGranted = cameraGranted,
            headingDelta = direction ?: 0f,
            datasetController = datasetController,
            routeCoordinates = routeCoordinates,
            userCoordinate = userCoordinate,
            locationAccuracyMeters = availableLocation?.accuracyMeters,
            headingDegrees = headingDegrees,
            onArStateChanged = { arState = it },
            modifier = Modifier.fillMaxSize(),
        )
        Column(
            Modifier
                .fillMaxSize()
                .statusBarsPadding()
                .navigationBarsPadding()
                .padding(horizontal = 24.dp, vertical = 20.dp),
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(direction?.let(::guidanceArrow) ?: "·", style = MaterialTheme.typography.headlineMedium, color = Color.White)
                Spacer(Modifier.width(16.dp))
                Column {
                    Row(verticalAlignment = Alignment.Bottom) {
                        Text(route?.distanceM?.let(::formatGuidanceDistance) ?: "—", style = MaterialTheme.typography.headlineMedium, color = Color.White)
                        Spacer(Modifier.width(7.dp))
                        Text(direction?.let(::guidanceInstruction) ?: "위치·방향 확인 중", style = MaterialTheme.typography.titleLarge, color = Color.White)
                    }
                    Text("현재 위치의 진행 선분을 따라 안내", style = MaterialTheme.typography.labelMedium, color = Color.White.copy(alpha = 0.70f))
                }
            }
            Spacer(Modifier.height(18.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(22.dp)) {
                Text(arRuntimeLabel(cameraGranted, arState), style = MaterialTheme.typography.labelMedium, color = Color(0xFF55D7BF))
                Text("수동 휠체어 조건", style = MaterialTheme.typography.labelMedium, color = Color.White)
                Text(availableLocation?.accuracyMeters?.let { "GPS ±${it.toInt()}m" } ?: "GPS 확인 중", style = MaterialTheme.typography.labelMedium, color = Color.White)
            }
            if (!cameraGranted) {
                Spacer(Modifier.height(12.dp))
                Text(
                    "카메라 켜기",
                    modifier = Modifier.clickable { permissionLauncher.launch(Manifest.permission.CAMERA) },
                    style = MaterialTheme.typography.titleMedium,
                    color = Color(0xFFFFD178),
                )
            }
            Spacer(Modifier.weight(1f))
            Row(verticalAlignment = Alignment.Top, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                Text("ⓘ", style = MaterialTheme.typography.bodySmall, color = Color(0xFFFFC75A))
                Text(
                    "화면이 아니라 앞을 보고 이동하세요. 카메라 영상은\n저장·전송하지 않아요.",
                    style = MaterialTheme.typography.bodySmall,
                    color = Color.White,
                )
            }
            Spacer(Modifier.height(16.dp))
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceAround) {
                CameraControl(DemoSymbol.Map, "지도", onMap)
                CameraControl(DemoSymbol.Volume, "음성", {}, active = true)
                CameraControl(DemoSymbol.Report, "제보", onReport)
                CameraControl(DemoSymbol.Close, "종료", onStop, destructive = true)
            }
        }
    }
}

private fun calculateGuidanceDirection(
    geometry: List<List<Double>>,
    location: LocationState,
    heading: HeadingState,
): Float? {
    val headingDegrees = (heading as? HeadingState.Available)?.degrees ?: return null
    val availableLocation = location as? LocationState.Available
    val userCoordinate = availableLocation?.coordinate?.let {
        GeoCoordinate(latitude = it.lat, longitude = it.lon)
    }
    val targetBearing = if (
        userCoordinate != null &&
        availableLocation.accuracyMeters != null &&
        availableLocation.accuracyMeters <= MAX_DIRECTION_LOCATION_ACCURACY_METERS
    ) {
        forwardRouteBearing(geometry, userCoordinate)
    } else {
        null
    } ?: routeBearing(geometry) ?: return null
    return normalizeHeadingDelta(targetBearing, headingDegrees)
}

private fun guidanceArrow(delta: Float): String = when {
    delta < -22f -> "↖"
    delta > 22f -> "↗"
    else -> "↑"
}

private fun guidanceInstruction(delta: Float): String = when {
    delta < -22f -> "왼쪽 방향으로 맞추세요"
    delta > 22f -> "오른쪽 방향으로 맞추세요"
    else -> "경로 방향으로 이동하세요"
}

private fun formatGuidanceDistance(distanceMeters: Double): String = when {
    distanceMeters >= 1_000.0 -> String.format("%.1fkm", distanceMeters / 1_000.0)
    else -> "${distanceMeters.toInt()}m"
}

private fun arrivalSummary(progress: ArrivalGateProgress, requiredObservations: Int): String = when (progress.status) {
    ArrivalGateStatus.WAITING_FOR_LOCATION -> "위치 확인 중"
    ArrivalGateStatus.POOR_ACCURACY -> "정확도 부족"
    ArrivalGateStatus.OUTSIDE_RADIUS -> progress.distanceMeters?.let { "${it.toInt()}m 남음" } ?: "도착 확인 중"
    ArrivalGateStatus.CONFIRMING -> "확인 ${progress.consecutiveObservations}/$requiredObservations"
    ArrivalGateStatus.ARRIVED -> "도착 확인"
}

private fun arRuntimeLabel(cameraGranted: Boolean, state: ArRuntimeState): String = when {
    !cameraGranted -> "● 2D 안내"
    state.mode == ArRuntimeMode.TRACKING && state.routeAligned -> "● AR 경로 정합"
    state.mode == ArRuntimeMode.TRACKING -> "● AR 위치 정합 중"
    else -> "● 2D 대체 안내"
}

private const val MAX_DIRECTION_LOCATION_ACCURACY_METERS = 30f

@Composable
private fun CameraControl(
    symbol: DemoSymbol,
    label: String,
    onClick: () -> Unit,
    active: Boolean = false,
    destructive: Boolean = false,
) {
    val background = when {
        destructive -> Color(0xFFC92C43)
        active -> Color(0xFF4A47E0)
        else -> Color(0xFF343944)
    }
    Column(horizontalAlignment = Alignment.CenterHorizontally) {
        Box(
            Modifier
                .size(50.dp)
                .background(background, CircleShape)
                .clickable(onClick = onClick),
            contentAlignment = Alignment.Center,
        ) {
            DemoVectorIcon(symbol, label, Modifier.size(24.dp), Color.White)
        }
        Spacer(Modifier.height(6.dp))
        Text(label, style = MaterialTheme.typography.labelMedium, color = Color.White)
    }
}

@Composable
private fun CameraCorridor(modifier: Modifier = Modifier) {
    Canvas(modifier) {
        drawRect(Color(0xFF121720))
        drawRect(Color(0xFF0E131B), Offset(0f, size.height * 0.20f), Size(size.width * 0.23f, size.height * 0.36f))
        drawRect(Color(0xFF0E131B), Offset(size.width * 0.80f, size.height * 0.20f), Size(size.width * 0.20f, size.height * 0.36f))
        val road = Path().apply {
            moveTo(size.width * 0.16f, size.height)
            lineTo(size.width * 0.36f, size.height * 0.49f)
            lineTo(size.width * 0.67f, size.height * 0.49f)
            lineTo(size.width * 0.86f, size.height)
            close()
        }
        drawPath(road, Color(0xFF181D27))
        val centers = listOf(
            0.84f to NaviBlue,
            0.72f to Color(0xFF4B54D0),
            0.64f to NaviViolet,
            0.57f to Color(0xFF2B96AF),
        )
        centers.forEachIndexed { index, (y, color) ->
            val half = (0.14f - index * 0.022f) * size.width
            val centerX = size.width * 0.50f
            val topY = size.height * (y - 0.075f)
            val bottomY = size.height * y
            val pane = Path().apply {
                moveTo(centerX - half * 0.68f, topY)
                lineTo(centerX + half * 0.68f, topY)
                lineTo(centerX + half, bottomY)
                lineTo(centerX - half, bottomY)
                close()
            }
            drawPath(pane, color)
        }
        drawLine(
            Color.White.copy(alpha = 0.42f),
            Offset(size.width * 0.50f, size.height * 0.52f),
            Offset(size.width * 0.50f, size.height * 0.88f),
            3f,
            pathEffect = androidx.compose.ui.graphics.PathEffect.dashPathEffect(floatArrayOf(8f, 14f)),
        )
        val arrow = Path().apply {
            moveTo(size.width * 0.42f, size.height * 0.54f)
            lineTo(size.width * 0.50f, size.height * 0.60f)
            lineTo(size.width * 0.58f, size.height * 0.54f)
        }
        drawPath(arrow, Color(0xFF9DA3AE), style = Stroke(width = 22f, cap = StrokeCap.Square))
    }
}
