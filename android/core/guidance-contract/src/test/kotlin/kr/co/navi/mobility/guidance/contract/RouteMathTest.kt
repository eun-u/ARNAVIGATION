package kr.co.navi.mobility.guidance.contract

import org.junit.Assert.assertEquals
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
    fun `known exclusion reason has a human label`() {
        assertEquals("계단 구간 제외", reasonLabel("stairs"))
        assertEquals("방금 확인한 장애 구간 제외", reasonLabel("session_blocked"))
    }
}
