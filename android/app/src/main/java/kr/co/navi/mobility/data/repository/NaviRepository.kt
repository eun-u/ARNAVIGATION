package kr.co.navi.mobility.data.repository

import kr.co.navi.mobility.data.model.CoordinateDto
import kr.co.navi.mobility.data.model.GraphEnrichmentCatalogDto
import kr.co.navi.mobility.data.model.GraphEnrichmentSimulationResponseDto
import kr.co.navi.mobility.data.model.NaviBootstrap
import kr.co.navi.mobility.data.model.ObservationCandidateDto
import kr.co.navi.mobility.data.model.RouteComparisonDto
import kr.co.navi.mobility.data.model.SessionRerouteResponseDto

interface NaviRepository {
    suspend fun bootstrap(): NaviBootstrap

    suspend fun compareRoute(
        origin: CoordinateDto,
        destination: CoordinateDto,
        profile: String,
    ): RouteComparisonDto

    suspend fun rerouteSession(
        sessionId: String,
        edgeId: String,
        reason: String,
    ): SessionRerouteResponseDto

    suspend fun createObservation(
        sessionId: String,
        edgeId: String,
        type: String,
        note: String?,
        coordinate: CoordinateDto?,
    ): ObservationCandidateDto

    suspend fun graphEnrichmentCatalog(): GraphEnrichmentCatalogDto

    suspend fun simulateGraphCandidate(
        origin: CoordinateDto,
        destination: CoordinateDto,
        profile: String,
        candidateId: String,
    ): GraphEnrichmentSimulationResponseDto
}
