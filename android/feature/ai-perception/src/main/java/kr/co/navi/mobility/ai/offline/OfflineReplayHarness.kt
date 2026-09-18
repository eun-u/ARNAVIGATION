package kr.co.navi.mobility.ai.offline

import kotlinx.serialization.Serializable
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
    val context: OfflineFrameContext = OfflineFrameContext(),
    val segmentation: OfflineSegmentationGroundTruth? = null,
) {
    init {
        require(caseId.isNotBlank()) { "caseId must not be blank" }
    }
}

data class GroundTruthRegion(
    val label: String,
    val bounds: NormalizedRegion,
    val instanceId: String? = null,
) {
    init {
        require(label.isNotBlank()) { "label must not be blank" }
        require(instanceId == null || instanceId.isNotBlank())
    }
}

@Serializable
data class DetectionMetrics(
    val truePositives: Int,
    val falsePositives: Int,
    val falseNegatives: Int,
    val precision: Double = ratio(truePositives, truePositives + falsePositives),
    val recall: Double = ratio(truePositives, truePositives + falseNegatives),
    val f1: Double = if (precision + recall == 0.0) {
        0.0
    } else {
        2.0 * precision * recall / (precision + recall)
    },
) {
    operator fun plus(other: DetectionMetrics): DetectionMetrics = DetectionMetrics(
        truePositives = truePositives + other.truePositives,
        falsePositives = falsePositives + other.falsePositives,
        falseNegatives = falseNegatives + other.falseNegatives,
    )

    private companion object {
        fun ratio(numerator: Int, denominator: Int): Double =
            if (denominator == 0) 0.0 else numerator.toDouble() / denominator
    }
}

@Serializable
data class LatencyMetrics(
    val sampleCount: Int,
    val meanMillis: Double,
    val p50Millis: Long,
    val p95Millis: Long,
    val maxMillis: Long,
)

@Serializable
data class OfflineFrameFailure(
    val caseId: String,
    val reason: String,
)

@Serializable
data class OfflineDetectionSnapshot(
    val label: String,
    val confidence: Float,
    val left: Float,
    val top: Float,
    val right: Float,
    val bottom: Float,
    val trackId: String? = null,
)

@Serializable
data class OfflineFrameEvaluation(
    val caseId: String,
    val status: String,
    val error: String? = null,
    val context: OfflineFrameContext,
    val modelVersion: String? = null,
    val inferenceMillis: Long? = null,
    val predictions: List<OfflineDetectionSnapshot> = emptyList(),
    val metrics: DetectionMetrics,
)

@Serializable
data class TrackingMetrics(
    val annotatedInstances: Int,
    val matchedObservations: Int,
    val idSwitches: Int,
    val uniquePredictedTracks: Int,
)

@Serializable
data class OfflineEvaluationReport(
    val frameCount: Int,
    val evaluatedFrameCount: Int,
    val failedFrames: List<OfflineFrameFailure>,
    val modelVersions: Set<String>,
    val overall: DetectionMetrics,
    val byLabel: Map<String, DetectionMetrics>,
    val byContext: Map<String, DetectionMetrics> = emptyMap(),
    val byObjectSize: Map<String, DetectionMetrics> = emptyMap(),
    val tracking: TrackingMetrics = TrackingMetrics(0, 0, 0, 0),
    val latency: LatencyMetrics,
    val frames: List<OfflineFrameEvaluation> = emptyList(),
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
        val byContext = linkedMapOf<String, DetectionMetrics>()
        val byObjectSize = linkedMapOf<String, DetectionMetrics>()
        val frameEvaluations = mutableListOf<OfflineFrameEvaluation>()
        val lastTrackByInstance = mutableMapOf<String, String>()
        val annotatedInstances = mutableSetOf<String>()
        val predictedTracks = mutableSetOf<String>()
        var matchedTrackObservations = 0
        var idSwitches = 0
        var frameCount = 0
        var evaluatedFrameCount = 0

        cases.forEach { frameCase ->
            frameCount += 1
            require(caseIds.add(frameCase.caseId)) {
                "Duplicate offline frame caseId: ${frameCase.caseId}"
            }
            frameCase.expected.mapNotNullTo(annotatedInstances) { it.instanceId }

            val frame = try {
                frameCase.openFrame()
            } catch (error: Exception) {
                val reason = error.message ?: error.javaClass.simpleName
                failures += OfflineFrameFailure(frameCase.caseId, reason)
                val metrics = missedMetrics(frameCase.expected)
                addMetrics(byLabel, metrics)
                addContextMetrics(byContext, frameCase.context, metrics)
                addObjectSizeMetrics(byObjectSize, frameCase.expected, emptySet())
                frameEvaluations += failedFrame(frameCase, "decode_failure", reason, metrics)
                return@forEach
            }
            val inputStamp = frame.stamp

            val result = try {
                engine.analyze(frame)
            } catch (error: Exception) {
                val reason = error.message ?: error.javaClass.simpleName
                failures += OfflineFrameFailure(frameCase.caseId, reason)
                val metrics = missedMetrics(frameCase.expected)
                addMetrics(byLabel, metrics)
                addContextMetrics(byContext, frameCase.context, metrics)
                addObjectSizeMetrics(byObjectSize, frameCase.expected, emptySet())
                frameEvaluations += failedFrame(frameCase, "inference_failure", reason, metrics)
                null
            } finally {
                frame.close()
            }

            if (result == null) return@forEach

            if (result.stamp != inputStamp) {
                val reason = "Perception result stamp ${result.stamp} does not match input $inputStamp"
                failures += OfflineFrameFailure(
                    frameCase.caseId,
                    reason,
                )
                val metrics = missedMetrics(frameCase.expected)
                addMetrics(byLabel, metrics)
                addContextMetrics(byContext, frameCase.context, metrics)
                addObjectSizeMetrics(byObjectSize, frameCase.expected, emptySet())
                frameEvaluations += failedFrame(frameCase, "stamp_mismatch", reason, metrics)
                return@forEach
            }

            evaluatedFrameCount += 1
            versions += result.modelVersion
            latencies += result.inferenceMillis
            val match = match(frameCase.expected, result.detections)
            addMetrics(byLabel, match.byLabel)
            addContextMetrics(byContext, frameCase.context, match.byLabel)
            addObjectSizeMetrics(byObjectSize, frameCase.expected, match.matchedExpected)
            match.pairs.forEach { pair ->
                val instanceId = frameCase.expected[pair.expectedIndex].instanceId ?: return@forEach
                val trackId = result.detections[pair.actualIndex].trackId ?: return@forEach
                matchedTrackObservations += 1
                predictedTracks += trackId
                val previousTrack = lastTrackByInstance.put(instanceId, trackId)
                if (previousTrack != null && previousTrack != trackId) idSwitches += 1
            }
            val frameOverall = match.byLabel.values.fold(ZERO_METRICS, DetectionMetrics::plus)
            frameEvaluations += OfflineFrameEvaluation(
                caseId = frameCase.caseId,
                status = "success",
                context = frameCase.context,
                modelVersion = result.modelVersion,
                inferenceMillis = result.inferenceMillis,
                predictions = result.detections.map { it.toSnapshot() },
                metrics = frameOverall,
            )
        }

        val stableByLabel = byLabel.toSortedMap()
        return OfflineEvaluationReport(
            frameCount = frameCount,
            evaluatedFrameCount = evaluatedFrameCount,
            failedFrames = failures.toList(),
            modelVersions = versions.toSortedSet(),
            overall = stableByLabel.values.fold(ZERO_METRICS, DetectionMetrics::plus),
            byLabel = stableByLabel,
            byContext = byContext.toSortedMap(),
            byObjectSize = byObjectSize.toSortedMap(),
            tracking = TrackingMetrics(
                annotatedInstances = annotatedInstances.size,
                matchedObservations = matchedTrackObservations,
                idSwitches = idSwitches,
                uniquePredictedTracks = predictedTracks.size,
            ),
            latency = summarizeLatency(latencies),
            frames = frameEvaluations,
        )
    }

    private data class MatchPair(val expectedIndex: Int, val actualIndex: Int)

    private data class MatchResult(
        val byLabel: Map<String, DetectionMetrics>,
        val pairs: List<MatchPair>,
    ) {
        val matchedExpected: Set<Int> = pairs.mapTo(mutableSetOf()) { it.expectedIndex }
    }

    private fun match(
        expected: List<GroundTruthRegion>,
        actual: List<DetectedRegion>,
    ): MatchResult {
        val labels = (expected.map { it.label } + actual.map { it.label }).toSortedSet()
        val allPairs = mutableListOf<MatchPair>()
        val byLabel = labels.associateWith { label ->
            val expectedIndexes = expected.indices.filter { expected[it].label == label }
            val actualIndexes = actual.indices.filter { actual[it].label == label }
            val result = matchLabel(
                expected = expectedIndexes.map(expected::get),
                actual = actualIndexes.map(actual::get),
            )
            result.pairs.forEach {
                allPairs += MatchPair(expectedIndexes[it.expectedIndex], actualIndexes[it.actualIndex])
            }
            result.metrics
        }
        return MatchResult(byLabel, allPairs)
    }

    private data class LabelMatchResult(
        val metrics: DetectionMetrics,
        val pairs: List<MatchPair>,
    )

    private fun matchLabel(
        expected: List<GroundTruthRegion>,
        actual: List<DetectedRegion>,
    ): LabelMatchResult {
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
        val selectedPairs = mutableListOf<MatchPair>()
        candidates.forEach { candidate ->
            if (candidate.expectedIndex !in matchedExpected && candidate.actualIndex !in matchedActual) {
                matchedExpected += candidate.expectedIndex
                matchedActual += candidate.actualIndex
                selectedPairs += MatchPair(candidate.expectedIndex, candidate.actualIndex)
            }
        }

        return LabelMatchResult(
            metrics = DetectionMetrics(
                truePositives = matchedExpected.size,
                falsePositives = actual.size - matchedActual.size,
                falseNegatives = expected.size - matchedExpected.size,
            ),
            pairs = selectedPairs,
        )
    }

    private fun addMetrics(
        target: MutableMap<String, DetectionMetrics>,
        metrics: Map<String, DetectionMetrics>,
    ) {
        metrics.forEach { (key, value) ->
            target[key] = (target[key] ?: ZERO_METRICS) + value
        }
    }

    private fun missedMetrics(expected: List<GroundTruthRegion>): Map<String, DetectionMetrics> =
        expected.groupingBy { it.label }.eachCount().mapValues { (_, count) ->
            DetectionMetrics(0, 0, count)
        }

    private fun addContextMetrics(
        target: MutableMap<String, DetectionMetrics>,
        context: OfflineFrameContext,
        byLabel: Map<String, DetectionMetrics>,
    ) {
        val metrics = byLabel.values.fold(ZERO_METRICS, DetectionMetrics::plus)
        listOf(
            "session:${context.sessionId ?: "unknown"}",
            "tracking_quality:${context.trackingQuality ?: "unknown"}",
            "depth_active:${context.depthActive ?: "unknown"}",
            "route_aligned:${context.routeAligned ?: "unknown"}",
        ).forEach { key -> target[key] = (target[key] ?: ZERO_METRICS) + metrics }
    }

    private fun addObjectSizeMetrics(
        target: MutableMap<String, DetectionMetrics>,
        expected: List<GroundTruthRegion>,
        matchedExpected: Set<Int>,
    ) {
        expected.forEachIndexed { index, truth ->
            val area = (truth.bounds.right - truth.bounds.left) *
                (truth.bounds.bottom - truth.bounds.top)
            val bucket = when {
                area < 0.02f -> "small"
                area < 0.15f -> "medium"
                else -> "large"
            }
            val metrics = if (index in matchedExpected) {
                DetectionMetrics(1, 0, 0)
            } else {
                DetectionMetrics(0, 0, 1)
            }
            target[bucket] = (target[bucket] ?: ZERO_METRICS) + metrics
        }
    }

    private fun failedFrame(
        frameCase: OfflineFrameCase,
        status: String,
        reason: String,
        byLabel: Map<String, DetectionMetrics>,
    ) = OfflineFrameEvaluation(
        caseId = frameCase.caseId,
        status = status,
        error = reason,
        context = frameCase.context,
        metrics = byLabel.values.fold(ZERO_METRICS, DetectionMetrics::plus),
    )

    private fun DetectedRegion.toSnapshot() = OfflineDetectionSnapshot(
        label = label,
        confidence = confidence,
        left = bounds.left,
        top = bounds.top,
        right = bounds.right,
        bottom = bounds.bottom,
        trackId = trackId,
    )

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
