package kr.co.navi.mobility.ar

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class ArTrackingDiagnosticsTest {
    @Test
    fun `initial degraded tracking is not counted as a loss`() {
        val diagnostics = ArTrackingDiagnostics()

        diagnostics.onSessionCreated(ArSessionTransitionReason.INITIAL_SESSION, 0L)
        val degraded = diagnostics.onTrackingObservation(
            tracking = false,
            failureReason = "INSUFFICIENT_FEATURES",
            elapsedRealtimeMillis = 100L,
        )
        val tracking = diagnostics.onTrackingObservation(
            tracking = true,
            failureReason = null,
            elapsedRealtimeMillis = 400L,
        )

        assertEquals(0, degraded.totalTrackingLossCount)
        assertEquals("INSUFFICIENT_FEATURES", degraded.trackingFailureReason)
        assertEquals(1, tracking.sessionGeneration)
        assertFalse(tracking.expectedSessionTransition)
        assertNull(tracking.trackingFailureReason)
    }

    @Test
    fun `playback transition loss is separated from an unexpected loss`() {
        val diagnostics = ArTrackingDiagnostics()
        diagnostics.onSessionCreated(ArSessionTransitionReason.INITIAL_SESSION, 0L)
        diagnostics.onTrackingObservation(true, null, 100L)

        diagnostics.beginExpectedTransition(ArSessionTransitionReason.PLAYBACK_START, 150L)
        val stillExpected = diagnostics.onTrackingObservation(true, null, 175L)
        val expectedLoss = diagnostics.onTrackingObservation(false, "NONE", 200L)
        val expectedRecovery = diagnostics.onTrackingObservation(true, null, 750L)
        diagnostics.onTrackingObservation(true, null, 1_250L)
        val unexpectedLoss = diagnostics.onTrackingObservation(false, "EXCESSIVE_MOTION", 1_500L)
        val unexpectedRecovery = diagnostics.onTrackingObservation(true, null, 2_400L)

        assertTrue(stillExpected.expectedSessionTransition)
        assertEquals(0, expectedLoss.unexpectedTrackingLossCount)
        assertEquals(1, expectedLoss.expectedTransitionLossCount)
        assertEquals(550L, expectedRecovery.lastRecoveryMillis)
        assertEquals(1, unexpectedLoss.unexpectedTrackingLossCount)
        assertEquals(1, unexpectedLoss.expectedTransitionLossCount)
        assertEquals("EXCESSIVE_MOTION", unexpectedLoss.trackingFailureReason)
        assertEquals(2, unexpectedRecovery.totalTrackingLossCount)
        assertEquals(900L, unexpectedRecovery.lastRecoveryMillis)
    }

    @Test
    fun `tracking flaps before stable recovery stay in one loss episode`() {
        val diagnostics = ArTrackingDiagnostics()
        diagnostics.onSessionCreated(ArSessionTransitionReason.INITIAL_SESSION, 0L)
        diagnostics.onTrackingObservation(true, null, 100L)

        diagnostics.onTrackingObservation(false, "INSUFFICIENT_FEATURES", 200L)
        diagnostics.onTrackingObservation(true, null, 300L)
        diagnostics.onTrackingObservation(false, "NONE", 450L)
        diagnostics.onTrackingObservation(true, null, 600L)
        val stable = diagnostics.onTrackingObservation(true, null, 1_100L)
        val nextLoss = diagnostics.onTrackingObservation(false, "EXCESSIVE_MOTION", 1_200L)

        assertEquals(1, stable.unexpectedTrackingLossCount)
        assertEquals(400L, stable.lastRecoveryMillis)
        assertEquals(2, nextLoss.unexpectedTrackingLossCount)
    }

    @Test
    fun `session generation and counters survive renderer replacement`() {
        val processHistory = ArTrackingDiagnostics()
        processHistory.onSessionCreated(ArSessionTransitionReason.INITIAL_SESSION, 0L)
        processHistory.onTrackingObservation(true, null, 10L)
        processHistory.onTrackingObservation(false, "INSUFFICIENT_LIGHT", 20L)

        val recreated = processHistory.onSessionCreated(ArSessionTransitionReason.VIEW_RECREATE, 30L)

        assertEquals(2, recreated.sessionGeneration)
        assertEquals(1, recreated.unexpectedTrackingLossCount)
        assertTrue(recreated.expectedSessionTransition)
        assertEquals(ArSessionTransitionReason.VIEW_RECREATE, recreated.transitionReason)
    }

    @Test
    fun `lifecycle transition keeps explicit state and reason`() {
        val diagnostics = ArTrackingDiagnostics()

        val paused = diagnostics.updateLifecycle(
            ArLifecycleState.PAUSED,
            ArSessionTransitionReason.LIFECYCLE_PAUSE,
            100L,
        )

        assertEquals(ArLifecycleState.PAUSED, paused.lifecycleState)
        assertEquals(ArSessionTransitionReason.LIFECYCLE_PAUSE, paused.transitionReason)
        assertTrue(paused.expectedSessionTransition)
    }
}
