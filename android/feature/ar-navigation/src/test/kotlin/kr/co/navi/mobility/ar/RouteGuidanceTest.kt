package kr.co.navi.mobility.ar

import kr.co.navi.mobility.guidance.contract.GeoCoordinate
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class RouteGuidanceTest {
    private val route = listOf(
        GeoCoordinate(latitude = 37.400000, longitude = 126.900000),
        GeoCoordinate(latitude = 37.400100, longitude = 126.900000),
        GeoCoordinate(latitude = 37.400200, longitude = 126.900100),
        GeoCoordinate(latitude = 37.400500, longitude = 126.900100),
    )

    @Test
    fun `builds a clipped forward path from the nearest segment`() {
        val path = buildForwardGuidancePath(
            route = route,
            user = GeoCoordinate(latitude = 37.400090, longitude = 126.900010),
            locationAccuracyMeters = 4f,
            lookAheadMeters = 20f,
        )

        assertNotNull(path)
        requireNotNull(path)
        assertTrue(path.lateralErrorMeters < 2f)
        assertTrue(path.points.size >= 2)
        val travelled = path.points.zipWithNext().sumOf { (from, to) ->
            hypot(
                (to.eastMeters - from.eastMeters).toDouble(),
                (to.northMeters - from.northMeters).toDouble(),
            )
        }
        assertEquals(20.0, travelled, 0.25)
    }

    @Test
    fun `rejects low accuracy instead of placing a misleading ribbon`() {
        assertNull(
            buildForwardGuidancePath(
                route = route,
                user = route.first(),
                locationAccuracyMeters = 32f,
            ),
        )
    }

    @Test
    fun `rejects a user far from the route`() {
        assertNull(
            buildForwardGuidancePath(
                route = route,
                user = GeoCoordinate(latitude = 37.410000, longitude = 126.910000),
                locationAccuracyMeters = 3f,
            ),
        )
    }
}
