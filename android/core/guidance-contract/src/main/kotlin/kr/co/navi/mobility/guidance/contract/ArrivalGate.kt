package kr.co.navi.mobility.guidance.contract

import kotlin.math.PI
import kotlin.math.atan2
import kotlin.math.cos
import kotlin.math.sin
import kotlin.math.sqrt

data class ArrivalGateConfig(
    val arrivalRadiusMeters: Double = 10.0,
    val maximumAccuracyMeters: Float = 15f,
    val requiredConsecutiveObservations: Int = 3,
    val requiredDwellMillis: Long = 2_000L,
) {
    init {
        require(arrivalRadiusMeters > 0.0)
        require(maximumAccuracyMeters > 0f)
        require(requiredConsecutiveObservations > 0)
        require(requiredDwellMillis >= 0L)
    }
}

enum class ArrivalGateStatus {
    WAITING_FOR_LOCATION,
    POOR_ACCURACY,
    OUTSIDE_RADIUS,
    CONFIRMING,
    ARRIVED,
}

data class ArrivalGateProgress(
    val destination: GeoCoordinate? = null,
    val status: ArrivalGateStatus = ArrivalGateStatus.WAITING_FOR_LOCATION,
    val distanceMeters: Double? = null,
    val accuracyMeters: Float? = null,
    val consecutiveObservations: Int = 0,
    val firstQualifyingAtMillis: Long? = null,
    val lastObservedAtMillis: Long? = null,
    val arrived: Boolean = false,
)

/**
 * Advances an immutable arrival gate with one distinct location observation.
 * Arrival latches for the current destination once both the count and dwell
 * requirements are met. Duplicate or reversed timestamps cannot advance it.
 */
fun updateArrivalGate(
    previous: ArrivalGateProgress,
    destination: GeoCoordinate,
    user: GeoCoordinate,
    accuracyMeters: Float?,
    observedAtMillis: Long,
    config: ArrivalGateConfig = ArrivalGateConfig(),
): ArrivalGateProgress {
    require(observedAtMillis >= 0L)

    val current = if (previous.destination == destination) {
        previous
    } else {
        ArrivalGateProgress(destination = destination)
    }
    if (current.arrived) return current
    if (current.lastObservedAtMillis != null && observedAtMillis <= current.lastObservedAtMillis) {
        return current
    }

    val distance = geodesicDistanceMeters(user, destination)
    val accuracyAccepted = accuracyMeters != null &&
        accuracyMeters.isFinite() &&
        accuracyMeters >= 0f &&
        accuracyMeters <= config.maximumAccuracyMeters
    if (!accuracyAccepted) {
        return current.resetQualifyingRun(
            status = ArrivalGateStatus.POOR_ACCURACY,
            distanceMeters = distance,
            accuracyMeters = accuracyMeters,
            observedAtMillis = observedAtMillis,
        )
    }
    if (distance > config.arrivalRadiusMeters) {
        return current.resetQualifyingRun(
            status = ArrivalGateStatus.OUTSIDE_RADIUS,
            distanceMeters = distance,
            accuracyMeters = accuracyMeters,
            observedAtMillis = observedAtMillis,
        )
    }

    val firstQualifyingAtMillis = current.firstQualifyingAtMillis ?: observedAtMillis
    val consecutiveObservations = current.consecutiveObservations + 1
    val dwellMillis = observedAtMillis - firstQualifyingAtMillis
    val arrived = consecutiveObservations >= config.requiredConsecutiveObservations &&
        dwellMillis >= config.requiredDwellMillis
    return current.copy(
        status = if (arrived) ArrivalGateStatus.ARRIVED else ArrivalGateStatus.CONFIRMING,
        distanceMeters = distance,
        accuracyMeters = accuracyMeters,
        consecutiveObservations = consecutiveObservations,
        firstQualifyingAtMillis = firstQualifyingAtMillis,
        lastObservedAtMillis = observedAtMillis,
        arrived = arrived,
    )
}

fun geodesicDistanceMeters(from: GeoCoordinate, to: GeoCoordinate): Double {
    val latitudeDelta = Math.toRadians(to.latitude - from.latitude)
    val longitudeDelta = Math.toRadians(to.longitude - from.longitude)
    val fromLatitude = from.latitude * PI / 180.0
    val toLatitude = to.latitude * PI / 180.0
    val haversine = sin(latitudeDelta / 2.0) * sin(latitudeDelta / 2.0) +
        cos(fromLatitude) * cos(toLatitude) *
        sin(longitudeDelta / 2.0) * sin(longitudeDelta / 2.0)
    val boundedHaversine = haversine.coerceIn(0.0, 1.0)
    val angularDistance = 2.0 * atan2(sqrt(boundedHaversine), sqrt(1.0 - boundedHaversine))
    return EARTH_RADIUS_METERS * angularDistance
}

private fun ArrivalGateProgress.resetQualifyingRun(
    status: ArrivalGateStatus,
    distanceMeters: Double,
    accuracyMeters: Float?,
    observedAtMillis: Long,
): ArrivalGateProgress = copy(
    status = status,
    distanceMeters = distanceMeters,
    accuracyMeters = accuracyMeters,
    consecutiveObservations = 0,
    firstQualifyingAtMillis = null,
    lastObservedAtMillis = observedAtMillis,
    arrived = false,
)

private const val EARTH_RADIUS_METERS = 6_371_000.0
