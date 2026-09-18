package kr.co.navi.mobility.ai.offline

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.media.MediaMetadataRetriever
import java.io.File
import java.nio.ByteBuffer
import kotlin.math.abs
import kotlin.math.max
import kr.co.navi.mobility.guidance.contract.FramePlane
import kr.co.navi.mobility.guidance.contract.FrameStamp
import kr.co.navi.mobility.guidance.contract.PerceptionFrameLease
import kr.co.navi.mobility.guidance.contract.PixelFormat

/** Decodes a still image or a selected MP4 frame into a short-lived ARGB/RGBA frame lease. */
class AndroidMediaFrameDecoder : OfflineFrameDecoder {
    override fun open(
        source: OfflineFrameSource,
        stamp: FrameStamp,
        rotationDegrees: Int,
    ): PerceptionFrameLease {
        require(source.file.isFile) { "Media does not exist: ${source.file}" }
        val decoded = when (source) {
            is OfflineFrameSource.Image -> decodeImage(source.file)
            is OfflineFrameSource.Video -> decodeVideoFrame(source.file, source.positionMillis)
        }
        val bitmap = if (decoded.config == Bitmap.Config.ARGB_8888) {
            decoded
        } else {
            decoded.copy(Bitmap.Config.ARGB_8888, false).also { decoded.recycle() }
        }
        return BitmapFrameLease(stamp, bitmap, rotationDegrees)
    }

    private fun decodeImage(file: File): Bitmap =
        requireNotNull(BitmapFactory.decodeFile(file.absolutePath)) {
            "Unsupported or corrupt image: $file"
        }

    private fun decodeVideoFrame(file: File, positionMillis: Long): Bitmap {
        val retriever = MediaMetadataRetriever()
        return try {
            retriever.setDataSource(file.absolutePath)
            requireNotNull(
                retriever.getFrameAtTime(
                    positionMillis * MICROS_PER_MILLISECOND,
                    MediaMetadataRetriever.OPTION_CLOSEST,
                ),
            ) { "Could not decode video frame at ${positionMillis}ms: $file" }
        } finally {
            retriever.release()
        }
    }

    private companion object {
        const val MICROS_PER_MILLISECOND = 1_000L
    }
}

/** Adds actual MP4 duration validation to the platform-independent hash checks. */
class AndroidOfflineRecordingValidator : OfflineRecordingValidator {
    override fun validate(
        datasetRoot: File,
        source: OfflineSourceRecording,
        maximumVideoPositionMillis: Long,
    ) {
        Sha256OfflineRecordingValidator.validate(datasetRoot, source, maximumVideoPositionMillis)
        val video = File(datasetRoot, source.videoPath).canonicalFile
        val retriever = MediaMetadataRetriever()
        val actualDurationMillis = try {
            retriever.setDataSource(video.absolutePath)
            requireNotNull(
                retriever.extractMetadata(MediaMetadataRetriever.METADATA_KEY_DURATION)?.toLongOrNull(),
            ) { "MP4 duration metadata is missing: $video" }
        } finally {
            retriever.release()
        }
        val toleranceMillis = max(
            MINIMUM_DURATION_TOLERANCE_MILLIS,
            max(source.sampleIntervalMillis, source.estimatedSyncErrorMillis),
        )
        require(abs(actualDurationMillis - source.durationMillis) <= toleranceMillis) {
            "MP4 duration ${actualDurationMillis}ms differs from telemetry duration " +
                "${source.durationMillis}ms by more than ${toleranceMillis}ms"
        }
        require(maximumVideoPositionMillis <= actualDurationMillis + toleranceMillis) {
            "requested frame position exceeds actual MP4 duration"
        }
    }

    private companion object {
        const val MINIMUM_DURATION_TOLERANCE_MILLIS = 1_000L
    }
}

private class BitmapFrameLease(
    override val stamp: FrameStamp,
    bitmap: Bitmap,
    override val rotationDegrees: Int,
) : PerceptionFrameLease {
    private val buffer = ByteBuffer.allocateDirect(bitmap.byteCount).also {
        bitmap.copyPixelsToBuffer(it)
        it.flip()
    }
    private var closed = false

    override val width: Int = bitmap.width
    override val height: Int = bitmap.height
    override val pixelFormat: PixelFormat = PixelFormat.RGBA_8888
    override val planes: List<FramePlane> = listOf(
        FramePlane(
            buffer = buffer.asReadOnlyBuffer(),
            rowStride = bitmap.rowBytes,
            pixelStride = BYTES_PER_PIXEL,
        ),
    )

    init {
        bitmap.recycle()
    }

    override fun close() {
        check(!closed) { "frame lease was closed twice" }
        closed = true
    }

    private companion object {
        const val BYTES_PER_PIXEL = 4
    }
}
