package kr.co.navi.mobility.ar.ui

import android.app.Activity
import android.content.Context
import android.content.ContextWrapper
import androidx.camera.core.CameraSelector
import androidx.camera.view.CameraController
import androidx.camera.view.LifecycleCameraController
import androidx.camera.view.PreviewView
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.drawscope.rotate
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.viewinterop.AndroidView
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.LocalLifecycleOwner
import kr.co.navi.mobility.ar.ArCoreNavigationView
import kr.co.navi.mobility.ar.ArDatasetController
import kr.co.navi.mobility.ar.ArRuntimeMode
import kr.co.navi.mobility.ar.ArRuntimeState
import kr.co.navi.mobility.guidance.contract.GeoCoordinate
import kotlin.math.max

private val RouteBlue = Color(0xFF2563EB)
private val RouteViolet = Color(0xFF7C3AED)
private val CameraScrim = Color(0xFF081633)

@Composable
fun CameraHud(
    cameraGranted: Boolean,
    headingDelta: Float,
    modifier: Modifier = Modifier,
    datasetController: ArDatasetController? = null,
    routeCoordinates: List<GeoCoordinate> = emptyList(),
    userCoordinate: GeoCoordinate? = null,
    locationAccuracyMeters: Float? = null,
    headingDegrees: Float? = null,
    onArStateChanged: (ArRuntimeState) -> Unit = {},
) {
    val context = LocalContext.current
    val activity = remember(context) { context.findActivity() }
    var arState by remember { mutableStateOf(ArRuntimeState()) }
    val useArCore = cameraGranted && activity != null && arState.mode != ArRuntimeMode.UNAVAILABLE

    LaunchedEffect(arState) { onArStateChanged(arState) }

    Box(modifier) {
        when {
            useArCore -> ArCorePreview(
                activity = requireNotNull(activity),
                routeCoordinates = routeCoordinates,
                userCoordinate = userCoordinate,
                locationAccuracyMeters = locationAccuracyMeters,
                headingDegrees = headingDegrees,
                onStateChanged = { arState = it },
                datasetController = datasetController,
                modifier = Modifier.fillMaxSize(),
            )

            cameraGranted -> CameraXPreview(Modifier.fillMaxSize())
            else -> CameraFallback(Modifier.fillMaxSize())
        }
        if (!cameraGranted || arState.shouldUse2dFallback) {
            PrismaticRouteRibbon(
                headingDelta = headingDelta,
                modifier = Modifier.fillMaxSize(),
            )
        }
    }
}

@Composable
private fun ArCorePreview(
    activity: Activity,
    routeCoordinates: List<GeoCoordinate>,
    userCoordinate: GeoCoordinate?,
    locationAccuracyMeters: Float?,
    headingDegrees: Float?,
    onStateChanged: (ArRuntimeState) -> Unit,
    datasetController: ArDatasetController?,
    modifier: Modifier = Modifier,
) {
    val context = LocalContext.current
    val lifecycleOwner = LocalLifecycleOwner.current
    val currentListener by rememberUpdatedState(onStateChanged)
    val view = remember(context, activity) {
        ArCoreNavigationView(context, activity) { currentListener(it) }
    }

    DisposableEffect(view, lifecycleOwner, datasetController) {
        datasetController?.attach(view)
        val observer = LifecycleEventObserver { _, event ->
            when (event) {
                Lifecycle.Event.ON_RESUME -> view.resumeSession()
                Lifecycle.Event.ON_PAUSE -> view.pauseSession()
                Lifecycle.Event.ON_DESTROY -> view.closeSession()
                else -> Unit
            }
        }
        lifecycleOwner.lifecycle.addObserver(observer)
        if (lifecycleOwner.lifecycle.currentState.isAtLeast(Lifecycle.State.RESUMED)) {
            view.resumeSession()
        }
        onDispose {
            lifecycleOwner.lifecycle.removeObserver(observer)
            datasetController?.detach(view)
            view.closeSession()
        }
    }

    AndroidView(
        factory = { view },
        update = { arView ->
            arView.setStateListener { currentListener(it) }
            arView.updateGuidance(
                route = routeCoordinates,
                user = userCoordinate,
                locationAccuracyMeters = locationAccuracyMeters,
                headingDegrees = headingDegrees,
            )
        },
        modifier = modifier,
    )
}

@Composable
private fun CameraXPreview(modifier: Modifier = Modifier) {
    val context = LocalContext.current
    val lifecycleOwner = LocalLifecycleOwner.current
    val controller = remember(context) {
        LifecycleCameraController(context).apply {
            cameraSelector = CameraSelector.DEFAULT_BACK_CAMERA
            setEnabledUseCases(0)
        }
    }
    DisposableEffect(controller, lifecycleOwner) {
        controller.bindToLifecycle(lifecycleOwner)
        onDispose { controller.unbind() }
    }

    AndroidView(
        factory = { previewContext: Context ->
            PreviewView(previewContext).apply {
                scaleType = PreviewView.ScaleType.FILL_CENTER
                implementationMode = PreviewView.ImplementationMode.COMPATIBLE
                this.controller = controller
            }
        },
        modifier = modifier,
    )
}

private tailrec fun Context.findActivity(): Activity? = when (this) {
    is Activity -> this
    is ContextWrapper -> baseContext.findActivity()
    else -> null
}

@Composable
private fun CameraFallback(modifier: Modifier = Modifier) {
    Canvas(modifier.background(CameraScrim)) {
        drawRect(
            brush = Brush.verticalGradient(
                listOf(Color(0xFF132A58), CameraScrim),
            ),
        )
        repeat(10) { index ->
            val y = size.height * index / 10f
            drawLine(
                color = Color.White.copy(alpha = 0.07f),
                start = Offset(0f, y),
                end = Offset(size.width, y + size.width * 0.14f),
                strokeWidth = 2f,
            )
        }
    }
}

@Composable
private fun PrismaticRouteRibbon(
    headingDelta: Float,
    modifier: Modifier = Modifier,
) {
    Canvas(modifier) {
        val turn = headingDelta.coerceIn(-65f, 65f)
        val horizonY = size.height * 0.36f
        val bottomY = size.height * 0.88f
        val pivot = Offset(size.width / 2f, size.height * 0.72f)
        rotate(turn * 0.46f, pivot) {
            repeat(7) { index ->
                val progress = index / 6f
                val y = bottomY - (bottomY - horizonY) * progress
                val width = size.width * (0.34f - progress * 0.25f)
                val height = width * 0.48f
                val centreX = size.width / 2f + turn / 65f * progress * size.width * 0.24f
                val alpha = 0.92f - progress * 0.46f
                val prism = prismPath(centreX, y, width, height)
                drawPath(
                    prism,
                    Color.Black.copy(alpha = alpha * 0.34f),
                    style = Stroke(width = max(8f, width * 0.11f)),
                )
                drawPath(
                    prism,
                    if (index % 2 == 0) RouteBlue.copy(alpha = alpha) else RouteViolet.copy(alpha = alpha),
                    style = Stroke(width = max(5f, width * 0.075f)),
                )
                drawPath(
                    prism,
                    Color.White.copy(alpha = alpha * 0.8f),
                    style = Stroke(width = max(1.5f, width * 0.016f)),
                )
            }
        }
    }
}

private fun prismPath(centreX: Float, y: Float, width: Float, height: Float): Path = Path().apply {
    moveTo(centreX - width / 2f, y + height / 2f)
    lineTo(centreX, y - height / 2f)
    lineTo(centreX + width / 2f, y + height / 2f)
}
