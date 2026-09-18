package kr.co.navi.mobility.ai.offline

import java.io.File
import java.nio.ByteBuffer
import java.security.MessageDigest
import kotlin.io.path.createTempDirectory
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
import org.junit.Assert.assertFalse
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Test

class OfflineDatasetPipelineTest {
    @Test
    fun `manifest pipeline writes deterministic json and csv reports`() = runBlocking {
        val directory = createTempDirectory("navi-ai-offline-").toFile()
        try {
            val manifest = File(directory, "manifest.json").apply {
                writeText(
                    """
                    {
                      "schema_version": 1,
                      "dataset_id": "tiny,fixture",
                      "frames": [
                        {
                          "case_id": "frame-001",
                          "image_path": "frames/001.png",
                          "timestamp_nanos": 1000,
                          "annotations": [
                            {"label":"obstacle","left":0.1,"top":0.1,"right":0.9,"bottom":0.9}
                          ]
                        }
                      ]
                    }
                    """.trimIndent(),
                )
            }
            val decoder = OfflineFrameDecoder { source, stamp, rotation ->
                assertTrue(source is OfflineFrameSource.Image)
                assertEquals(File(directory, "frames/001.png").canonicalFile, source.file)
                TestFrameLease(stamp, rotation)
            }
            val engine = object : PerceptionEngine {
                override suspend fun analyze(frame: PerceptionFrameLease) = PerceptionResult(
                    stamp = frame.stamp,
                    modelVersion = "fixture-v1",
                    inferenceMillis = 12,
                    detections = listOf(
                        DetectedRegion(
                            label = "obstacle",
                            confidence = 0.8f,
                            bounds = NormalizedRegion(0.1f, 0.1f, 0.9f, 0.9f),
                        ),
                    ),
                )

                override fun close() = Unit
            }
            val output = File(directory, "reports")

            val artifacts = OfflineEvaluationRunner(
                loader = ManifestOfflineDatasetLoader(decoder),
            ).run(
                manifestFile = manifest,
                outputDirectory = output,
                engine = engine,
                regressionPolicy = OfflineRegressionPolicy(
                    minimumOverallPrecision = 1.0,
                    minimumOverallRecall = 1.0,
                    minimumRecallByLabel = mapOf("obstacle" to 1.0),
                    maximumP95LatencyMillis = 20,
                ),
            )

            assertEquals(DetectionMetrics(1, 0, 0), artifacts.report.evaluation.overall)
            assertTrue(requireNotNull(artifacts.report.regression).passed)
            assertTrue(artifacts.jsonFile.isFile)
            assertTrue(artifacts.csvFile.isFile)
            assertTrue(artifacts.framesCsvFile.isFile)
            val json = artifacts.jsonFile.readText()
            assertTrue(json.contains("\"datasetId\": \"tiny,fixture\""))
            assertTrue(json.contains("\"passed\": true"))
            assertTrue(json.contains("\"precision\": 1.0"))
            val csv = artifacts.csvFile.readText()
            assertTrue(csv.contains("\"tiny,fixture\",overall"))
            assertTrue(csv.contains(",1,0,0,1.0,1.0,1.0,"))
            assertTrue(artifacts.framesCsvFile.readText().contains("frame-001,success"))
        } finally {
            directory.deleteRecursively()
        }
    }

    @Test
    fun `manifest rejects paths outside its dataset directory`() {
        val directory = createTempDirectory("navi-ai-path-").toFile()
        try {
            val manifest = File(directory, "manifest.json").apply {
                writeText(
                    """
                    {
                      "schema_version": 1,
                      "dataset_id": "unsafe",
                      "frames": [{
                        "case_id": "escape",
                        "image_path": "../secret.png",
                        "timestamp_nanos": 1
                      }]
                    }
                    """.trimIndent(),
                )
            }

            assertThrows(IllegalArgumentException::class.java) {
                ManifestOfflineDatasetLoader(
                    decoder = OfflineFrameDecoder { _, _, _ -> error("must not decode") },
                ).load(manifest)
            }
        } finally {
            directory.deleteRecursively()
        }
    }

    @Test
    fun `manifest exposes an exact video frame source`() {
        val directory = createTempDirectory("navi-ai-video-").toFile()
        try {
            val manifest = File(directory, "manifest.json").apply {
                writeText(
                    """
                    {
                      "schema_version": 1,
                      "dataset_id": "video-fixture",
                      "frames": [{
                        "case_id": "video-1500",
                        "video_path": "walk.mp4",
                        "video_position_ms": 1500,
                        "timestamp_nanos": 1500000000
                      }]
                    }
                    """.trimIndent(),
                )
            }
            val decoder = OfflineFrameDecoder { source, stamp, rotation ->
                assertTrue(source is OfflineFrameSource.Video)
                source as OfflineFrameSource.Video
                assertEquals(1500L, source.positionMillis)
                assertEquals(File(directory, "walk.mp4").canonicalFile, source.file)
                TestFrameLease(stamp, rotation)
            }

            val dataset = ManifestOfflineDatasetLoader(decoder).load(manifest)
            dataset.cases.single().openFrame().close()
        } finally {
            directory.deleteRecursively()
        }
    }

    @Test
    fun `source recording hashes are enforced before decoding`() {
        val directory = createTempDirectory("navi-ai-provenance-").toFile()
        try {
            val video = File(directory, "walk.mp4").apply { writeBytes(byteArrayOf(1, 2, 3)) }
            val telemetry = File(directory, "walk.csv").apply { writeText("fixture") }
            val manifest = File(directory, "manifest.json").apply {
                writeText(
                    """
                    {
                      "schema_version": 1,
                      "dataset_id": "provenance-fixture",
                      "source_recording": {
                        "video_path": "walk.mp4",
                        "telemetry_path": "walk.csv",
                        "video_sha256": "${video.sha256()}",
                        "telemetry_sha256": "${telemetry.sha256()}",
                        "telemetry_origin_elapsed_realtime_ms": 1,
                        "duration_ms": 100,
                        "sample_interval_ms": 100,
                        "sync_strategy": "fixture",
                        "estimated_sync_error_ms": 10
                      },
                      "frames": [{
                        "case_id": "video-100",
                        "video_path": "walk.mp4",
                        "video_position_ms": 100,
                        "timestamp_nanos": 100000000
                      }]
                    }
                    """.trimIndent(),
                )
            }
            val loader = ManifestOfflineDatasetLoader(
                decoder = OfflineFrameDecoder { _, stamp, rotation -> TestFrameLease(stamp, rotation) },
            )

            assertEquals("provenance-fixture", loader.load(manifest).datasetId)
            video.appendBytes(byteArrayOf(4))
            assertThrows(IllegalArgumentException::class.java) { loader.load(manifest) }
        } finally {
            directory.deleteRecursively()
        }
    }

    @Test
    fun `regression gate explains all failed thresholds`() {
        val evaluation = OfflineEvaluationReport(
            frameCount = 2,
            evaluatedFrameCount = 1,
            failedFrames = listOf(OfflineFrameFailure("frame-2", "decode failed")),
            modelVersions = setOf("fixture-v1"),
            overall = DetectionMetrics(1, 1, 1),
            byLabel = mapOf("obstacle" to DetectionMetrics(1, 0, 1)),
            latency = LatencyMetrics(1, 40.0, 40, 40, 40),
        )

        val result = OfflineRegressionGate.evaluate(
            evaluation,
            OfflineRegressionPolicy(
                minimumOverallPrecision = 0.8,
                minimumOverallRecall = 0.8,
                minimumRecallByLabel = mapOf("obstacle" to 0.9, "vehicle" to 0.5),
                maximumP95LatencyMillis = 30,
                maximumFailedFrames = 0,
            ),
        )

        assertFalse(result.passed)
        assertEquals(6, result.violations.size)
        assertTrue(result.violations.any { it.contains("vehicle") })
    }

    private class TestFrameLease(
        override val stamp: FrameStamp,
        override val rotationDegrees: Int,
    ) : PerceptionFrameLease {
        override val width = 1
        override val height = 1
        override val pixelFormat = PixelFormat.RGBA_8888
        override val planes = listOf(FramePlane(ByteBuffer.allocate(4), 4, 4))
        override fun close() = Unit
    }

    private fun File.sha256(): String = MessageDigest.getInstance("SHA-256")
        .digest(readBytes())
        .joinToString("") { "%02x".format(it) }
}
