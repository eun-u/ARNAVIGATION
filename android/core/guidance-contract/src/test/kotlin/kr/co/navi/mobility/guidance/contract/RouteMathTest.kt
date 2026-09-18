package kr.co.navi.mobility.guidance.contract

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class RouteMathTest {
    @Test
    fun `bearing points east`() {
        val bearing = bearingDegrees(
            from = listOf(126.0, 37.0),
            to = listOf(126.01, 37.0),
        )

        assertTrue(bearing in 89f..91f)
    }

    @Test
    fun `heading delta chooses shortest signed turn`() {
        assertEquals(20f, normalizeHeadingDelta(10f, 350f), 0.001f)
        assertEquals(-20f, normalizeHeadingDelta(350f, 10f), 0.001f)
    }

    @Test
    fun `forward bearing uses the segment nearest the user after a turn`() {
        val geometry = listOf(
            listOf(127.000000, 35.000000),
            listOf(127.000100, 35.000000),
            listOf(127.000100, 35.000100),
        )

        val bearing = forwardRouteBearing(
            geometry = geometry,
            user = GeoCoordinate(latitude = 35.000070, longitude = 127.000101),
        )

        requireNotNull(bearing)
        assertTrue(bearing < 1f || bearing > 359f)
    }

    @Test
    fun `forward bearing chooses the outgoing segment at a reroute branch`() {
        val sharedApproach = listOf(
            listOf(127.000000, 35.000000),
            listOf(127.000100, 35.000000),
        )
        val primary = sharedApproach + listOf(listOf(127.000200, 35.000000))
        val rerouted = sharedApproach + listOf(listOf(127.000100, 35.000100))
        val branch = GeoCoordinate(latitude = 35.000000, longitude = 127.000100)

        val primaryBearing = forwardRouteBearing(primary, branch)
        val reroutedBearing = forwardRouteBearing(rerouted, branch)

        requireNotNull(primaryBearing)
        requireNotNull(reroutedBearing)
        assertTrue(primaryBearing in 89f..91f)
        assertTrue(reroutedBearing < 1f || reroutedBearing > 359f)
    }

    @Test
    fun `forward bearing rejects a location far from the route`() {
        val geometry = listOf(
            listOf(127.000000, 35.000000),
            listOf(127.000100, 35.000000),
        )

        assertNull(
            forwardRouteBearing(
                geometry = geometry,
                user = GeoCoordinate(latitude = 35.010000, longitude = 127.010000),
            ),
        )
    }

    @Test
    fun `known exclusion reason has a human label`() {
        assertEquals("계단 구간 제외", reasonLabel("stairs"))
        assertEquals("방금 확인한 장애 구간 제외", reasonLabel("session_blocked"))
    }
}
