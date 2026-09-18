package kr.co.navi.mobility.ai.segmentation

import kotlinx.serialization.Serializable

/** One unsigned 8-bit class id per pixel, independent from any model runtime. */
data class SegmentationMask(
    val width: Int,
    val height: Int,
    val classIds: ByteArray,
) {
    init {
        require(width > 0 && height > 0)
        require(classIds.size == width * height) {
            "segmentation mask must contain exactly width * height pixels"
        }
    }
}

fun interface SegmentationMaskDecoder {
    fun decode(encodedMask: java.io.File): SegmentationMask
}

@Serializable
data class SegmentationClassMetrics(
    val classId: Int,
    val label: String,
    val intersectionPixels: Int,
    val unionPixels: Int,
    val truthPixels: Int,
    val predictedPixels: Int,
    val iou: Double,
    val dice: Double,
    val pixelRecall: Double,
)

@Serializable
data class SegmentationEvaluationReport(
    val width: Int,
    val height: Int,
    val byLabel: Map<String, SegmentationClassMetrics>,
    val macroIou: Double,
    val macroDice: Double,
    val macroPixelRecall: Double,
)

object SegmentationEvaluator {
    fun evaluate(
        expected: SegmentationMask,
        predicted: SegmentationMask,
        labels: Map<Int, String>,
    ): SegmentationEvaluationReport {
        require(expected.width == predicted.width && expected.height == predicted.height) {
            "expected and predicted masks must have identical dimensions"
        }
        require(labels.isNotEmpty()) { "at least one evaluated segmentation label is required" }
        require(labels.keys.all { it in 0..255 })
        require(labels.values.all { it.isNotBlank() })
        require(labels.values.distinct().size == labels.size) { "segmentation labels must be unique" }

        val byLabel = linkedMapOf<String, SegmentationClassMetrics>()
        labels.toSortedMap().forEach { (classId, label) ->
            var intersection = 0
            var union = 0
            var truth = 0
            var prediction = 0
            expected.classIds.indices.forEach { index ->
                val expectedId = expected.classIds[index].toInt() and 0xff
                val predictedId = predicted.classIds[index].toInt() and 0xff
                val isTruth = expectedId == classId
                val isPrediction = predictedId == classId
                if (isTruth) truth += 1
                if (isPrediction) prediction += 1
                if (isTruth && isPrediction) intersection += 1
                if (isTruth || isPrediction) union += 1
            }
            byLabel[label] = SegmentationClassMetrics(
                classId = classId,
                label = label,
                intersectionPixels = intersection,
                unionPixels = union,
                truthPixels = truth,
                predictedPixels = prediction,
                iou = ratio(intersection, union),
                dice = ratio(2 * intersection, truth + prediction),
                pixelRecall = ratio(intersection, truth),
            )
        }
        val metrics = byLabel.values
        return SegmentationEvaluationReport(
            width = expected.width,
            height = expected.height,
            byLabel = byLabel,
            macroIou = metrics.map { it.iou }.average(),
            macroDice = metrics.map { it.dice }.average(),
            macroPixelRecall = metrics.map { it.pixelRecall }.average(),
        )
    }

    private fun ratio(numerator: Int, denominator: Int): Double =
        if (denominator == 0) 1.0 else numerator.toDouble() / denominator
}
