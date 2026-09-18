package kr.co.navi.mobility.ui.components

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithText
import kr.co.navi.mobility.data.model.GraphEnrichmentCandidateDto
import kr.co.navi.mobility.data.model.GraphEnrichmentSimulationResponseDto
import kr.co.navi.mobility.data.model.OrthophotoEvidenceRefDto
import kr.co.navi.mobility.data.model.ProvenanceSummaryDto
import kr.co.navi.mobility.data.model.RouteResultDto
import kr.co.navi.mobility.ui.screens.GraphCandidateEvidencePanel
import kr.co.navi.mobility.ui.screens.GraphCandidateSimulationPanel
import kr.co.navi.mobility.ui.theme.NaviTheme
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonPrimitive
import org.junit.Rule
import org.junit.Test

class NaviComponentsTest {
    @get:Rule
    val composeRule = createComposeRule()

    @Test
    fun primaryActionExposesItsVisibleLabel() {
        composeRule.setContent {
            NaviTheme {
                PrimaryActionButton("접근 가능한 길 찾기", onClick = {})
            }
        }

        composeRule.onNodeWithText("접근 가능한 길 찾기").assertIsDisplayed()
    }

    @Test
    fun graphCandidateSimulationDisclosesReadOnlyStatus() {
        val candidate = candidate()
        val baseline = route(98.1, listOf("E15"))
        val simulation = GraphEnrichmentSimulationResponseDto(
            status = "ok",
            candidateIds = listOf("GEC-01"),
            appliedEdgeIds = listOf("E15"),
            baselineCandidateEdgeIds = listOf("E15"),
            baseline = baseline,
            simulated = route(212.2, listOf("E20")),
            routeChanged = true,
            differenceM = 114.1,
            graphRevision = 7,
            graphMutated = false,
            databaseMutated = false,
        )
        composeRule.setContent {
            NaviTheme {
                GraphCandidateSimulationPanel(
                    candidate = candidate,
                    simulation = simulation,
                    loading = false,
                )
            }
        }

        composeRule.onNodeWithText("후보 영향 시뮬레이션").assertIsDisplayed()
        composeRule.onNodeWithText("+114m 우회").assertIsDisplayed()
        composeRule.onNodeWithText("공유 Graph 변경 없음 · SQLite 변경 없음").assertIsDisplayed()
    }

    @Test
    fun graphCandidateEvidenceShowsProvenanceAndProposedChange() {
        composeRule.setContent {
            NaviTheme {
                GraphCandidateEvidencePanel(candidate())
            }
        }

        composeRule.onNodeWithText("선택 후보 근거").assertIsDisplayed()
        composeRule.onNodeWithText("계단 false → true").assertIsDisplayed()
        composeRule.onNodeWithText("2025 제작 · 도엽 37612047 · 객체코드 C0390000").assertIsDisplayed()
        composeRule.onNodeWithText("Edge 매칭 거리 2.77m · 매칭 점수 0.396").assertIsDisplayed()
        composeRule.onNodeWithText("승인 전에는 공유 Graph에 반영할 수 없습니다.").assertIsDisplayed()
        composeRule.onNodeWithText("도엽 37612047 · pixel 200, 100").assertIsDisplayed()
        composeRule.onNodeWithText("형상 자동 보정 불가 · Graph 반영 불가").assertIsDisplayed()
    }

    @Test
    fun demSlopeCandidateDisclosesDiagnosticOnlyBoundary() {
        val diagnostic = candidate().copy(
            type = "dem_slope_diagnostic_candidate",
            candidateClass = "diagnostic_sensitivity",
            approvalEligible = false,
            qualityFlags = listOf("coarse_90m_dem", "not_hard_constraint_eligible"),
            proposedChanges = JsonObject(mapOf("slope" to JsonPrimitive(9.25))),
            currentValues = JsonObject(mapOf("slope" to JsonNull)),
        )
        composeRule.setContent {
            NaviTheme {
                GraphCandidateSimulationPanel(
                    candidate = diagnostic,
                    simulation = null,
                    loading = false,
                )
            }
        }

        composeRule.onNodeWithText(
            "민감도 시험 전용 · 이 경사값은 현장 보도 경사로 승인하거나 공유 Graph에 저장하지 않습니다.",
        ).assertIsDisplayed()
    }

    private fun candidate() = GraphEnrichmentCandidateDto(
        candidateId = "GEC-01",
        edgeId = "E15",
        type = "stairs_attribute_candidate",
        source = "spatial_evaluation_candidate",
        status = "pending",
        verified = false,
        graphUpdateAllowed = false,
        requiresHumanReview = true,
        priority = "high",
        routingImpact = "wheelchair_edge_exclusion_after_approval",
        mappingStatus = "unique",
        mappingQuality = "single_source_unique_match",
        candidateClass = "routing_attribute",
        simulationAllowed = true,
        approvalEligible = true,
        proposedChanges = JsonObject(mapOf("stairs" to JsonPrimitive(true))),
        currentValues = JsonObject(mapOf("stairs" to JsonPrimitive(false))),
        evidenceCount = 1,
        sourceTypes = listOf("ngii_topographic_map"),
        evidence = listOf(
            JsonObject(
                mapOf(
                    "source_type" to JsonPrimitive("ngii_topographic_map"),
                    "source_dataset_id" to JsonPrimitive("ngii_digital_topographic_map_anyang_corridor_20260917"),
                    "source_feature_id" to JsonPrimitive("1000037612047C03910000000000000111"),
                    "source_feature_code" to JsonPrimitive("C0390000"),
                    "mapping_distance_m" to JsonPrimitive(2.771062),
                    "mapping_score" to JsonPrimitive(0.395665),
                    "source_sheet_id" to JsonPrimitive("37612047"),
                    "source_year" to JsonPrimitive(2025),
                ),
            ),
        ),
        visualEvidenceRefs = listOf(
            OrthophotoEvidenceRefDto(
                referenceId = "ORTHO-GEC-01-37612047",
                sheetId = "37612047",
                pixelRow = 100,
                pixelCol = 200,
                referenceStatus = "visual_qa_only_provisional_georeferencing",
                allowedUse = "human_visual_spatial_qa",
            ),
        ),
        lat = 37.4,
        lon = 126.9,
        createdAt = "2026-09-18T09:26:23+09:00",
    )

    private fun route(distance: Double, edgeIds: List<String>) = RouteResultDto(
        distanceM = distance,
        estimatedMinutes = 2,
        routeType = "accessible",
        profile = "wheelchair",
        originNode = "A",
        destinationNode = "B",
        edgeIds = edgeIds,
        geometry = listOf(listOf(126.9, 37.4), listOf(126.901, 37.401)),
        provenance = ProvenanceSummaryDto(sources = listOf("osm")),
    )
}
