package kr.co.navi.mobility.guidance.contract

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class ArrivalGateTest {
    private val destination = GeoCoordinate(latitude = 35.846000, longitude = 127.132000)
    private val inside = GeoCoordinate(latitude = 35.846020, longitude = 127.132000)
    private val outside = GeoCoordinate(latitude = 35.846200, longitude = 127.132000)

    @Test
    fun `arrives only after three accurate observations spanning two seconds`() {
        var progress = ArrivalGateProgress()

        progress = observe(progress, inside, accuracyMeters = 4f, observedAtMillis = 1_000L)
        assertEquals(ArrivalGateStatus.CONFIRMING, progress.status)
        assertFalse(progress.arrived)

        progress = observe(progress, inside, accuracyMeters = 5f, observedAtMillis = 2_000L)
        assertFalse(progress.arrived)

        progress = observe(progress, inside, accuracyMeters = 4f, observedAtMillis = 3_000L)
        assertEquals(ArrivalGateStatus.ARRIVED, progress.status)
        assertEquals(3, progress.consecutiveObservations)
        assertTrue(progress.arrived)
    }

    @Test
    fun `poor accuracy and leaving the radius reset consecutive evidence`() {
        var progress = observe(
            ArrivalGateProgress(),
            inside,
            accuracyMeters = 4f,
            observedAtMillis = 1_000L,
        )
        progress = observe(progress, inside, accuracyMeters = 20f, observedAtMillis = 2_000L)
        assertEquals(ArrivalGateStatus.POOR_ACCURACY, progress.status)
        assertEquals(0, progress.consecutiveObservations)

        progress = observe(progress, inside, accuracyMeters = 4f, observedAtMillis = 3_000L)
        progress = observe(progress, outside, accuracyMeters = 4f, observedAtMillis = 4_000L)
        assertEquals(ArrivalGateStatus.OUTSIDE_RADIUS, progress.status)
        assertEquals(0, progress.consecutiveObservations)
    }

    @Test
    fun `duplicate or reversed timestamps cannot advance the gate`() {
        var progress = observe(
            ArrivalGateProgress(),
            inside,
            accuracyMeters = 4f,
            observedAtMillis = 1_000L,
        )

        progress = observe(progress, inside, accuracyMeters = 4f, observedAtMillis = 1_000L)
        progress = observe(progress, inside, accuracyMeters = 4f, observedAtMillis = 900L)

        assertEquals(1, progress.consecutiveObservations)
        assertFalse(progress.arrived)
    }

    @Test
    fun `a new destination clears a latched arrival`() {
        var progress = ArrivalGateProgress()
        progress = observe(progress, inside, accuracyMeters = 4f, observedAtMillis = 1_000L)
        progress = observe(progress, inside, accuracyMeters = 4f, observedAtMillis = 2_000L)
        progress = observe(progress, inside, accuracyMeters = 4f, observedAtMillis = 3_000L)
        assertTrue(progress.arrived)

        val nextDestination = GeoCoordinate(latitude = 35.847000, longitude = 127.132000)
        val reset = updateArrivalGate(
            previous = progress,
            destination = nextDestination,
            user = inside,
            accuracyMeters = 4f,
            observedAtMillis = 4_000L,
        )

        assertEquals(nextDestination, reset.destination)
        assertEquals(ArrivalGateStatus.OUTSIDE_RADIUS, reset.status)
        assertFalse(reset.arrived)
    }

    private fun observe(
        previous: ArrivalGateProgress,
        user: GeoCoordinate,
        accuracyMeters: Float,
        observedAtMillis: Long,
    ): ArrivalGateProgress = updateArrivalGate(
        previous = previous,
        destination = destination,
        user = user,
        accuracyMeters = accuracyMeters,
        observedAtMillis = observedAtMillis,
    )
}
