package kr.co.navi.mobility.ar

import android.app.Activity
import android.content.Context
import android.opengl.GLES11Ext
import android.opengl.GLES20
import android.opengl.GLSurfaceView
import android.opengl.Matrix
import android.os.SystemClock
import android.view.Surface
import com.google.ar.core.ArCoreApk
import com.google.ar.core.Config
import com.google.ar.core.Coordinates2d
import com.google.ar.core.Frame
import com.google.ar.core.Pose
import com.google.ar.core.Session
import com.google.ar.core.TrackingState
import com.google.ar.core.exceptions.CameraNotAvailableException
import com.google.ar.core.exceptions.NotYetAvailableException
import com.google.ar.core.exceptions.UnavailableException
import kr.co.navi.mobility.guidance.contract.GeoCoordinate
import kr.co.navi.mobility.guidance.contract.TrackingQuality
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.nio.FloatBuffer
import javax.microedition.khronos.egl.EGLConfig
import javax.microedition.khronos.opengles.GL10
import kotlin.math.PI
import kotlin.math.abs
import kotlin.math.cos
import kotlin.math.hypot
import kotlin.math.sin

/**
 * Owns the ARCore camera session. CameraX must never be bound while this view is active.
 */
class ArCoreNavigationView(
    context: Context,
    private val activity: Activity,
    onStateChanged: (ArRuntimeState) -> Unit,
) : GLSurfaceView(context) {
    private val renderer = ArCoreRenderer(::onFrameTelemetry)
    private var stateListener = onStateChanged
    private var session: Session? = null
    private var installRequested = false
    private var resumed = false
    private var routeAligned = false
    private var depthSupported = false
    private var lastState = ArRuntimeState()
    private var lastGuidanceInput: GuidanceInput? = null

    init {
        setEGLContextClientVersion(2)
        setEGLConfigChooser(8, 8, 8, 8, 16, 0)
        setRenderer(renderer)
        renderMode = RENDERMODE_CONTINUOUSLY
        preserveEGLContextOnPause = true
        publish(lastState)
    }

    fun setStateListener(listener: (ArRuntimeState) -> Unit) {
        stateListener = listener
        publish(lastState)
    }

    fun updateGuidance(
        route: List<GeoCoordinate>,
        user: GeoCoordinate?,
        locationAccuracyMeters: Float?,
        headingDegrees: Float?,
    ) {
        val input = GuidanceInput(route, user, locationAccuracyMeters, headingDegrees)
        if (input == lastGuidanceInput) return
        lastGuidanceInput = input

        val path = if (user != null && headingDegrees != null) {
            buildForwardGuidancePath(
                route = route,
                user = user,
                locationAccuracyMeters = locationAccuracyMeters,
            )
        } else {
            null
        }
        routeAligned = path != null
        queueEvent { renderer.setGuidance(path, headingDegrees) }
        publish(lastState.copy(routeAligned = routeAligned))
    }

    fun resumeSession() {
        if (resumed) return
        val current = session ?: createSession() ?: return
        try {
            current.resume()
            renderer.session = current
            super.onResume()
            resumed = true
        } catch (error: CameraNotAvailableException) {
            closeSession()
            publishUnavailable("ARCore가 후면 카메라를 열지 못했습니다.")
        }
    }

    fun pauseSession() {
        if (!resumed) return
        super.onPause()
        session?.pause()
        resumed = false
    }

    fun closeSession() {
        pauseSession()
        renderer.session = null
        session?.close()
        session = null
    }

    private fun createSession(): Session? {
        publish(lastState.copy(mode = ArRuntimeMode.CHECKING, message = "ARCore 지원 상태 확인 중"))
        return try {
            when (ArCoreApk.getInstance().requestInstall(activity, !installRequested)) {
                ArCoreApk.InstallStatus.INSTALL_REQUESTED -> {
                    installRequested = true
                    publish(
                        lastState.copy(
                            mode = ArRuntimeMode.INSTALL_REQUIRED,
                            trackingQuality = TrackingQuality.WAITING,
                            message = "Google Play Services for AR 설치 또는 업데이트 필요",
                        ),
                    )
                    null
                }

                ArCoreApk.InstallStatus.INSTALLED -> {
                    val created = Session(activity)
                    val config = created.config.apply {
                        focusMode = Config.FocusMode.AUTO
                        planeFindingMode = Config.PlaneFindingMode.HORIZONTAL_AND_VERTICAL
                        updateMode = Config.UpdateMode.LATEST_CAMERA_IMAGE
                    }
                    depthSupported = created.isDepthModeSupported(Config.DepthMode.AUTOMATIC)
                    config.depthMode = if (depthSupported) {
                        Config.DepthMode.AUTOMATIC
                    } else {
                        Config.DepthMode.DISABLED
                    }
                    created.configure(config)
                    session = created
                    publish(
                        lastState.copy(
                            mode = ArRuntimeMode.DEGRADED,
                            trackingQuality = TrackingQuality.WAITING,
                            depthSupported = depthSupported,
                            routeAligned = routeAligned,
                            message = "ARCore가 주변 공간을 인식하는 중",
                        ),
                    )
                    created
                }
            }
        } catch (error: UnavailableException) {
            publishUnavailable(error.toUserMessage())
            null
        }
    }

    private fun onFrameTelemetry(telemetry: FrameTelemetry) {
        post {
            val mode = when (telemetry.trackingQuality) {
                TrackingQuality.TRACKING -> ArRuntimeMode.TRACKING
                TrackingQuality.UNAVAILABLE -> ArRuntimeMode.UNAVAILABLE
                TrackingQuality.WAITING,
                TrackingQuality.DEGRADED,
                -> ArRuntimeMode.DEGRADED
            }
            publish(
                ArRuntimeState(
                    mode = mode,
                    trackingQuality = telemetry.trackingQuality,
                    depthSupported = depthSupported,
                    depthActive = telemetry.depthActive,
                    routeAligned = routeAligned,
                    trackingLossCount = telemetry.trackingLossCount,
                    lastRecoveryMillis = telemetry.lastRecoveryMillis,
                    frameTimeMillis = telemetry.frameTimeMillis,
                    message = telemetry.message,
                ),
            )
        }
    }

    private fun publishUnavailable(message: String) {
        publish(
            lastState.copy(
                mode = ArRuntimeMode.UNAVAILABLE,
                trackingQuality = TrackingQuality.UNAVAILABLE,
                message = message,
            ),
        )
    }

    private fun publish(state: ArRuntimeState) {
        if (state == lastState && state != ArRuntimeState()) return
        lastState = state
        if (android.os.Looper.myLooper() == android.os.Looper.getMainLooper()) {
            stateListener(state)
        } else {
            post { stateListener(state) }
        }
    }

    private data class GuidanceInput(
        val route: List<GeoCoordinate>,
        val user: GeoCoordinate?,
        val accuracyMeters: Float?,
        val headingDegrees: Float?,
    )
}

private data class FrameTelemetry(
    val trackingQuality: TrackingQuality,
    val depthActive: Boolean,
    val trackingLossCount: Int,
    val lastRecoveryMillis: Long?,
    val frameTimeMillis: Float,
    val message: String?,
)

private class ArCoreRenderer(
    private val onTelemetry: (FrameTelemetry) -> Unit,
) : GLSurfaceView.Renderer {
    @Volatile
    var session: Session? = null

    private val cameraRenderer = CameraBackgroundRenderer()
    private val ribbonRenderer = RouteRibbonRenderer()
    private var textureSession: Session? = null
    private var viewportWidth = 1
    private var viewportHeight = 1
    private var wasTracking = false
    private var trackingLossStartedAt: Long? = null
    private var trackingLossCount = 0
    private var lastRecoveryMillis: Long? = null
    private var lastTelemetryAt = 0L

    fun setGuidance(path: ForwardGuidancePath?, headingDegrees: Float?) {
        ribbonRenderer.setGuidance(path, headingDegrees)
    }

    override fun onSurfaceCreated(gl: GL10?, config: EGLConfig?) {
        GLES20.glClearColor(0.03f, 0.08f, 0.18f, 1f)
        cameraRenderer.createOnGlThread()
        ribbonRenderer.createOnGlThread()
        textureSession = null
    }

    override fun onSurfaceChanged(gl: GL10?, width: Int, height: Int) {
        viewportWidth = width.coerceAtLeast(1)
        viewportHeight = height.coerceAtLeast(1)
        GLES20.glViewport(0, 0, viewportWidth, viewportHeight)
    }

    override fun onDrawFrame(gl: GL10?) {
        GLES20.glClear(GLES20.GL_COLOR_BUFFER_BIT or GLES20.GL_DEPTH_BUFFER_BIT)
        val activeSession = session ?: return
        if (textureSession !== activeSession) {
            activeSession.setCameraTextureName(cameraRenderer.textureId)
            textureSession = activeSession
        }

        activeSession.setDisplayGeometry(
            displayRotation(),
            viewportWidth,
            viewportHeight,
        )
        val frameStartedAt = System.nanoTime()
        val frame = try {
            activeSession.update()
        } catch (_: CameraNotAvailableException) {
            publishUnavailableTelemetry(frameStartedAt)
            return
        }

        cameraRenderer.draw(frame)
        val camera = frame.camera
        val tracking = camera.trackingState == TrackingState.TRACKING
        updateTrackingMetrics(tracking)
        val depthActive = if (tracking) frame.hasDepthImage() else false
        if (tracking) ribbonRenderer.draw(camera.pose, camera, frame)

        val now = SystemClock.elapsedRealtime()
        if (now - lastTelemetryAt >= TELEMETRY_INTERVAL_MILLIS || tracking != wasTracking) {
            lastTelemetryAt = now
            onTelemetry(
                FrameTelemetry(
                    trackingQuality = if (tracking) TrackingQuality.TRACKING else TrackingQuality.DEGRADED,
                    depthActive = depthActive,
                    trackingLossCount = trackingLossCount,
                    lastRecoveryMillis = lastRecoveryMillis,
                    frameTimeMillis = (System.nanoTime() - frameStartedAt) / 1_000_000f,
                    message = if (tracking) null else camera.trackingFailureReason.name,
                ),
            )
        }
        wasTracking = tracking
    }

    private fun updateTrackingMetrics(tracking: Boolean) {
        val now = SystemClock.elapsedRealtime()
        if (wasTracking && !tracking) {
            trackingLossCount += 1
            trackingLossStartedAt = now
        } else if (!wasTracking && tracking) {
            trackingLossStartedAt?.let { lastRecoveryMillis = now - it }
            trackingLossStartedAt = null
        }
    }

    private fun publishUnavailableTelemetry(frameStartedAt: Long) {
        onTelemetry(
            FrameTelemetry(
                trackingQuality = TrackingQuality.UNAVAILABLE,
                depthActive = false,
                trackingLossCount = trackingLossCount,
                lastRecoveryMillis = lastRecoveryMillis,
                frameTimeMillis = (System.nanoTime() - frameStartedAt) / 1_000_000f,
                message = "CAMERA_NOT_AVAILABLE",
            ),
        )
    }

    private fun displayRotation(): Int = when (android.content.res.Resources.getSystem().configuration.orientation) {
        android.content.res.Configuration.ORIENTATION_LANDSCAPE -> Surface.ROTATION_90
        else -> Surface.ROTATION_0
    }

    private fun Frame.hasDepthImage(): Boolean = try {
        acquireDepthImage16Bits().use { true }
    } catch (_: NotYetAvailableException) {
        false
    } catch (_: IllegalStateException) {
        false
    }

    private companion object {
        const val TELEMETRY_INTERVAL_MILLIS = 300L
    }
}

private class CameraBackgroundRenderer {
    var textureId: Int = 0
        private set

    private var program = 0
    private var positionAttribute = 0
    private var texCoordAttribute = 0
    private var textureUniform = 0
    private val quadCoordinates = floatBufferOf(
        -1f, -1f,
        1f, -1f,
        -1f, 1f,
        1f, 1f,
    )
    private val textureCoordinates = floatBufferOf(
        0f, 0f,
        1f, 0f,
        0f, 1f,
        1f, 1f,
    )

    fun createOnGlThread() {
        val textures = IntArray(1)
        GLES20.glGenTextures(1, textures, 0)
        textureId = textures[0]
        GLES20.glBindTexture(GLES11Ext.GL_TEXTURE_EXTERNAL_OES, textureId)
        GLES20.glTexParameteri(
            GLES11Ext.GL_TEXTURE_EXTERNAL_OES,
            GLES20.GL_TEXTURE_MIN_FILTER,
            GLES20.GL_LINEAR,
        )
        GLES20.glTexParameteri(
            GLES11Ext.GL_TEXTURE_EXTERNAL_OES,
            GLES20.GL_TEXTURE_MAG_FILTER,
            GLES20.GL_LINEAR,
        )
        GLES20.glTexParameteri(
            GLES11Ext.GL_TEXTURE_EXTERNAL_OES,
            GLES20.GL_TEXTURE_WRAP_S,
            GLES20.GL_CLAMP_TO_EDGE,
        )
        GLES20.glTexParameteri(
            GLES11Ext.GL_TEXTURE_EXTERNAL_OES,
            GLES20.GL_TEXTURE_WRAP_T,
            GLES20.GL_CLAMP_TO_EDGE,
        )

        program = createProgram(CAMERA_VERTEX_SHADER, CAMERA_FRAGMENT_SHADER)
        positionAttribute = GLES20.glGetAttribLocation(program, "a_Position")
        texCoordAttribute = GLES20.glGetAttribLocation(program, "a_TexCoord")
        textureUniform = GLES20.glGetUniformLocation(program, "u_Texture")
    }

    fun draw(frame: Frame) {
        if (frame.timestamp == 0L) return
        if (frame.hasDisplayGeometryChanged()) {
            quadCoordinates.position(0)
            textureCoordinates.position(0)
            frame.transformCoordinates2d(
                Coordinates2d.OPENGL_NORMALIZED_DEVICE_COORDINATES,
                quadCoordinates,
                Coordinates2d.TEXTURE_NORMALIZED,
                textureCoordinates,
            )
        }

        GLES20.glDisable(GLES20.GL_DEPTH_TEST)
        GLES20.glDepthMask(false)
        GLES20.glUseProgram(program)
        GLES20.glActiveTexture(GLES20.GL_TEXTURE0)
        GLES20.glBindTexture(GLES11Ext.GL_TEXTURE_EXTERNAL_OES, textureId)
        GLES20.glUniform1i(textureUniform, 0)

        quadCoordinates.position(0)
        GLES20.glVertexAttribPointer(positionAttribute, 2, GLES20.GL_FLOAT, false, 0, quadCoordinates)
        GLES20.glEnableVertexAttribArray(positionAttribute)
        textureCoordinates.position(0)
        GLES20.glVertexAttribPointer(texCoordAttribute, 2, GLES20.GL_FLOAT, false, 0, textureCoordinates)
        GLES20.glEnableVertexAttribArray(texCoordAttribute)
        GLES20.glDrawArrays(GLES20.GL_TRIANGLE_STRIP, 0, 4)
        GLES20.glDisableVertexAttribArray(positionAttribute)
        GLES20.glDisableVertexAttribArray(texCoordAttribute)
        GLES20.glDepthMask(true)
    }

    private companion object {
        const val CAMERA_VERTEX_SHADER = """
            attribute vec4 a_Position;
            attribute vec2 a_TexCoord;
            varying vec2 v_TexCoord;
            void main() {
                gl_Position = a_Position;
                v_TexCoord = a_TexCoord;
            }
        """

        const val CAMERA_FRAGMENT_SHADER = """
            #extension GL_OES_EGL_image_external : require
            precision mediump float;
            uniform samplerExternalOES u_Texture;
            varying vec2 v_TexCoord;
            void main() {
                gl_FragColor = texture2D(u_Texture, v_TexCoord);
            }
        """
    }
}

private class RouteRibbonRenderer {
    private var program = 0
    private var positionAttribute = 0
    private var mvpUniform = 0
    private var colorUniform = 0
    private var guidance: ForwardGuidancePath? = null
    private var headingDegrees: Float? = null
    private var guidanceRevision = 0
    private var anchoredRevision = -1
    private var vertices: FloatBuffer? = null
    private var vertexCount = 0
    private val projection = FloatArray(16)
    private val view = FloatArray(16)
    private val mvp = FloatArray(16)

    fun createOnGlThread() {
        program = createProgram(RIBBON_VERTEX_SHADER, RIBBON_FRAGMENT_SHADER)
        positionAttribute = GLES20.glGetAttribLocation(program, "a_Position")
        mvpUniform = GLES20.glGetUniformLocation(program, "u_Mvp")
        colorUniform = GLES20.glGetUniformLocation(program, "u_Color")
        anchoredRevision = -1
    }

    fun setGuidance(path: ForwardGuidancePath?, heading: Float?) {
        guidance = path
        headingDegrees = heading
        guidanceRevision += 1
    }

    fun draw(cameraPose: Pose, camera: com.google.ar.core.Camera, frame: Frame) {
        if (anchoredRevision != guidanceRevision) {
            vertices = buildWorldRibbon(cameraPose, frame)
            vertexCount = (vertices?.capacity() ?: 0) / 3
            anchoredRevision = guidanceRevision
        }
        val activeVertices = vertices ?: return
        if (vertexCount < 4) return

        camera.getProjectionMatrix(projection, 0, 0.1f, 100f)
        camera.getViewMatrix(view, 0)
        Matrix.multiplyMM(mvp, 0, projection, 0, view, 0)

        GLES20.glEnable(GLES20.GL_DEPTH_TEST)
        GLES20.glEnable(GLES20.GL_BLEND)
        GLES20.glBlendFunc(GLES20.GL_SRC_ALPHA, GLES20.GL_ONE_MINUS_SRC_ALPHA)
        GLES20.glUseProgram(program)
        GLES20.glUniformMatrix4fv(mvpUniform, 1, false, mvp, 0)
        GLES20.glUniform4f(colorUniform, 0.16f, 0.39f, 0.96f, 0.82f)
        activeVertices.position(0)
        GLES20.glVertexAttribPointer(positionAttribute, 3, GLES20.GL_FLOAT, false, 0, activeVertices)
        GLES20.glEnableVertexAttribArray(positionAttribute)
        GLES20.glDrawArrays(GLES20.GL_TRIANGLE_STRIP, 0, vertexCount)
        GLES20.glDisableVertexAttribArray(positionAttribute)
        GLES20.glDisable(GLES20.GL_BLEND)
    }

    private fun buildWorldRibbon(cameraPose: Pose, frame: Frame): FloatBuffer? {
        val path = guidance ?: return null
        val heading = headingDegrees ?: return null
        if (path.points.size < 2) return null

        val cameraOrigin = cameraPose.translation
        val cameraRight = cameraPose.xAxis.horizontalNormalized() ?: return null
        val cameraForward = cameraPose.zAxis
            .map { -it }
            .toFloatArray()
            .horizontalNormalized() ?: return null
        val floorY = estimateFloorY(frame, cameraOrigin[1])
        val headingRadians = heading * PI.toFloat() / 180f
        val headingCos = cos(headingRadians)
        val headingSin = sin(headingRadians)

        val centres = path.points.map { point ->
            val rightMeters = point.eastMeters * headingCos - point.northMeters * headingSin
            val forwardMeters = point.eastMeters * headingSin + point.northMeters * headingCos
            WorldPoint(
                x = cameraOrigin[0] + cameraRight[0] * rightMeters + cameraForward[0] * forwardMeters,
                y = floorY,
                z = cameraOrigin[2] + cameraRight[2] * rightMeters + cameraForward[2] * forwardMeters,
            )
        }

        val values = ArrayList<Float>(centres.size * 6)
        centres.forEachIndexed { index, centre ->
            val before = centres[(index - 1).coerceAtLeast(0)]
            val after = centres[(index + 1).coerceAtMost(centres.lastIndex)]
            val dx = after.x - before.x
            val dz = after.z - before.z
            val length = hypot(dx, dz).coerceAtLeast(0.001f)
            val normalX = -dz / length * RIBBON_HALF_WIDTH_METERS
            val normalZ = dx / length * RIBBON_HALF_WIDTH_METERS
            values += centre.x + normalX
            values += centre.y
            values += centre.z + normalZ
            values += centre.x - normalX
            values += centre.y
            values += centre.z - normalZ
        }
        return floatBufferOf(*values.toFloatArray())
    }

    private fun estimateFloorY(frame: Frame, cameraY: Float): Float {
        val hits = frame.hitTest(0.5f, 0.72f)
        val groundHit = hits.firstOrNull { it.trackable.trackingState == TrackingState.TRACKING }
        return groundHit?.hitPose?.ty() ?: (cameraY - DEFAULT_CAMERA_HEIGHT_METERS)
    }

    private data class WorldPoint(val x: Float, val y: Float, val z: Float)

    private companion object {
        const val RIBBON_HALF_WIDTH_METERS = 0.28f
        const val DEFAULT_CAMERA_HEIGHT_METERS = 1.35f

        const val RIBBON_VERTEX_SHADER = """
            uniform mat4 u_Mvp;
            attribute vec4 a_Position;
            void main() {
                gl_Position = u_Mvp * a_Position;
            }
        """

        const val RIBBON_FRAGMENT_SHADER = """
            precision mediump float;
            uniform vec4 u_Color;
            void main() {
                gl_FragColor = u_Color;
            }
        """
    }
}

private fun FloatArray.horizontalNormalized(): FloatArray? {
    if (size < 3) return null
    val length = hypot(this[0], this[2])
    if (length < 0.001f) return null
    return floatArrayOf(this[0] / length, 0f, this[2] / length)
}

private fun floatBufferOf(vararg values: Float): FloatBuffer =
    ByteBuffer.allocateDirect(values.size * Float.SIZE_BYTES)
        .order(ByteOrder.nativeOrder())
        .asFloatBuffer()
        .apply {
            put(values)
            position(0)
        }

private fun createProgram(vertexSource: String, fragmentSource: String): Int {
    val vertexShader = compileShader(GLES20.GL_VERTEX_SHADER, vertexSource)
    val fragmentShader = compileShader(GLES20.GL_FRAGMENT_SHADER, fragmentSource)
    return GLES20.glCreateProgram().also { program ->
        GLES20.glAttachShader(program, vertexShader)
        GLES20.glAttachShader(program, fragmentShader)
        GLES20.glLinkProgram(program)
        val status = IntArray(1)
        GLES20.glGetProgramiv(program, GLES20.GL_LINK_STATUS, status, 0)
        check(status[0] == GLES20.GL_TRUE) { "OpenGL program link failed: ${GLES20.glGetProgramInfoLog(program)}" }
        GLES20.glDeleteShader(vertexShader)
        GLES20.glDeleteShader(fragmentShader)
    }
}

private fun compileShader(type: Int, source: String): Int = GLES20.glCreateShader(type).also { shader ->
    GLES20.glShaderSource(shader, source)
    GLES20.glCompileShader(shader)
    val status = IntArray(1)
    GLES20.glGetShaderiv(shader, GLES20.GL_COMPILE_STATUS, status, 0)
    check(status[0] == GLES20.GL_TRUE) { "OpenGL shader compile failed: ${GLES20.glGetShaderInfoLog(shader)}" }
}

private fun UnavailableException.toUserMessage(): String = when (this) {
    is com.google.ar.core.exceptions.UnavailableDeviceNotCompatibleException -> "이 기기는 ARCore를 지원하지 않습니다."
    is com.google.ar.core.exceptions.UnavailableArcoreNotInstalledException -> "Google Play Services for AR이 설치되지 않았습니다."
    is com.google.ar.core.exceptions.UnavailableApkTooOldException -> "Google Play Services for AR 업데이트가 필요합니다."
    is com.google.ar.core.exceptions.UnavailableSdkTooOldException -> "앱의 ARCore SDK 업데이트가 필요합니다."
    is com.google.ar.core.exceptions.UnavailableUserDeclinedInstallationException -> "ARCore 설치가 취소되었습니다."
    else -> "ARCore 세션을 시작할 수 없습니다."
}
