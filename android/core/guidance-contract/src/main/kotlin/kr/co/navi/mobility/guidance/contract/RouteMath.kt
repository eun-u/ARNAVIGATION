package kr.co.navi.mobility.guidance.contract

import kotlin.math.PI
import kotlin.math.abs
import kotlin.math.atan2
import kotlin.math.cos
import kotlin.math.hypot
import kotlin.math.sin

fun bearingDegrees(from: List<Double>, to: List<Double>): Float {
    require(from.size >= 2 && to.size >= 2)
    val lon1 = from[0] * PI / 180.0
    val lat1 = from[1] * PI / 180.0
    val lon2 = to[0] * PI / 180.0
    val lat2 = to[1] * PI / 180.0
    val y = sin(lon2 - lon1) * cos(lat2)
    val x = cos(lat1) * sin(lat2) - sin(lat1) * cos(lat2) * cos(lon2 - lon1)
    return ((Math.toDegrees(atan2(y, x)) + 360.0) % 360.0).toFloat()
}

fun normalizeHeadingDelta(routeBearing: Float, deviceHeading: Float): Float =
    ((routeBearing - deviceHeading + 540f) % 360f) - 180f

fun routeBearing(geometry: List<List<Double>>): Float? =
    geometry.zipWithNext()
        .firstOrNull { (from, to) -> from != to }
        ?.let { (from, to) -> bearingDegrees(from, to) }

data class RouteSegmentMatch(
    val segmentIndex: Int,
    val fraction: Double,
    val lateralErrorMeters: Double,
    val bearingDegrees: Float,
)

/**
 * Finds the route segment nearest to [user] without depending on an AR or map SDK.
 *
 * When the user is exactly on a shared vertex, the later segment wins the tie so
 * guidance points through the turn instead of back along the segment just completed.
 */
fun nearestForwardRouteSegment(
    geometry: List<List<Double>>,
    user: GeoCoordinate,
    maximumLateralErrorMeters: Double = 30.0,
): RouteSegmentMatch? {
    require(maximumLateralErrorMeters >= 0.0) {
        "maximumLateralErrorMeters must be non-negative"
    }

    var best: RouteSegmentMatch? = null
    geometry.zipWithNext().forEachIndexed { index, (from, to) ->
        if (!from.isCoordinate() || !to.isCoordinate() || from == to) return@forEachIndexed

        val start = from.toLocalMeters(user)
        val end = to.toLocalMeters(user)
        val dx = end.first - start.first
        val dy = end.second - start.second
        val lengthSquared = dx * dx + dy * dy
        if (lengthSquared <= MIN_SEGMENT_LENGTH_SQUARED_METERS) return@forEachIndexed

        val fraction = (-(start.first * dx + start.second * dy) / lengthSquared)
            .coerceIn(0.0, 1.0)
        val projectedEast = start.first + dx * fraction
        val projectedNorth = start.second + dy * fraction
        val distance = hypot(projectedEast, projectedNorth)
        val candidate = RouteSegmentMatch(
            segmentIndex = index,
            fraction = fraction,
            lateralErrorMeters = distance,
            bearingDegrees = bearingDegrees(from, to),
        )
        val current = best
        if (
            current == null ||
            distance < current.lateralErrorMeters - SEGMENT_TIE_METERS ||
            (abs(distance - current.lateralErrorMeters) <= SEGMENT_TIE_METERS && index > current.segmentIndex)
        ) {
            best = candidate
        }
    }

    return best?.takeIf { it.lateralErrorMeters <= maximumLateralErrorMeters }
}

fun forwardRouteBearing(
    geometry: List<List<Double>>,
    user: GeoCoordinate,
    maximumLateralErrorMeters: Double = 30.0,
): Float? = nearestForwardRouteSegment(
    geometry = geometry,
    user = user,
    maximumLateralErrorMeters = maximumLateralErrorMeters,
)?.bearingDegrees

private fun List<Double>.isCoordinate(): Boolean =
    size >= 2 && this[0].isFinite() && this[1].isFinite() && this[0] in -180.0..180.0 && this[1] in -90.0..90.0

private fun List<Double>.toLocalMeters(origin: GeoCoordinate): Pair<Double, Double> {
    val meanLatitudeRadians = (this[1] + origin.latitude) * 0.5 * PI / 180.0
    val east = (this[0] - origin.longitude) * METERS_PER_DEGREE * cos(meanLatitudeRadians)
    val north = (this[1] - origin.latitude) * METERS_PER_DEGREE
    return east to north
}

fun reasonLabel(reason: String): String = when (reason) {
    "stairs" -> "계단 구간 제외"
    "high_curb" -> "높은 턱 구간 제외"
    "blocked" -> "통행 제한 구간 제외"
    "construction" -> "공사 구간 제외"
    "temporary_closure" -> "임시 통행 불가 구간 제외"
    "session_blocked" -> "방금 확인한 장애 구간 제외"
    "unknown_accessibility" -> "접근성 정보 미확인 구간 제외"
    else -> reason.replace('_', ' ')
}

private const val METERS_PER_DEGREE = 111_320.0
private const val MIN_SEGMENT_LENGTH_SQUARED_METERS = 0.0001
private const val SEGMENT_TIE_METERS = 0.05
