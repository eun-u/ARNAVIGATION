package kr.co.navi.mobility.ai.offline

import java.nio.ByteBuffer
import kotlinx.coroutines.runBlocking
import kr.co.navi.mobility.ai.PerceptionEngine
import kr.co.navi.mobility.guidance.contract.DetectedRegion
import kr.co.navi.mobility.guidance.contract.FramePlane
import kr.co.navi.mobility.guidance.contract.FrameStamp
import kr.co.navi.mobility.guidance.contract.NormalizedRegion
import kr.co.navi.mobility.guidance.contract.PerceptionFrameLease
import kr.co.navi.mobility.guidance.contract.PerceptionResult
import kr.co.navi.mobility.guidance.contract.PixelFormat
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class OfflineReplayHarnessTest {
    @Test
    fun `aggregates detection and latency metrics deterministically`() = runBlocking {
        val frames = listOf(fakeFrame(1), fakeFrame(2))
        val cases = listOf(
            case(
                id = "frame-1",
                frame = frames[0],
                truth("obstacle", box(0f, 0f, 0.5f, 0.5f)),
                truth("pedestrian", box(0.5f, 0.5f, 1f, 1f)),
            ),
            case(
                id = "frame-2",
                frame = frames[1],
                truth("obstacle", box(0f, 0f, 0.2f, 0.2f)),
            ),
        )
        val engine = resultEngine(
            mapOf(
                1L to result(
                    frames[0].stamp,
                    latency = 10,
                    detection("obstacle", box(0f, 0f, 0.5f, 0.5f)),
                    detection("bicycle", box(0.5f, 0f, 1f, 0.5f)),
                ),
                2L to result(
                    frames[1].stamp,
                    latency = 30,
                    detection("obstacle", box(0.8f, 0.8f, 1f, 1f)),
                ),
            ),
        )

        val report = OfflineReplayHarness(iouThreshold = 0.5f).evaluate(cases, engine)

        assertEquals(2, report.frameCount)
        assertEquals(2, report.evaluatedFrameCount)
        assertTrue(report.failedFrames.isEmpty())
        assertEquals(setOf("fake-v1"), report.modelVersions)
        assertEquals(DetectionMetrics(1, 2, 2), report.overall)
        assertEquals(DetectionMetrics(1, 1, 1), report.byLabel["obstacle"])
        assertEquals(DetectionMetrics(0, 1, 0), report.byLabel["bicycle"])
        assertEquals(DetectionMetrics(0, 0, 1), report.byLabel["pedestrian"])
        assertEquals(2, report.latency.sampleCount)
        assertEquals(20.0, report.latency.meanMillis, 0.001)
        assertEquals(10, report.latency.p50Millis)
        assertEquals(30, report.latency.p95Millis)
        assertTrue(frames.all { it.closed })
    }

    @Test
    fun `records engine failures and always closes leases`() = runBlocking {
        val frame = fakeFrame(7)
        val engine = object : PerceptionEngine {
            override suspend fun analyze(frame: PerceptionFrameLease): PerceptionResult {
                error("inference failed")
            }

            override fun close() = Unit
        }

        val report = OfflineReplayHarness().evaluate(
            cases = listOf(case("broken-frame", frame, truth("obstacle", box(0f, 0f, 1f, 1f)))),
            engine = engine,
        )

        assertTrue(frame.closed)
        assertEquals(0, report.evaluatedFrameCount)
        assertEquals(1, report.failedFrames.size)
        assertEquals(DetectionMetrics(0, 0, 1), report.overall)
    }

    @Test
    fun `rejects a result from a different frame`() = runBlocking {
        val frame = fakeFrame(9)
        val engine = resultEngine(
            mapOf(9L to result(FrameStamp(10, 10_000), latency = 5)),
        )

        val report = OfflineReplayHarness().evaluate(
            cases = listOf(case("wrong-stamp", frame, truth("obstacle", box(0f, 0f, 1f, 1f)))),
            engine = engine,
        )

        assertEquals(0, report.evaluatedFrameCount)
        assertEquals(1, report.failedFrames.size)
        assertEquals(0, report.latency.sampleCount)
        assertEquals(DetectionMetrics(0, 0, 1), report.overall)
        assertTrue(frame.closed)
    }

    private fun case(
        id: String,
        frame: FakeFrameLease,
        vararg expected: GroundTruthRegion,
    ) = OfflineFrameCase(id, openFrame = { frame }, expected = expected.toList())

    private fun truth(label: String, bounds: NormalizedRegion) = GroundTruthRegion(label, bounds)

    private fun detection(label: String, bounds: NormalizedRegion) = DetectedRegion(
        label = label,
        confidence = 0.9f,
        bounds = bounds,
    )

    private fun result(
        stamp: FrameStamp,
        latency: Long,
        vararg detections: DetectedRegion,
    ) = PerceptionResult(stamp, "fake-v1", latency, detections.toList())

    private fun resultEngine(results: Map<Long, PerceptionResult>) = object : PerceptionEngine {
        override suspend fun analyze(frame: PerceptionFrameLease): PerceptionResult =
            requireNotNull(results[frame.stamp.frameId])

        override fun close() = Unit
    }

    private fun fakeFrame(frameId: Long) = FakeFrameLease(FrameStamp(frameId, frameId * 1_000))

    private fun box(left: Float, top: Float, right: Float, bottom: Float) =
        NormalizedRegion(left, top, right, bottom)

    private class FakeFrameLease(
        override val stamp: FrameStamp,
    ) : PerceptionFrameLease {
        var closed: Boolean = false
            private set

        override val width: Int = 1
        override val height: Int = 1
        override val rotationDegrees: Int = 0
        override val pixelFormat: PixelFormat = PixelFormat.RGBA_8888
        override val planes: List<FramePlane> = listOf(FramePlane(ByteBuffer.allocate(4), 4, 4))

        override fun close() {
            check(!closed) { "frame was closed twice" }
            closed = true
        }
    }
}
