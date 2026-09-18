package kr.co.navi.mobility.ai.tracking

import kr.co.navi.mobility.ai.PerceptionEngine
import kr.co.navi.mobility.guidance.contract.DetectedRegion
import kr.co.navi.mobility.guidance.contract.NormalizedRegion
import kr.co.navi.mobility.guidance.contract.PerceptionFrameLease
import kr.co.navi.mobility.guidance.contract.PerceptionResult
import kotlin.math.max
import kotlin.math.min

/** Lightweight deterministic IoU tracker used as the first M2 temporal baseline. */
class TemporalDetectionTracker(
    private val minimumIou: Float = 0.3f,
    private val maximumMissedFrames: Int = 2,
    private val trackIdPrefix: String = "track",
) {
    private data class Track(
        val id: String,
        val label: String,
        var bounds: NormalizedRegion,
        var missedFrames: Int,
    )

    private val tracks = linkedMapOf<String, Track>()
    private var nextTrackNumber = 1L
    private var lastFrameId: Long? = null

    init {
        require(minimumIou > 0f && minimumIou <= 1f)
        require(maximumMissedFrames >= 0)
        require(trackIdPrefix.isNotBlank())
    }

    @Synchronized
    fun update(result: PerceptionResult): PerceptionResult {
        val previousFrameId = lastFrameId
        require(previousFrameId == null || result.stamp.frameId > previousFrameId) {
            "tracker frame IDs must be strictly increasing"
        }
        require(result.detections.none { it.trackId != null }) {
            "tracker accepts untracked detections only"
        }
        lastFrameId = result.stamp.frameId

        tracks.values.forEach { it.missedFrames += 1 }
        data class Candidate(val trackId: String, val detectionIndex: Int, val iou: Float)

        val candidates = buildList {
            tracks.values.forEach { track ->
                result.detections.forEachIndexed { detectionIndex, detection ->
                    if (track.label == detection.label) {
                        val overlap = intersectionOverUnion(track.bounds, detection.bounds)
                        if (overlap >= minimumIou) add(Candidate(track.id, detectionIndex, overlap))
                    }
                }
            }
        }.sortedWith(
            compareByDescending<Candidate> { it.iou }
                .thenBy { it.trackId }
                .thenBy { it.detectionIndex },
        )

        val assignedTracks = mutableSetOf<String>()
        val assignedDetections = mutableMapOf<Int, String>()
        candidates.forEach { candidate ->
            if (candidate.trackId !in assignedTracks && candidate.detectionIndex !in assignedDetections) {
                assignedTracks += candidate.trackId
                assignedDetections[candidate.detectionIndex] = candidate.trackId
                tracks.getValue(candidate.trackId).apply {
                    bounds = result.detections[candidate.detectionIndex].bounds
                    missedFrames = 0
                }
            }
        }

        result.detections.indices.forEach { detectionIndex ->
            if (detectionIndex !in assignedDetections) {
                val detection = result.detections[detectionIndex]
                val id = "$trackIdPrefix-${nextTrackNumber++}"
                tracks[id] = Track(id, detection.label, detection.bounds, missedFrames = 0)
                assignedDetections[detectionIndex] = id
            }
        }
        tracks.entries.removeAll { (_, track) -> track.missedFrames > maximumMissedFrames }

        return result.copy(
            detections = result.detections.mapIndexed { index, detection ->
                detection.copy(trackId = assignedDetections.getValue(index))
            },
        )
    }

    @Synchronized
    fun reset() {
        tracks.clear()
        nextTrackNumber = 1L
        lastFrameId = null
    }

    private fun intersectionOverUnion(a: NormalizedRegion, b: NormalizedRegion): Float {
        val width = max(0f, min(a.right, b.right) - max(a.left, b.left))
        val height = max(0f, min(a.bottom, b.bottom) - max(a.top, b.top))
        val intersection = width * height
        val union = area(a) + area(b) - intersection
        return if (union <= 0f) 0f else intersection / union
    }

    private fun area(region: NormalizedRegion): Float =
        (region.right - region.left) * (region.bottom - region.top)
}

class TrackingPerceptionEngine(
    private val delegate: PerceptionEngine,
    private val tracker: TemporalDetectionTracker = TemporalDetectionTracker(),
) : PerceptionEngine {
    override suspend fun analyze(frame: PerceptionFrameLease): PerceptionResult =
        tracker.update(delegate.analyze(frame))

    override fun close() = delegate.close()
}
