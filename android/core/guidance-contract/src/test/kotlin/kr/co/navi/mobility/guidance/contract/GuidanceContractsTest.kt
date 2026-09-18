package kr.co.navi.mobility.guidance.contract

import org.junit.Assert.assertThrows
import org.junit.Test

class GuidanceContractsTest {
    @Test
    fun `normalized regions reject coordinates outside the image`() {
        assertThrows(IllegalArgumentException::class.java) {
            NormalizedRegion(left = -0.1f, top = 0f, right = 0.5f, bottom = 0.5f)
        }
    }

    @Test
    fun `detections reject confidence outside zero to one`() {
        assertThrows(IllegalArgumentException::class.java) {
            DetectedRegion(
                label = "obstacle",
                confidence = 1.1f,
                bounds = NormalizedRegion(0f, 0f, 1f, 1f),
            )
        }
    }

    @Test
    fun `perception result requires model provenance and non-negative latency`() {
        assertThrows(IllegalArgumentException::class.java) {
            PerceptionResult(
                stamp = FrameStamp(1, 1),
                modelVersion = "",
                inferenceMillis = 0,
                detections = emptyList(),
            )
        }
        assertThrows(IllegalArgumentException::class.java) {
            PerceptionResult(
                stamp = FrameStamp(1, 1),
                modelVersion = "fixture-v1",
                inferenceMillis = -1,
                detections = emptyList(),
            )
        }
    }
}
