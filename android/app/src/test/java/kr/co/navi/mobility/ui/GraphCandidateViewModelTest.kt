package kr.co.navi.mobility.ui

import kr.co.navi.mobility.data.NaviSessionStore
import kr.co.navi.mobility.data.model.CoordinateDto
import kr.co.navi.mobility.data.model.CoverageBounds
import kr.co.navi.mobility.data.model.GraphEnrichmentCandidateDto
import kr.co.navi.mobility.data.model.GraphEnrichmentCatalogDto
import kr.co.navi.mobility.data.model.GraphEnrichmentSimulationResponseDto
import kr.co.navi.mobility.data.model.GraphEnrichmentSummaryDto
import kr.co.navi.mobility.data.model.NamedCoordinate
import kr.co.navi.mobility.data.model.NaviBootstrap
import kr.co.navi.mobility.data.model.ObservationCandidateDto
import kr.co.navi.mobility.data.model.ProvenanceSummaryDto
import kr.co.navi.mobility.data.model.RouteComparisonDto
import kr.co.navi.mobility.data.model.RouteResultDto
import kr.co.navi.mobility.data.model.SessionRerouteResponseDto
import kr.co.navi.mobility.data.repository.NaviRepository
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class GraphCandidateViewModelTest {
    @Test
    fun `candidate impacts preload from edge endpoints and selection reuses the result`() = runTest {
        Dispatchers.setMain(StandardTestDispatcher(testScheduler))
        try {
            val repository = FakeRepository()
            val store = NaviSessionStore().apply {
                setBootstrap(bootstrap())
                setProfile("wheelchair")
            }
            val viewModel = GraphCandidateViewModel(repository, store)
            advanceUntilIdle()

            assertEquals(1, viewModel.uiState.value.candidates.size)
            assertNull(viewModel.uiState.value.selectedCandidateId)
            assertEquals(1, repository.simulationCallCount)
            assertEquals(114.1, viewModel.uiState.value.simulationsByCandidateId["GEC-01"]?.differenceM ?: 0.0, 0.001)

            viewModel.selectCandidate("GEC-01")
            advanceUntilIdle()

            val state = viewModel.uiState.value
            assertEquals("GEC-01", state.selectedCandidateId)
            assertEquals(114.1, state.simulation?.differenceM ?: 0.0, 0.001)
            assertEquals(CoordinateDto(lat = 37.4, lon = 126.9), repository.lastOrigin)
            assertEquals(CoordinateDto(lat = 37.401, lon = 126.901), repository.lastDestination)
            assertEquals("wheelchair", repository.lastProfile)
            assertEquals(1, repository.simulationCallCount)
            assertFalse(state.simulation!!.graphMutated)
            assertFalse(state.simulation!!.databaseMutated)
        } finally {
            Dispatchers.resetMain()
        }
    }

    @Test
    fun `impact ranking prioritizes disconnected routes then larger detours`() {
        val disconnected = SIMULATION.copy(
            candidateIds = listOf("GEC-DISCONNECTED"),
            simulated = null,
            status = "no_accessible_route",
            differenceM = null,
        )
        val longDetour = SIMULATION.copy(
            candidateIds = listOf("GEC-LONG"),
            differenceM = 1_205.8,
        )
        val shortDetour = SIMULATION.copy(
            candidateIds = listOf("GEC-SHORT"),
            differenceM = 114.1,
        )
        val candidates = listOf(
            CANDIDATE.copy(candidateId = "GEC-SHORT"),
            CANDIDATE.copy(candidateId = "GEC-DISCONNECTED"),
            CANDIDATE.copy(candidateId = "GEC-LONG"),
        )

        val ranked = rankGraphCandidateImpacts(
            candidates,
            mapOf(
                "GEC-SHORT" to shortDetour,
                "GEC-DISCONNECTED" to disconnected,
                "GEC-LONG" to longDetour,
            ),
        )

        assertEquals(
            listOf("GEC-DISCONNECTED", "GEC-LONG", "GEC-SHORT"),
            ranked.map { it.candidate.candidateId },
        )
        assertTrue(ranked.first().simulation?.simulated == null)
    }

    @Test
    fun `candidate filters separate simulations from evidence map layers`() {
        val slope = CANDIDATE.copy(
            candidateId = "GEC-SLOPE",
            type = "dem_slope_diagnostic_candidate",
            candidateClass = "diagnostic_sensitivity",
            simulationAllowed = true,
            approvalEligible = false,
        )
        val pedestrian = CANDIDATE.copy(
            candidateId = "GEC-WALK",
            type = "pedestrian_area_evidence",
            candidateClass = "evidence_only",
            simulationAllowed = false,
            proposedChanges = JsonObject(emptyMap()),
        )
        val crossing = pedestrian.copy(
            candidateId = "GEC-CROSS",
            type = "crosswalk_geometry_evidence",
        )
        val curb = pedestrian.copy(
            candidateId = "GEC-CURB",
            type = "curb_presence_evidence",
        )
        val candidates = listOf(CANDIDATE, slope, pedestrian, crossing, curb)

        assertEquals(
            listOf("GEC-01", "GEC-SLOPE"),
            filterGraphCandidates(candidates, GraphCandidateFilter.IMPACT).map { it.candidateId },
        )
        assertEquals(
            listOf("GEC-WALK"),
            filterGraphCandidates(candidates, GraphCandidateFilter.PEDESTRIAN).map { it.candidateId },
        )
        assertEquals(
            listOf("GEC-CROSS"),
            filterGraphCandidates(candidates, GraphCandidateFilter.CROSSING).map { it.candidateId },
        )
        assertEquals(
            listOf("GEC-CURB"),
            filterGraphCandidates(candidates, GraphCandidateFilter.CURB).map { it.candidateId },
        )
    }

    @Test
    fun `candidate preload retries a transient simulation failure once`() = runTest {
        Dispatchers.setMain(StandardTestDispatcher(testScheduler))
        try {
            val repository = FakeRepository(mutableSetOf("GEC-01"))
            val store = NaviSessionStore().apply {
                setBootstrap(bootstrap())
                setProfile("wheelchair")
            }

            val viewModel = GraphCandidateViewModel(repository, store)
            advanceUntilIdle()

            assertEquals(2, repository.simulationCallCount)
            assertTrue(viewModel.uiState.value.rankingFailedCandidateIds.isEmpty())
            assertEquals(
                114.1,
                viewModel.uiState.value.simulationsByCandidateId["GEC-01"]?.differenceM ?: 0.0,
                0.001,
            )
        } finally {
            Dispatchers.resetMain()
        }
    }

    private fun bootstrap(): NaviBootstrap = NaviBootstrap(
        areaName = "안양 대표회랑",
        source = "osm",
        accessibilityAttributes = "mixed",
        disclaimer = "현장 검증 필요",
        origin = NamedCoordinate("A", "출발", CoordinateDto(37.4, 126.9)),
        destination = NamedCoordinate("B", "도착", CoordinateDto(37.401, 126.901)),
        blockEdgeId = "E15",
        blockEdgeGeometry = EDGE_GEOMETRY,
        coverageBounds = CoverageBounds(37.39, 126.89, 37.41, 126.91),
        edgeGeometries = mapOf("E15" to EDGE_GEOMETRY),
    )

    private class FakeRepository(
        private val failFirstCandidateIds: MutableSet<String> = mutableSetOf(),
    ) : NaviRepository {
        var lastOrigin: CoordinateDto? = null
        var lastDestination: CoordinateDto? = null
        var lastProfile: String? = null
        var simulationCallCount: Int = 0

        override suspend fun graphEnrichmentCatalog(): GraphEnrichmentCatalogDto =
            GraphEnrichmentCatalogDto(
                summary = GraphEnrichmentSummaryDto(
                    available = true,
                    candidateCount = 235,
                    candidateEdgeCount = 192,
                    routeAffectingCandidateCount = 5,
                    evidenceOnlyCandidateCount = 230,
                    allPending = true,
                    allUnverified = true,
                    graphUpdateAllowed = false,
                ),
                candidates = listOf(CANDIDATE),
            )

        override suspend fun simulateGraphCandidate(
            origin: CoordinateDto,
            destination: CoordinateDto,
            profile: String,
            candidateId: String,
        ): GraphEnrichmentSimulationResponseDto {
            simulationCallCount++
            lastOrigin = origin
            lastDestination = destination
            lastProfile = profile
            if (failFirstCandidateIds.remove(candidateId)) {
                error("transient simulation failure")
            }
            return SIMULATION
        }

        override suspend fun bootstrap(): NaviBootstrap = error("not used")

        override suspend fun compareRoute(
            origin: CoordinateDto,
            destination: CoordinateDto,
            profile: String,
        ): RouteComparisonDto = error("not used")

        override suspend fun rerouteSession(
            sessionId: String,
            edgeId: String,
            reason: String,
        ): SessionRerouteResponseDto = error("not used")

        override suspend fun createObservation(
            sessionId: String,
            edgeId: String,
            type: String,
            note: String?,
            coordinate: CoordinateDto?,
        ): ObservationCandidateDto = error("not used")
    }

    companion object {
        private val EDGE_GEOMETRY = listOf(
            listOf(126.9, 37.4),
            listOf(126.901, 37.401),
        )
        private val CANDIDATE = GraphEnrichmentCandidateDto(
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
                        "source_year" to JsonPrimitive(2025),
                        "mapping_distance_m" to JsonPrimitive(2.77),
                    ),
                ),
            ),
            lat = 37.4005,
            lon = 126.9005,
            createdAt = "2026-09-18T09:26:23+09:00",
        )
        private val BASELINE = route(98.1, listOf("E15"))
        private val SIMULATED = route(212.2, listOf("E20"))
        private val SIMULATION = GraphEnrichmentSimulationResponseDto(
            status = "ok",
            candidateIds = listOf("GEC-01"),
            appliedEdgeIds = listOf("E15"),
            baselineCandidateEdgeIds = listOf("E15"),
            baseline = BASELINE,
            simulated = SIMULATED,
            routeChanged = true,
            differenceM = 114.1,
            graphRevision = 7,
            graphMutated = false,
            databaseMutated = false,
        )

        private fun route(distance: Double, edges: List<String>) = RouteResultDto(
            distanceM = distance,
            estimatedMinutes = 2,
            routeType = "accessible",
            profile = "wheelchair",
            originNode = "A",
            destinationNode = "B",
            edgeIds = edges,
            geometry = EDGE_GEOMETRY,
            provenance = ProvenanceSummaryDto(sources = listOf("osm")),
        )
    }
}
