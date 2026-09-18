package kr.co.navi.mobility.data

import kr.co.navi.mobility.data.model.CoordinateDto
import kr.co.navi.mobility.data.model.CoverageBounds
import kr.co.navi.mobility.data.model.NamedCoordinate
import kr.co.navi.mobility.data.model.NaviBootstrap
import kr.co.navi.mobility.data.model.ProvenanceSummaryDto
import kr.co.navi.mobility.data.model.RouteComparisonDto
import kr.co.navi.mobility.data.model.RouteResultDto
import kr.co.navi.mobility.data.model.SessionRerouteResponseDto
import kr.co.navi.mobility.guidance.contract.GeoCoordinate
import kr.co.navi.mobility.guidance.contract.forwardRouteBearing
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class NaviSessionStoreTest {
    @Test
    fun `bootstrap selects declared demo endpoints`() {
        val store = NaviSessionStore()
        val bootstrap = bootstrap()

        store.setBootstrap(bootstrap)

        assertEquals(bootstrap.origin.coordinate, store.state.value.origin)
        assertEquals(bootstrap.destination.coordinate, store.state.value.destination)
    }

    @Test
    fun `session reroute replaces only active route and records evidence`() {
        val store = NaviSessionStore()
        val before = route(distance = 940.0, edgeIds = listOf("E01", "E15"))
        val standard = route(distance = 820.0, edgeIds = listOf("E01", "E02"), type = "standard")
        val comparison = RouteComparisonDto(
            standard = standard,
            accessible = before,
            differenceM = 120.0,
            differencePct = 14.6,
            sessionId = "S01",
        )
        val after = route(distance = 1_087.0, edgeIds = listOf("E01", "E20"))
        val reroute = SessionRerouteResponseDto(
            status = "rerouted",
            sessionId = "S01",
            temporaryBlockedEdgeIds = listOf("E15"),
            graphRevision = 1,
            routeAffected = true,
            routeChanged = true,
            previousRoute = before,
            recalculatedRoute = after,
            comparison = comparison.copy(accessible = after, differenceM = 267.0),
        )

        store.setComparison(comparison)
        store.applyReroute(reroute)

        assertEquals(after, store.state.value.activeRoute)
        assertEquals(listOf("E15"), store.state.value.reroute?.temporaryBlockedEdgeIds)
        assertNull(store.state.value.observation)
    }

    @Test
    fun `session reroute immediately changes the forward bearing at the branch`() {
        val store = NaviSessionStore()
        val branch = GeoCoordinate(latitude = 35.0, longitude = 127.0001)
        val sharedStart = listOf(127.0, 35.0)
        val sharedBranch = listOf(127.0001, 35.0)
        val before = route(
            distance = 130.7,
            edgeIds = listOf("APPROACH", "BLOCK"),
            geometry = listOf(sharedStart, sharedBranch, listOf(127.0002, 35.0)),
        )
        val after = route(
            distance = 153.5,
            edgeIds = listOf("APPROACH", "DETOUR"),
            geometry = listOf(sharedStart, sharedBranch, listOf(127.0001, 35.0001)),
        )
        val comparison = RouteComparisonDto(
            standard = before,
            accessible = before,
            differenceM = 0.0,
            differencePct = 0.0,
            sessionId = "S-E2E",
        )
        val reroute = SessionRerouteResponseDto(
            status = "rerouted",
            sessionId = "S-E2E",
            temporaryBlockedEdgeIds = listOf("BLOCK"),
            graphRevision = 1,
            routeAffected = true,
            routeChanged = true,
            previousRoute = before,
            recalculatedRoute = after,
            comparison = comparison.copy(accessible = after),
        )

        store.setComparison(comparison)
        val beforeBearing = forwardRouteBearing(store.state.value.activeRoute!!.geometry, branch)
        store.applyReroute(reroute)
        val afterBearing = forwardRouteBearing(store.state.value.activeRoute!!.geometry, branch)

        requireNotNull(beforeBearing)
        requireNotNull(afterBearing)
        assertTrue(beforeBearing in 89f..91f)
        assertTrue(afterBearing < 1f || afterBearing > 359f)
    }

    private fun bootstrap(): NaviBootstrap = NaviBootstrap(
        areaName = "테스트 구역",
        source = "synthetic",
        accessibilityAttributes = "synthetic",
        disclaimer = "실험 데이터",
        origin = NamedCoordinate("A", "출발", CoordinateDto(37.0, 126.0)),
        destination = NamedCoordinate("B", "도착", CoordinateDto(37.01, 126.01)),
        blockEdgeId = "E15",
        blockEdgeGeometry = listOf(listOf(126.0, 37.0), listOf(126.01, 37.01)),
        coverageBounds = CoverageBounds(36.99, 125.99, 37.02, 126.02),
    )

    private fun route(
        distance: Double,
        edgeIds: List<String>,
        type: String = "accessible",
        geometry: List<List<Double>> = listOf(listOf(126.0, 37.0), listOf(126.01, 37.01)),
    ): RouteResultDto = RouteResultDto(
        distanceM = distance,
        estimatedMinutes = 12,
        routeType = type,
        profile = "wheelchair",
        originNode = "A",
        destinationNode = "B",
        edgeIds = edgeIds,
        geometry = geometry,
        provenance = ProvenanceSummaryDto(sources = listOf("synthetic"), containsSynthetic = true),
    )
}
