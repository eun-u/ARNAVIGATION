package kr.co.navi.mobility.ar

import java.io.BufferedWriter
import java.io.File
import java.util.Locale

internal data class ArTelemetrySample(
    val elapsedRealtimeMillis: Long,
    val trackingQuality: String,
    val depthActive: Boolean,
    val routeAligned: Boolean,
    val trackingLossCount: Int,
    val unexpectedTrackingLossCount: Int,
    val expectedTransitionLossCount: Int,
    val lastRecoveryMillis: Long?,
    val frameTimeMillis: Float,
    val message: String?,
    val trackingFailureReason: String?,
    val lifecycleState: String,
    val displayInteractive: Boolean,
    val sessionGeneration: Int,
    val datasetMode: String,
    val transitionReason: String,
    val expectedSessionTransition: Boolean,
)

internal class ArSessionMetricsRecorder {
    private var writer: BufferedWriter? = null

    fun start(file: File) {
        stop()
        file.parentFile?.mkdirs()
        writer = file.bufferedWriter().also {
            it.appendLine(
                "elapsed_realtime_ms,tracking_quality,depth_active,route_aligned," +
                    "tracking_loss_count,last_recovery_ms,frame_time_ms,message," +
                    "tracking_failure_reason,lifecycle_state,display_interactive," +
                    "session_generation,dataset_mode,transition_reason," +
                    "expected_session_transition,unexpected_tracking_loss_count," +
                    "expected_transition_loss_count",
            )
            it.flush()
        }
    }

    fun append(sample: ArTelemetrySample) {
        writer?.apply {
            append(sample.elapsedRealtimeMillis.toString())
            append(',')
            append(sample.trackingQuality.csv())
            append(',')
            append(sample.depthActive.toString())
            append(',')
            append(sample.routeAligned.toString())
            append(',')
            append(sample.trackingLossCount.toString())
            append(',')
            append(sample.lastRecoveryMillis?.toString().orEmpty())
            append(',')
            append(String.format(Locale.US, "%.3f", sample.frameTimeMillis))
            append(',')
            append(sample.message.orEmpty().csv())
            append(',')
            append(sample.trackingFailureReason.orEmpty().csv())
            append(',')
            append(sample.lifecycleState.csv())
            append(',')
            append(sample.displayInteractive.toString())
            append(',')
            append(sample.sessionGeneration.toString())
            append(',')
            append(sample.datasetMode.csv())
            append(',')
            append(sample.transitionReason.csv())
            append(',')
            append(sample.expectedSessionTransition.toString())
            append(',')
            append(sample.unexpectedTrackingLossCount.toString())
            append(',')
            append(sample.expectedTransitionLossCount.toString())
            appendLine()
            flush()
        }
    }

    fun stop() {
        writer?.runCatching { flush() }
        writer?.runCatching { close() }
        writer = null
    }

    private fun String.csv(): String = "\"${replace("\"", "\"\"")}\""
}
