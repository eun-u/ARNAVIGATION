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
    val lastRecoveryMillis: Long?,
    val frameTimeMillis: Float,
    val message: String?,
)

internal class ArSessionMetricsRecorder {
    private var writer: BufferedWriter? = null

    fun start(file: File) {
        stop()
        file.parentFile?.mkdirs()
        writer = file.bufferedWriter().also {
            it.appendLine(
                "elapsed_realtime_ms,tracking_quality,depth_active,route_aligned," +
                    "tracking_loss_count,last_recovery_ms,frame_time_ms,message",
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
