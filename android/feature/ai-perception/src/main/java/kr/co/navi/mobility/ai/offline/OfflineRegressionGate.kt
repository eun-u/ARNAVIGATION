package kr.co.navi.mobility.ai.offline

import kotlinx.serialization.Serializable

@Serializable
data class OfflineRegressionPolicy(
    val minimumOverallPrecision: Double = 0.0,
    val minimumOverallRecall: Double = 0.0,
    val minimumRecallByLabel: Map<String, Double> = emptyMap(),
    val maximumP95LatencyMillis: Long = Long.MAX_VALUE,
    val maximumFailedFrames: Int = 0,
) {
    init {
        require(minimumOverallPrecision in 0.0..1.0)
        require(minimumOverallRecall in 0.0..1.0)
        require(minimumRecallByLabel.values.all { it in 0.0..1.0 })
        require(maximumP95LatencyMillis >= 0)
        require(maximumFailedFrames >= 0)
    }
}

@Serializable
data class OfflineRegressionResult(
    val passed: Boolean,
    val violations: List<String>,
)

object OfflineRegressionGate {
    fun evaluate(
        report: OfflineEvaluationReport,
        policy: OfflineRegressionPolicy,
    ): OfflineRegressionResult {
        val violations = buildList {
            if (report.overall.precision < policy.minimumOverallPrecision) {
                add(
                    "overall precision ${report.overall.precision} is below " +
                        policy.minimumOverallPrecision,
                )
            }
            if (report.overall.recall < policy.minimumOverallRecall) {
                add("overall recall ${report.overall.recall} is below ${policy.minimumOverallRecall}")
            }
            policy.minimumRecallByLabel.toSortedMap().forEach { (label, minimumRecall) ->
                val metrics = report.byLabel[label]
                if (metrics == null) {
                    add("required label '$label' is missing from the report")
                } else if (metrics.recall < minimumRecall) {
                    add("recall for '$label' ${metrics.recall} is below $minimumRecall")
                }
            }
            if (report.latency.p95Millis > policy.maximumP95LatencyMillis) {
                add(
                    "p95 latency ${report.latency.p95Millis}ms exceeds " +
                        "${policy.maximumP95LatencyMillis}ms",
                )
            }
            if (report.failedFrames.size > policy.maximumFailedFrames) {
                add(
                    "failed frame count ${report.failedFrames.size} exceeds " +
                        policy.maximumFailedFrames,
                )
            }
        }
        return OfflineRegressionResult(passed = violations.isEmpty(), violations = violations)
    }
}
