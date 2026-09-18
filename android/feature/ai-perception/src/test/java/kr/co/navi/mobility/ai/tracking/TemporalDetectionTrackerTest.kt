package kr.co.navi.mobility.ai.tracking

import kr.co.navi.mobility.guidance.contract.DetectedRegion
import kr.co.navi.mobility.guidance.contract.FrameStamp
import kr.co.navi.mobility.guidance.contract.NormalizedRegion
import kr.co.navi.mobility.guidance.contract.PerceptionResult
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertThrows
import org.junit.Test

class TemporalDetectionTrackerTest {
    @Test
    fun `keeps an ID for overlapping detections of the same label`() {
        val tracker = TemporalDetectionTracker(minimumIou = 0.3f)

        val first = tracker.update(result(1, detection("person", box(0.1f, 0.1f, 0.4f, 0.6f))))
        val second = tracker.update(result(2, detection("person", box(0.12f, 0.1f, 0.42f, 0.6f))))

        assertEquals("track-1", first.detections.single().trackId)
        assertEquals("track-1", second.detections.single().trackId)
    }

    @Test
    fun `expires a track after the configured missed frame count`() {
        val tracker = TemporalDetectionTracker(maximumMissedFrames = 1)
        val first = tracker.update(result(1, detection("car", box(0f, 0f, 0.5f, 0.5f))))
        tracker.update(result(2))
        tracker.update(result(3))
        val fourth = tracker.update(result(4, detection("car", box(0f, 0f, 0.5f, 0.5f))))

        assertNotEquals(first.detections.single().trackId, fourth.detections.single().trackId)
        assertEquals("track-2", fourth.detections.single().trackId)
    }

    @Test
    fun `rejects replay frames that move backwards`() {
        val tracker = TemporalDetectionTracker()
        tracker.update(result(2))

        assertThrows(IllegalArgumentException::class.java) {
            tracker.update(result(1))
        }
    }

    private fun result(frameId: Long, vararg detections: DetectedRegion) = PerceptionResult(
        stamp = FrameStamp(frameId, frameId * 1_000),
        modelVersion = "fixture-v1",
        inferenceMillis = 1,
        detections = detections.toList(),
    )

    private fun detection(label: String, bounds: NormalizedRegion) = DetectedRegion(
        label = label,
        confidence = 0.9f,
        bounds = bounds,
    )

    private fun box(left: Float, top: Float, right: Float, bottom: Float) =
        NormalizedRegion(left, top, right, bottom)
}
