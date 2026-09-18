package kr.co.navi.mobility.ai.segmentation

import org.junit.Assert.assertEquals
import org.junit.Assert.assertThrows
import org.junit.Test

class SegmentationEvaluationTest {
    @Test
    fun `evaluates tiny golden mask deterministically`() {
        val expected = mask(1, 1, 0, 2)
        val predicted = mask(1, 0, 0, 2)

        val report = SegmentationEvaluator.evaluate(
            expected = expected,
            predicted = predicted,
            labels = mapOf(1 to "sidewalk", 2 to "roadway"),
        )

        val sidewalk = requireNotNull(report.byLabel["sidewalk"])
        assertEquals(0.5, sidewalk.iou, 0.0001)
        assertEquals(2.0 / 3.0, sidewalk.dice, 0.0001)
        assertEquals(0.5, sidewalk.pixelRecall, 0.0001)
        val roadway = requireNotNull(report.byLabel["roadway"])
        assertEquals(1.0, roadway.iou, 0.0001)
        assertEquals(0.75, report.macroIou, 0.0001)
    }

    @Test
    fun `rejects masks with different dimensions`() {
        assertThrows(IllegalArgumentException::class.java) {
            SegmentationEvaluator.evaluate(
                expected = SegmentationMask(1, 1, byteArrayOf(1)),
                predicted = SegmentationMask(2, 1, byteArrayOf(1, 1)),
                labels = mapOf(1 to "sidewalk"),
            )
        }
    }

    private fun mask(vararg ids: Int) = SegmentationMask(
        width = 2,
        height = 2,
        classIds = ids.map(Int::toByte).toByteArray(),
    )
}
