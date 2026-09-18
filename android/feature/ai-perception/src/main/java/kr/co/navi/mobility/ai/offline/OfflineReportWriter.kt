package kr.co.navi.mobility.ai.offline

import java.io.File
import kotlinx.serialization.Serializable
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json

@Serializable
data class OfflineRunReport(
    val schemaVersion: Int = 2,
    val datasetId: String,
    val sourceRecording: OfflineSourceRecording? = null,
    val evaluation: OfflineEvaluationReport,
    val regression: OfflineRegressionResult? = null,
) {
    init {
        require(datasetId.isNotBlank()) { "datasetId must not be blank" }
    }
}

data class OfflineRunArtifacts(
    val report: OfflineRunReport,
    val jsonFile: File,
    val csvFile: File,
    val framesCsvFile: File,
)

object OfflineReportWriter {
    private val json = Json {
        prettyPrint = true
        encodeDefaults = true
    }

    fun toJson(report: OfflineRunReport): String = json.encodeToString(report)

    fun toCsv(report: OfflineRunReport): String = buildString {
        appendLine(
            "dataset_id,scope,label,true_positives,false_positives,false_negatives," +
                "precision,recall,f1,frame_count,evaluated_frame_count,failed_frame_count," +
                "latency_samples,latency_mean_ms,latency_p50_ms,latency_p95_ms,latency_max_ms",
        )
        appendMetricsRow(report, "overall", "", report.evaluation.overall)
        report.evaluation.byLabel.toSortedMap().forEach { (label, metrics) ->
            appendMetricsRow(report, "label", label, metrics)
        }
        report.evaluation.byContext.toSortedMap().forEach { (context, metrics) ->
            appendMetricsRow(report, "context", context, metrics)
        }
        report.evaluation.byObjectSize.toSortedMap().forEach { (size, metrics) ->
            appendMetricsRow(report, "object_size", size, metrics)
        }
    }

    fun toFramesCsv(report: OfflineRunReport): String = buildString {
        appendLine(
            "dataset_id,case_id,status,error,model_version,inference_ms,prediction_count," +
                "true_positives,false_positives,false_negatives,session_id,tracking_quality," +
                "depth_active,route_aligned,tracking_loss_count,ar_frame_time_ms," +
                "telemetry_offset_ms",
        )
        report.evaluation.frames.forEach { frame ->
            appendLine(
                listOf(
                    csv(report.datasetId),
                    csv(frame.caseId),
                    frame.status,
                    csv(frame.error.orEmpty()),
                    csv(frame.modelVersion.orEmpty()),
                    frame.inferenceMillis ?: "",
                    frame.predictions.size,
                    frame.metrics.truePositives,
                    frame.metrics.falsePositives,
                    frame.metrics.falseNegatives,
                    csv(frame.context.sessionId.orEmpty()),
                    csv(frame.context.trackingQuality.orEmpty()),
                    frame.context.depthActive ?: "",
                    frame.context.routeAligned ?: "",
                    frame.context.trackingLossCount ?: "",
                    frame.context.arFrameTimeMillis ?: "",
                    frame.context.telemetryOffsetMillis ?: "",
                ).joinToString(","),
            )
        }
    }

    fun write(
        report: OfflineRunReport,
        outputDirectory: File,
    ): OfflineRunArtifacts {
        require(outputDirectory.exists() || outputDirectory.mkdirs()) {
            "Could not create report directory: $outputDirectory"
        }
        require(outputDirectory.isDirectory) { "Report output is not a directory: $outputDirectory" }
        val baseName = report.datasetId.replace(Regex("[^A-Za-z0-9._-]"), "_")
        val jsonFile = File(outputDirectory, "$baseName-report.json")
        val csvFile = File(outputDirectory, "$baseName-metrics.csv")
        val framesCsvFile = File(outputDirectory, "$baseName-frames.csv")
        jsonFile.writeText(toJson(report), Charsets.UTF_8)
        csvFile.writeText(toCsv(report), Charsets.UTF_8)
        framesCsvFile.writeText(toFramesCsv(report), Charsets.UTF_8)
        return OfflineRunArtifacts(report, jsonFile, csvFile, framesCsvFile)
    }

    private fun StringBuilder.appendMetricsRow(
        report: OfflineRunReport,
        scope: String,
        label: String,
        metrics: DetectionMetrics,
    ) {
        val evaluation = report.evaluation
        val latency = evaluation.latency
        appendLine(
            listOf(
                csv(report.datasetId),
                scope,
                csv(label),
                metrics.truePositives,
                metrics.falsePositives,
                metrics.falseNegatives,
                metrics.precision,
                metrics.recall,
                metrics.f1,
                evaluation.frameCount,
                evaluation.evaluatedFrameCount,
                evaluation.failedFrames.size,
                latency.sampleCount,
                latency.meanMillis,
                latency.p50Millis,
                latency.p95Millis,
                latency.maxMillis,
            ).joinToString(","),
        )
    }

    private fun csv(value: String): String =
        if (value.any { it == ',' || it == '"' || it == '\n' || it == '\r' }) {
            "\"${value.replace("\"", "\"\"")}\""
        } else {
            value
        }
}

class OfflineEvaluationRunner(
    private val loader: ManifestOfflineDatasetLoader =
        ManifestOfflineDatasetLoader(
            decoder = AndroidMediaFrameDecoder(),
            recordingValidator = AndroidOfflineRecordingValidator(),
        ),
    private val harness: OfflineReplayHarness = OfflineReplayHarness(),
) {
    suspend fun run(
        manifestFile: File,
        outputDirectory: File,
        engine: kr.co.navi.mobility.ai.PerceptionEngine,
        regressionPolicy: OfflineRegressionPolicy? = null,
    ): OfflineRunArtifacts {
        val dataset = loader.load(manifestFile)
        val evaluation = harness.evaluate(dataset.cases, engine)
        val regression = regressionPolicy?.let { OfflineRegressionGate.evaluate(evaluation, it) }
        return OfflineReportWriter.write(
            report = OfflineRunReport(
                datasetId = dataset.datasetId,
                sourceRecording = dataset.sourceRecording,
                evaluation = evaluation,
                regression = regression,
            ),
            outputDirectory = outputDirectory,
        )
    }
}
