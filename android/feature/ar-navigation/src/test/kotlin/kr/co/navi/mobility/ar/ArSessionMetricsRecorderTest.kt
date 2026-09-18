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
                lastRecoveryMillis = 340L,
                frameTimeMillis = 8.25f,
                message = "stable,local",
            ),
        )
        recorder.stop()

        val lines = file.readLines()
        assertEquals(2, lines.size)
        assertTrue(lines.first().startsWith("elapsed_realtime_ms"))
        assertTrue(lines.last().contains("8.250"))
        assertTrue(lines.last().contains("\"stable,local\""))
        assertTrue(file.delete())
        assertTrue(directory.delete())
    }
}
