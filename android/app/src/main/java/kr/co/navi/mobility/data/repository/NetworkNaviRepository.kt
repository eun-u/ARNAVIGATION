package kr.co.navi.mobility.data.repository

import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.TimeZone
import kr.co.navi.mobility.data.model.CoordinateDto
import kr.co.navi.mobility.data.model.NaviBootstrap
import kr.co.navi.mobility.data.model.ObservationCandidateCreateDto
import kr.co.navi.mobility.data.model.ObservationCandidateDto
import kr.co.navi.mobility.data.model.RouteComparisonDto
import kr.co.navi.mobility.data.model.RouteRequestDto
import kr.co.navi.mobility.data.model.SessionRerouteRequestDto
import kr.co.navi.mobility.data.model.SessionRerouteResponseDto
import kr.co.navi.mobility.data.model.toBootstrap
import kr.co.navi.mobility.data.remote.NaviApiClient

class NetworkNaviRepository(
    private val api: NaviApiClient,
) : NaviRepository {
    override suspend fun bootstrap(): NaviBootstrap = api.getGraph().toBootstrap()

    override suspend fun compareRoute(
        origin: CoordinateDto,
        destination: CoordinateDto,
        profile: String,
    ): RouteComparisonDto = api.compareRoute(
        RouteRequestDto(origin = origin, destination = destination, profile = profile),
    )

    override suspend fun rerouteSession(
        sessionId: String,
        edgeId: String,
        reason: String,
    ): SessionRerouteResponseDto = api.reroute(
        sessionId,
        SessionRerouteRequestDto(
            temporaryBlockedEdgeIds = listOf(edgeId),
            reason = reason,
        ),
    )

    override suspend fun createObservation(
        sessionId: String,
        edgeId: String,
        type: String,
        note: String?,
        coordinate: CoordinateDto?,
    ): ObservationCandidateDto = api.createCandidate(
        ObservationCandidateCreateDto(
            edgeId = edgeId,
            type = type,
            source = "manual_camera",
            sessionId = sessionId,
            observedAt = utcTimestamp(),
            note = note,
            lat = coordinate?.lat,
            lon = coordinate?.lon,
        ),
    )

    private fun utcTimestamp(): String = SimpleDateFormat(
        "yyyy-MM-dd'T'HH:mm:ss.SSS'Z'",
        Locale.US,
    ).apply {
        timeZone = TimeZone.getTimeZone("UTC")
    }.format(Date())
}
