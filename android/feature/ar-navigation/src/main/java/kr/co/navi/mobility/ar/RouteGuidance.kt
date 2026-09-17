package kr.co.navi.mobility.ar

import kr.co.navi.mobility.guidance.contract.GeoCoordinate
import kotlin.math.PI
import kotlin.math.cos
import kotlin.math.hypot

data class GuidancePoint(
    val eastMeters: Float,
    val northMeters: Float,
)

data class ForwardGuidancePath(
    val points: List<GuidancePoint>,
    val lateralErrorMeters: Float,
)

/**
 * Builds the short route section ahead of the user in a local east/north frame.
 * Returning null is intentional: callers must use the 2D HUD when location quality
 * cannot safely place a world-locked ribbon.
 */
fun buildForwardGuidancePath(
    route: List<GeoCoordinate>,
    user: GeoCoordinate,
    locationAccuracyMeters: Float?,
    maximumAccuracyMeters: Float = 15f,
    maximumLateralErrorMeters: Float = 20f,
    lookAheadMeters: Float = 45f,
): ForwardGuidancePath? {
    if (route.size < 2 || locationAccuracyMeters == null || locationAccuracyMeters > maximumAccuracyMeters) {
        return null
    }

    val local = route.map { it.toLocalMeters(user) }
    var bestSegment = -1
    var bestT = 0f
    var bestDistance = Float.POSITIVE_INFINITY
    var bestProjection = GuidancePoint(0f, 0f)

    local.zipWithNext().forEachIndexed { index, (start, end) ->
        val dx = end.eastMeters - start.eastMeters
        val dy = end.northMeters - start.northMeters
        val lengthSquared = dx * dx + dy * dy
        if (lengthSquared <= 0.0001f) return@forEachIndexed
        val t = (-(start.eastMeters * dx + start.northMeters * dy) / lengthSquared).coerceIn(0f, 1f)
        val projected = GuidancePoint(
            eastMeters = start.eastMeters + dx * t,
            northMeters = start.northMeters + dy * t,
        )
        val distance = hypot(projected.eastMeters, projected.northMeters)
        if (distance < bestDistance) {
            bestSegment = index
            bestT = t
            bestDistance = distance
            bestProjection = projected
        }
    }

    if (bestSegment < 0 || bestDistance > maximumLateralErrorMeters) return null

    val candidates = buildList {
        add(bestProjection)
        if (bestT < 0.999f) add(local[bestSegment + 1])
        for (index in (bestSegment + 2) until local.size) add(local[index])
    }.distinctBy { point ->
        // Millimetre precision is unnecessary here; this only removes duplicate route vertices.
        Pair((point.eastMeters * 100f).toInt(), (point.northMeters * 100f).toInt())
    }

    if (candidates.size < 2) return null

    val clipped = mutableListOf(candidates.first())
    var accumulated = 0f
    candidates.zipWithNext().forEach { (start, end) ->
        if (accumulated >= lookAheadMeters) return@forEach
        val dx = end.eastMeters - start.eastMeters
        val dy = end.northMeters - start.northMeters
        val segmentLength = hypot(dx, dy)
        if (segmentLength <= 0.001f) return@forEach
        val remaining = lookAheadMeters - accumulated
        if (segmentLength <= remaining) {
            clipped += end
            accumulated += segmentLength
        } else {
            val fraction = remaining / segmentLength
            clipped += GuidancePoint(
                eastMeters = start.eastMeters + dx * fraction,
                northMeters = start.northMeters + dy * fraction,
            )
            accumulated = lookAheadMeters
        }
    }

    return clipped.takeIf { it.size >= 2 }?.let {
        ForwardGuidancePath(points = it, lateralErrorMeters = bestDistance)
    }
}

private fun GeoCoordinate.toLocalMeters(origin: GeoCoordinate): GuidancePoint {
    val meanLatitudeRadians = (latitude + origin.latitude) * 0.5 * PI / 180.0
    val east = (longitude - origin.longitude) * METERS_PER_DEGREE * cos(meanLatitudeRadians)
    val north = (latitude - origin.latitude) * METERS_PER_DEGREE
    return GuidancePoint(east.toFloat(), north.toFloat())
}

private const val METERS_PER_DEGREE = 111_320.0
