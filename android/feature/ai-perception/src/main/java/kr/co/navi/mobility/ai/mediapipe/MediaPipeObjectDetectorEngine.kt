package kr.co.navi.mobility.ai.mediapipe

import android.graphics.Bitmap
import android.graphics.Matrix
import com.google.mediapipe.framework.image.BitmapImageBuilder
import com.google.mediapipe.tasks.core.BaseOptions
import com.google.mediapipe.tasks.vision.core.RunningMode
import com.google.mediapipe.tasks.vision.objectdetector.ObjectDetector
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kr.co.navi.mobility.ai.PerceptionEngine
import kr.co.navi.mobility.guidance.contract.DetectedRegion
import kr.co.navi.mobility.guidance.contract.NormalizedRegion
import kr.co.navi.mobility.guidance.contract.PerceptionFrameLease
import kr.co.navi.mobility.guidance.contract.PerceptionResult
import kr.co.navi.mobility.guidance.contract.PixelFormat

data class MediaPipeObjectDetectorConfig(
    val modelAssetPath: String = DEFAULT_MODEL_ASSET_PATH,
    val modelVersion: String = "efficientdet-lite0-int8",
    val scoreThreshold: Float = 0.35f,
    val maxResults: Int = 10,
    val categoryAllowlist: List<String> = emptyList(),
) {
    init {
        require(modelAssetPath.isNotBlank())
        require(modelVersion.isNotBlank())
        require(scoreThreshold in 0f..1f)
        require(maxResults > 0)
    }

    companion object {
        const val DEFAULT_MODEL_ASSET_PATH = "efficientdet_lite0_int8.tflite"
    }
}

/** CPU/IMAGE-mode baseline used by deterministic M2 replay, not the future live AR pipeline. */
class MediaPipeObjectDetectorEngine(
    context: android.content.Context,
    private val config: MediaPipeObjectDetectorConfig = MediaPipeObjectDetectorConfig(),
) : PerceptionEngine {
    private val lock = Any()
    private var closed = false
    private val detector: ObjectDetector

    init {
        val baseOptions = BaseOptions.builder()
            .setModelAssetPath(config.modelAssetPath)
            .build()
        val options = ObjectDetector.ObjectDetectorOptions.builder()
            .setBaseOptions(baseOptions)
            .setRunningMode(RunningMode.IMAGE)
            .setScoreThreshold(config.scoreThreshold)
            .setMaxResults(config.maxResults)
            .apply {
                if (config.categoryAllowlist.isNotEmpty()) {
                    setCategoryAllowlist(config.categoryAllowlist)
                }
            }
            .build()
        detector = ObjectDetector.createFromOptions(context.applicationContext, options)
    }

    override suspend fun analyze(frame: PerceptionFrameLease): PerceptionResult =
        withContext(Dispatchers.Default) {
            require(frame.pixelFormat == PixelFormat.RGBA_8888) {
                "M2 MediaPipe baseline accepts RGBA_8888 frames only"
            }
            val uprightBitmap = frame.toUprightBitmap()
            try {
                val startedAt = System.nanoTime()
                val result = synchronized(lock) {
                    check(!closed) { "MediaPipe object detector is closed" }
                    BitmapImageBuilder(uprightBitmap).build().let(detector::detect)
                }
                val inferenceMillis = (System.nanoTime() - startedAt) / NANOS_PER_MILLISECOND
                val width = uprightBitmap.width.toFloat()
                val height = uprightBitmap.height.toFloat()
                val detections = result.detections().mapNotNull { detection ->
                    val category = detection.categories().maxByOrNull { it.score() }
                        ?: return@mapNotNull null
                    val box = detection.boundingBox()
                    val label = category.categoryName().ifBlank { category.displayName() }
                    if (label.isBlank()) return@mapNotNull null
                    DetectedRegion(
                        label = label,
                        confidence = category.score().coerceIn(0f, 1f),
                        bounds = NormalizedRegion(
                            left = (box.left / width).coerceIn(0f, 1f),
                            top = (box.top / height).coerceIn(0f, 1f),
                            right = (box.right / width).coerceIn(0f, 1f),
                            bottom = (box.bottom / height).coerceIn(0f, 1f),
                        ),
                    )
                }
                PerceptionResult(
                    stamp = frame.stamp,
                    modelVersion = config.modelVersion,
                    inferenceMillis = inferenceMillis,
                    detections = detections,
                )
            } finally {
                uprightBitmap.recycle()
            }
        }

    override fun close() {
        synchronized(lock) {
            if (!closed) {
                closed = true
                detector.close()
            }
        }
    }

    private fun PerceptionFrameLease.toUprightBitmap(): Bitmap {
        require(planes.size == 1) { "RGBA frame must have exactly one plane" }
        val plane = planes.single()
        require(plane.pixelStride == BYTES_PER_PIXEL) { "RGBA pixel stride must be 4" }
        require(plane.rowStride >= width * BYTES_PER_PIXEL) { "RGBA row stride is too small" }

        val packed = java.nio.ByteBuffer.allocateDirect(width * height * BYTES_PER_PIXEL)
        val source = plane.buffer.duplicate()
        val rowBytes = width * BYTES_PER_PIXEL
        val row = ByteArray(rowBytes)
        repeat(height) { y ->
            source.position(y * plane.rowStride)
            source.get(row)
            packed.put(row)
        }
        packed.flip()

        val original = Bitmap.createBitmap(width, height, Bitmap.Config.ARGB_8888).also {
            it.copyPixelsFromBuffer(packed)
        }
        if (rotationDegrees == 0) return original
        return Bitmap.createBitmap(
            original,
            0,
            0,
            original.width,
            original.height,
            Matrix().apply { postRotate(rotationDegrees.toFloat()) },
            true,
        ).also { original.recycle() }
    }

    private companion object {
        const val BYTES_PER_PIXEL = 4
        const val NANOS_PER_MILLISECOND = 1_000_000L
    }
}
