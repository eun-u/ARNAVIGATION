package kr.co.navi.mobility.ai.offline

import java.io.File
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json
import kr.co.navi.mobility.guidance.contract.FrameStamp
import kr.co.navi.mobility.guidance.contract.NormalizedRegion
import kr.co.navi.mobility.guidance.contract.PerceptionFrameLease

@Serializable
data class OfflineDatasetManifest(
    @SerialName("schema_version") val schemaVersion: Int,
    @SerialName("dataset_id") val datasetId: String,
    @SerialName("source_recording") val sourceRecording: OfflineSourceRecording? = null,
    val frames: List<OfflineFrameEntry>,
) {
    init {
        require(schemaVersion == CURRENT_SCHEMA_VERSION) {
            "Unsupported offline dataset schema version: $schemaVersion"
        }
        require(datasetId.isNotBlank()) { "dataset_id must not be blank" }
        require(frames.isNotEmpty()) { "offline dataset must contain at least one frame" }
        require(frames.map { it.caseId }.distinct().size == frames.size) {
            "offline dataset contains duplicate case_id values"
        }
    }

    companion object {
        const val CURRENT_SCHEMA_VERSION = 1
    }
}

@Serializable
data class OfflineSourceRecording(
    @SerialName("video_path") val videoPath: String,
    @SerialName("telemetry_path") val telemetryPath: String,
    @SerialName("video_sha256") val videoSha256: String,
    @SerialName("telemetry_sha256") val telemetrySha256: String,
    @SerialName("telemetry_origin_elapsed_realtime_ms")
    val telemetryOriginElapsedRealtimeMillis: Long,
    @SerialName("duration_ms") val durationMillis: Long,
    @SerialName("sample_interval_ms") val sampleIntervalMillis: Long,
    @SerialName("sync_strategy") val syncStrategy: String,
    @SerialName("estimated_sync_error_ms") val estimatedSyncErrorMillis: Long,
    @SerialName("privacy_status") val privacyStatus: String = "unreviewed",
    @SerialName("consent_reference") val consentReference: String? = null,
) {
    init {
        require(videoPath.isNotBlank() && telemetryPath.isNotBlank())
        require(videoSha256.matches(SHA256)) { "video_sha256 must be a lowercase SHA-256 digest" }
        require(telemetrySha256.matches(SHA256)) {
            "telemetry_sha256 must be a lowercase SHA-256 digest"
        }
        require(telemetryOriginElapsedRealtimeMillis >= 0)
        require(durationMillis >= 0)
        require(sampleIntervalMillis > 0)
        require(syncStrategy.isNotBlank())
        require(estimatedSyncErrorMillis >= 0)
        require(privacyStatus in setOf("unreviewed", "redacted", "approved"))
        require(consentReference == null || consentReference.isNotBlank())
    }

    private companion object {
        val SHA256 = Regex("[0-9a-f]{64}")
    }
}

@Serializable
data class OfflineFrameEntry(
    @SerialName("case_id") val caseId: String,
    @SerialName("image_path") val imagePath: String? = null,
    @SerialName("video_path") val videoPath: String? = null,
    @SerialName("video_position_ms") val videoPositionMillis: Long? = null,
    @SerialName("timestamp_nanos") val timestampNanos: Long,
    @SerialName("rotation_degrees") val rotationDegrees: Int = 0,
    val context: OfflineFrameContext = OfflineFrameContext(),
    val annotations: List<OfflineAnnotation> = emptyList(),
    val segmentation: OfflineSegmentationAnnotation? = null,
) {
    init {
        require(caseId.isNotBlank()) { "case_id must not be blank" }
        require((imagePath != null) xor (videoPath != null)) {
            "exactly one of image_path or video_path must be set"
        }
        require(imagePath == null || imagePath.isNotBlank()) { "image_path must not be blank" }
        require(videoPath == null || videoPath.isNotBlank()) { "video_path must not be blank" }
        require(videoPath == null || videoPositionMillis != null) {
            "video_position_ms is required with video_path"
        }
        require(videoPositionMillis == null || videoPositionMillis >= 0) {
            "video_position_ms must be non-negative"
        }
        require(timestampNanos >= 0) { "timestamp_nanos must be non-negative" }
        require(rotationDegrees in SUPPORTED_ROTATIONS) {
            "rotation_degrees must be one of $SUPPORTED_ROTATIONS"
        }
    }

    private companion object {
        val SUPPORTED_ROTATIONS = setOf(0, 90, 180, 270)
    }
}

@Serializable
data class OfflineFrameContext(
    @SerialName("session_id") val sessionId: String? = null,
    @SerialName("tracking_quality") val trackingQuality: String? = null,
    @SerialName("depth_active") val depthActive: Boolean? = null,
    @SerialName("route_aligned") val routeAligned: Boolean? = null,
    @SerialName("tracking_loss_count") val trackingLossCount: Int? = null,
    @SerialName("last_recovery_ms") val lastRecoveryMillis: Long? = null,
    @SerialName("ar_frame_time_ms") val arFrameTimeMillis: Float? = null,
    @SerialName("telemetry_offset_ms") val telemetryOffsetMillis: Long? = null,
    val message: String? = null,
) {
    init {
        require(sessionId == null || sessionId.isNotBlank())
        require(trackingQuality == null || trackingQuality.isNotBlank())
        require(trackingLossCount == null || trackingLossCount >= 0)
        require(lastRecoveryMillis == null || lastRecoveryMillis >= 0)
        require(arFrameTimeMillis == null || (arFrameTimeMillis.isFinite() && arFrameTimeMillis >= 0f))
    }
}

@Serializable
data class OfflineAnnotation(
    val label: String,
    @SerialName("instance_id") val instanceId: String? = null,
    val left: Float,
    val top: Float,
    val right: Float,
    val bottom: Float,
) {
    init {
        require(label.isNotBlank()) { "annotation label must not be blank" }
        require(instanceId == null || instanceId.isNotBlank()) {
            "annotation instance_id must not be blank"
        }
        NormalizedRegion(left, top, right, bottom)
    }

    fun toGroundTruth(): GroundTruthRegion = GroundTruthRegion(
        label = label,
        bounds = NormalizedRegion(left, top, right, bottom),
        instanceId = instanceId,
    )
}

@Serializable
data class OfflineSegmentationAnnotation(
    @SerialName("mask_path") val maskPath: String,
    val labels: Map<Int, String>,
) {
    init {
        require(maskPath.isNotBlank())
        require(labels.isNotEmpty())
        require(labels.keys.all { it in 0..255 })
        require(labels.values.all { it.isNotBlank() })
    }
}

data class OfflineSegmentationGroundTruth(
    val maskFile: File,
    val labels: Map<Int, String>,
)

data class OfflineDataset(
    val datasetId: String,
    val cases: List<OfflineFrameCase>,
    val sourceRecording: OfflineSourceRecording? = null,
)

sealed interface OfflineFrameSource {
    val file: File

    data class Image(override val file: File) : OfflineFrameSource

    data class Video(
        override val file: File,
        val positionMillis: Long,
    ) : OfflineFrameSource
}

fun interface OfflineFrameDecoder {
    fun open(
        source: OfflineFrameSource,
        stamp: FrameStamp,
        rotationDegrees: Int,
    ): PerceptionFrameLease
}

fun interface OfflineRecordingValidator {
    fun validate(
        datasetRoot: File,
        source: OfflineSourceRecording,
        maximumVideoPositionMillis: Long,
    )
}

object Sha256OfflineRecordingValidator : OfflineRecordingValidator {
    override fun validate(
        datasetRoot: File,
        source: OfflineSourceRecording,
        maximumVideoPositionMillis: Long,
    ) {
        val video = resolveInside(datasetRoot, source.videoPath)
        val telemetry = resolveInside(datasetRoot, source.telemetryPath)
        require(video.isFile && telemetry.isFile) { "source recording files are missing" }
        require(video.sha256() == source.videoSha256) { "source video SHA-256 does not match manifest" }
        require(telemetry.sha256() == source.telemetrySha256) {
            "source telemetry SHA-256 does not match manifest"
        }
        require(maximumVideoPositionMillis <= source.durationMillis) {
            "manifest frame position exceeds source recording duration"
        }
    }

    private fun resolveInside(root: File, relativePath: String): File {
        require(!File(relativePath).isAbsolute)
        val resolved = File(root, relativePath).canonicalFile
        require(resolved.isInside(root))
        return resolved
    }

    private fun File.sha256(): String {
        val digest = java.security.MessageDigest.getInstance("SHA-256")
        inputStream().buffered().use { stream ->
            val buffer = ByteArray(DEFAULT_BUFFER_SIZE)
            while (true) {
                val count = stream.read(buffer)
                if (count < 0) break
                digest.update(buffer, 0, count)
            }
        }
        return digest.digest().joinToString("") { "%02x".format(it) }
    }
}

object OfflineManifestCodec {
    private val json = Json {
        ignoreUnknownKeys = false
        isLenient = false
    }

    fun decode(content: String): OfflineDatasetManifest =
        json.decodeFromString(OfflineDatasetManifest.serializer(), content)
}

class ManifestOfflineDatasetLoader(
    private val decoder: OfflineFrameDecoder,
    private val recordingValidator: OfflineRecordingValidator = Sha256OfflineRecordingValidator,
) {
    fun load(manifestFile: File): OfflineDataset {
        require(manifestFile.isFile) { "Manifest does not exist: $manifestFile" }
        val manifest = OfflineManifestCodec.decode(manifestFile.readText(Charsets.UTF_8))
        val root = requireNotNull(manifestFile.canonicalFile.parentFile) {
            "Manifest must have a parent directory"
        }
        manifest.sourceRecording?.let { source ->
            val videoEntries = manifest.frames.filter { it.videoPath != null }
            require(videoEntries.all { it.videoPath == source.videoPath }) {
                "all recorded video frames must reference source_recording.video_path"
            }
            recordingValidator.validate(
                datasetRoot = root,
                source = source,
                maximumVideoPositionMillis = videoEntries.maxOfOrNull {
                    requireNotNull(it.videoPositionMillis)
                } ?: 0L,
            )
        }

        val cases = manifest.frames.mapIndexed { index, entry ->
            val source = when {
                entry.imagePath != null -> OfflineFrameSource.Image(
                    resolveInside(root, entry.imagePath),
                )
                entry.videoPath != null -> OfflineFrameSource.Video(
                    file = resolveInside(root, entry.videoPath),
                    positionMillis = requireNotNull(entry.videoPositionMillis),
                )
                else -> error("manifest source validation was bypassed")
            }
            OfflineFrameCase(
                caseId = entry.caseId,
                openFrame = {
                    decoder.open(
                        source = source,
                        stamp = FrameStamp(index.toLong(), entry.timestampNanos),
                        rotationDegrees = entry.rotationDegrees,
                    )
                },
                expected = entry.annotations.map(OfflineAnnotation::toGroundTruth),
                context = entry.context,
                segmentation = entry.segmentation?.let {
                    OfflineSegmentationGroundTruth(
                        maskFile = resolveInside(root, it.maskPath),
                        labels = it.labels,
                    )
                },
            )
        }
        return OfflineDataset(manifest.datasetId, cases, manifest.sourceRecording)
    }

    private fun resolveInside(root: File, relativePath: String): File {
        require(!File(relativePath).isAbsolute) { "dataset path must be relative: $relativePath" }
        val resolved = File(root, relativePath).canonicalFile
        require(resolved.isInside(root)) {
            "dataset path escapes the dataset directory: $relativePath"
        }
        return resolved
    }
}

private fun File.isInside(directory: File): Boolean {
    val rootPath = directory.canonicalFile.path.trimEnd(File.separatorChar)
    val candidatePath = canonicalFile.path
    return candidatePath == rootPath || candidatePath.startsWith(rootPath + File.separator)
}
