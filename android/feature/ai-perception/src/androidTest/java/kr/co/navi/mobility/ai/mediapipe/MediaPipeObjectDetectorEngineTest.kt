package kr.co.navi.mobility.ai.mediapipe

import android.content.Context
import android.graphics.Bitmap
import android.graphics.Color
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import java.nio.ByteBuffer
import kotlinx.coroutines.runBlocking
import kr.co.navi.mobility.ai.offline.AndroidMediaFrameDecoder
import kr.co.navi.mobility.ai.offline.OfflineFrameSource
import kr.co.navi.mobility.guidance.contract.FramePlane
import kr.co.navi.mobility.guidance.contract.FrameStamp
import kr.co.navi.mobility.guidance.contract.PerceptionFrameLease
import kr.co.navi.mobility.guidance.contract.PixelFormat
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class MediaPipeObjectDetectorEngineTest {
    @Test
    fun stillImageDecoderProducesAnRgbaLease() {
        val context = ApplicationProvider.getApplicationContext<Context>()
        val imageFile = java.io.File(context.cacheDir, "offline-decoder-test.png")
        val bitmap = Bitmap.createBitmap(16, 8, Bitmap.Config.ARGB_8888)
        try {
            imageFile.outputStream().use { output ->
                assertTrue(bitmap.compress(Bitmap.CompressFormat.PNG, 100, output))
            }
        } finally {
            bitmap.recycle()
        }

        val frame = AndroidMediaFrameDecoder().open(
            source = OfflineFrameSource.Image(imageFile),
            stamp = FrameStamp(2, 2_000_000),
            rotationDegrees = 0,
        )
        assertEquals(16, frame.width)
        assertEquals(8, frame.height)
        assertEquals(PixelFormat.RGBA_8888, frame.pixelFormat)
        assertEquals(16 * 4, frame.planes.single().rowStride)
        frame.close()
        assertTrue(imageFile.delete())
    }

    @Test
    fun baselineModelLoadsAndProcessesOneFrame() = runBlocking {
        val context = ApplicationProvider.getApplicationContext<Context>()
        val frame = SolidBitmapFrameLease(FrameStamp(1, 1_000_000))

        MediaPipeObjectDetectorEngine(context).use { engine ->
            val result = engine.analyze(frame)
            assertEquals(frame.stamp, result.stamp)
            assertEquals("efficientdet-lite0-int8", result.modelVersion)
            assertTrue(result.inferenceMillis >= 0)
        }
        frame.close()
    }

    private class SolidBitmapFrameLease(
        override val stamp: FrameStamp,
    ) : PerceptionFrameLease {
        private val bitmap = Bitmap.createBitmap(320, 320, Bitmap.Config.ARGB_8888).apply {
            eraseColor(Color.DKGRAY)
        }
        private val buffer = ByteBuffer.allocateDirect(bitmap.byteCount).also {
            bitmap.copyPixelsToBuffer(it)
            it.flip()
        }

        override val width = bitmap.width
        override val height = bitmap.height
        override val rotationDegrees = 0
        override val pixelFormat = PixelFormat.RGBA_8888
        override val planes = listOf(FramePlane(buffer, bitmap.rowBytes, 4))

        override fun close() {
            bitmap.recycle()
        }
    }
}
