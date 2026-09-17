package kr.co.navi.mobility.ai.offline

import kr.co.navi.mobility.ai.PerceptionEngine
import kr.co.navi.mobility.guidance.contract.DetectedRegion
import kr.co.navi.mobility.guidance.contract.NormalizedRegion
import kr.co.navi.mobility.guidance.contract.PerceptionFrameLease
import kotlin.math.ceil
import kotlin.math.max
import kotlin.math.min

/** A labelled frame whose short-lived image buffers are opened only when replayed. */
data class OfflineFrameCase(
    val caseId: String,
    val openFrame: () -> PerceptionFrameLease,
    val expected: List<GroundTruthRegion>,
) {
    init {
        require(caseId.isNotBlank()) { "caseId must not be blank" }
    }
}

data class GroundTruthRegion(
    val label: String,
    val bounds: NormalizedRegion,
) {
    init {
        require(label.isNotBlank()) { "label must not be blank" }
    }
}

data class DetectionMetrics(
    val truePositives: Int,
    val falsePositives: Int,
    val falseNegatives: Int,
) {
    val precision: Double
        get() = ratio(truePositives, truePositives + falsePositives)

    val recall: Double
        get() = ratio(truePositives, truePositives + falseNegatives)

    val f1: Double
        get() = if (precision + recall == 0.0) 0.0 else 2.0 * precision * recall / (precision + recall)

    operator fun plus(other: DetectionMetrics): DetectionMetrics = DetectionMetrics(
        truePositives = truePositives + other.truePositives,
        falsePositives = falsePositives + other.falsePositives,
        falseNegatives = falseNegatives + other.falseNegatives,
    )

    private fun ratio(numerator: Int, denominator: Int): Double =
        if (denominator == 0) 0.0 else numerator.toDouble() / denominator
}

data class LatencyMetrics(
    val sampleCount: Int,
    val meanMillis: Double,
    val p50Millis: Long,
    val p95Millis: Long,
    val maxMillis: Long,
)

data class OfflineFrameFailure(
    val caseId: String,
    val reason: String,
)

data class OfflineEvaluationReport(
    val frameCount: Int,
    val evaluatedFrameCount: Int,
    val failedFrames: List<OfflineFrameFailure>,
    val modelVersions: Set<String>,
    val overall: DetectionMetrics,
    val byLabel: Map<String, DetectionMetrics>,
    val latency: LatencyMetrics,
)

/**
 * Deterministic, single-frame-at-a-time evaluator for recorded or synthetic input.
 *
 * Keeping one lease in flight makes the host harness bounded by construction. A decoder adapter
 * supplies [OfflineFrameCase.openFrame], so this evaluator has no dependency on a video codec or
 * a particular ML runtime.
 */
class OfflineReplayHarness(
    private val iouThreshold: Float = 0.5f,
) {
    init {
        require(iouThreshold > 0f && iouThreshold <= 1f) {
            "iouThreshold must be in (0, 1]"
        }
    }

    suspend fun evaluate(
        cases: Iterable<OfflineFrameCase>,
        engine: PerceptionEngine,
    ): OfflineEvaluationReport {
        val caseIds = mutableSetOf<String>()
        val failures = mutableListOf<OfflineFrameFailure>()
        val versions = linkedSetOf<String>()
        val latencies = mutableListOf<Long>()
        val byLabel = linkedMapOf<String, DetectionMetrics>()
        var frameCount = 0
        var evaluatedFrameCount = 0

        cases.forEach { frameCase ->
            frameCount += 1
            require(caseIds.add(frameCase.caseId)) {
                "Duplicate offline frame caseId: ${frameCase.caseId}"
            }

            val frame = try {
                frameCase.openFrame()
            } catch (error: Exception) {
                failures += OfflineFrameFailure(frameCase.caseId, error.message ?: error.javaClass.simpleName)
                addMissedGroundTruth(byLabel, frameCase.expected)
                return@forEach
            }
            val inputStamp = frame.stamp

            val result = try {
                engine.analyze(frame)
            } catch (error: Exception) {
                failures += OfflineFrameFailure(frameCase.caseId, error.message ?: error.javaClass.simpleName)
                addMissedGroundTruth(byLabel, frameCase.expected)
                null
            } finally {
                frame.close()
            }

            if (result == null) return@forEach

            if (result.stamp != inputStamp) {
                failures += OfflineFrameFailure(
                    frameCase.caseId,
                    "Perception result stamp ${result.stamp} does not match input $inputStamp",
                )
                addMissedGroundTruth(byLabel, frameCase.expected)
                return@forEach
            }

            evaluatedFrameCount += 1
            versions += result.modelVersion
            latencies += result.inferenceMillis
            val frameMetrics = match(frameCase.expected, result.detections)
            frameMetrics.forEach { (label, metrics) ->
                byLabel[label] = (byLabel[label] ?: ZERO_METRICS) + metrics
            }
        }

        val stableByLabel = byLabel.toSortedMap()
        return OfflineEvaluationReport(
            frameCount = frameCount,
            evaluatedFrameCount = evaluatedFrameCount,
            failedFrames = failures.toList(),
            modelVersions = versions.toSortedSet(),
            overall = stableByLabel.values.fold(ZERO_METRICS, DetectionMetrics::plus),
            byLabel = stableByLabel,
            latency = summarizeLatency(latencies),
        )
    }

    private fun match(
        expected: List<GroundTruthRegion>,
        actual: List<DetectedRegion>,
    ): Map<String, DetectionMetrics> {
        val labels = (expected.map { it.label } + actual.map { it.label }).toSortedSet()
        return labels.associateWith { label ->
            matchLabel(
                expected = expected.filter { it.label == label },
                actual = actual.filter { it.label == label },
            )
        }
    }

    private fun matchLabel(
        expected: List<GroundTruthRegion>,
        actual: List<DetectedRegion>,
    ): DetectionMetrics {
        data class Candidate(val expectedIndex: Int, val actualIndex: Int, val iou: Float)

        val candidates = buildList {
            expected.forEachIndexed { expectedIndex, truth ->
                actual.forEachIndexed { actualIndex, detection ->
                    val overlap = intersectionOverUnion(truth.bounds, detection.bounds)
                    if (overlap >= iouThreshold) add(Candidate(expectedIndex, actualIndex, overlap))
                }
            }
        }.sortedWith(
            compareByDescending<Candidate> { it.iou }
                .thenBy { it.expectedIndex }
                .thenBy { it.actualIndex },
        )

        val matchedExpected = mutableSetOf<Int>()
        val matchedActual = mutableSetOf<Int>()
        candidates.forEach { candidate ->
            if (candidate.expectedIndex !in matchedExpected && candidate.actualIndex !in matchedActual) {
                matchedExpected += candidate.expectedIndex
                matchedActual += candidate.actualIndex
            }
        }

        return DetectionMetrics(
            truePositives = matchedExpected.size,
            falsePositives = actual.size - matchedActual.size,
            falseNegatives = expected.size - matchedExpected.size,
        )
    }

    private fun addMissedGroundTruth(
        byLabel: MutableMap<String, DetectionMetrics>,
        expected: List<GroundTruthRegion>,
    ) {
        expected.groupingBy { it.label }.eachCount().forEach { (label, count) ->
            byLabel[label] = (byLabel[label] ?: ZERO_METRICS) + DetectionMetrics(0, 0, count)
        }
    }

    private fun intersectionOverUnion(a: NormalizedRegion, b: NormalizedRegion): Float {
        val intersectionWidth = max(0f, min(a.right, b.right) - max(a.left, b.left))
        val intersectionHeight = max(0f, min(a.bottom, b.bottom) - max(a.top, b.top))
        val intersection = intersectionWidth * intersectionHeight
        val areaA = (a.right - a.left) * (a.bottom - a.top)
        val areaB = (b.right - b.left) * (b.bottom - b.top)
        val union = areaA + areaB - intersection
        return if (union <= 0f) 0f else intersection / union
    }

    private fun summarizeLatency(samples: List<Long>): LatencyMetrics {
        if (samples.isEmpty()) return LatencyMetrics(0, 0.0, 0, 0, 0)
        val sorted = samples.sorted()
        return LatencyMetrics(
            sampleCount = sorted.size,
            meanMillis = sorted.average(),
            p50Millis = nearestRank(sorted, 0.50),
            p95Millis = nearestRank(sorted, 0.95),
            maxMillis = sorted.last(),
        )
    }

    private fun nearestRank(sorted: List<Long>, percentile: Double): Long {
        val index = ceil(percentile * sorted.size).toInt().coerceIn(1, sorted.size) - 1
        return sorted[index]
    }

    private companion object {
        val ZERO_METRICS = DetectionMetrics(0, 0, 0)
    }
}
