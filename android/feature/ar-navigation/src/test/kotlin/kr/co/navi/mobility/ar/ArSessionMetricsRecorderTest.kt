package kr.co.navi.mobility.ar

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.nio.file.Files

class ArSessionMetricsRecorderTest {
    @Test
    fun `writes a bounded telemetry row and closes the file`() {
        val directory = Files.createTempDirectory("navi-ar-metrics").toFile()
        val file = directory.resolve("session.csv")
        val recorder = ArSessionMetricsRecorder()

        recorder.start(file)
        recorder.append(
            ArTelemetrySample(
                elapsedRealtimeMillis = 1200L,
                trackingQuality = "TRACKING",
                depthActive = true,
                routeAligned = false,
                trackingLossCount = 2,
                unexpectedTrackingLossCount = 1,
                expectedTransitionLossCount = 1,
                lastRecoveryMillis = 340L,
                frameTimeMillis = 8.25f,
                message = "stable,local",
                trackingFailureReason = "EXCESSIVE_MOTION",
                lifecycleState = "RESUMED",
                displayInteractive = true,
                sessionGeneration = 3,
                datasetMode = "PLAYBACK",
                transitionReason = "PLAYBACK_START",
                expectedSessionTransition = false,
            ),
        )
        recorder.stop()

        val lines = file.readLines()
        assertEquals(2, lines.size)
        assertTrue(lines.first().startsWith("elapsed_realtime_ms"))
        assertTrue(lines.first().contains("tracking_failure_reason"))
        assertTrue(lines.first().contains("unexpected_tracking_loss_count"))
        assertTrue(lines.last().contains("8.250"))
        assertTrue(lines.last().contains("\"stable,local\""))
        assertTrue(lines.last().contains("\"EXCESSIVE_MOTION\""))
        assertTrue(lines.last().endsWith(",1,1"))
        assertTrue(file.delete())
        assertTrue(directory.delete())
    }
}
