package kr.co.navi.mobility.guidance.fusion

import kr.co.navi.mobility.guidance.contract.FrameStamp
import kr.co.navi.mobility.guidance.contract.PerceptionResult
import kr.co.navi.mobility.guidance.contract.SpatialFrameContext
import kr.co.navi.mobility.guidance.contract.TrackingQuality
import org.junit.Assert.assertThrows
import org.junit.Test

class GuidanceFusionTest {
    @Test
    fun `fusion rejects perception from a different frame`() {
        val spatial = SpatialFrameContext(
            stamp = FrameStamp(frameId = 1, timestampNanos = 100),
            localPose = null,
            geoCoordinate = null,
            accuracy = null,
            trackingQuality = TrackingQuality.WAITING,
            depthAvailable = false,
        )
        val perception = PerceptionResult(
            stamp = FrameStamp(frameId = 2, timestampNanos = 200),
            modelVersion = "test",
            inferenceMillis = 1,
            detections = emptyList(),
        )

        assertThrows(IllegalArgumentException::class.java) {
            NoOpGuidanceFusion().fuse(spatial, perception)
        }
    }
}
