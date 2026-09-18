package kr.co.navi.mobility.ar

enum class ArLifecycleState {
    INITIALIZED,
    CREATED,
    STARTED,
    RESUMED,
    PAUSED,
    STOPPED,
    DISPOSED,
    DESTROYED,
}

enum class ArSessionTransitionReason {
    NONE,
    INITIAL_SESSION,
    VIEW_RECREATE,
    LIFECYCLE_RESUME,
    LIFECYCLE_PAUSE,
    PLAYBACK_START,
    PLAYBACK_TO_LIVE,
    VIEW_DISPOSE,
    CAMERA_UNAVAILABLE,
}

internal data class ArTrackingDiagnosticsSnapshot(
    val sessionGeneration: Int,
    val lifecycleState: ArLifecycleState,
    val transitionReason: ArSessionTransitionReason,
    val expectedSessionTransition: Boolean,
    val trackingFailureReason: String?,
    val unexpectedTrackingLossCount: Int,
    val expectedTransitionLossCount: Int,
    val lastRecoveryMillis: Long?,
) {
    val totalTrackingLossCount: Int
        get() = unexpectedTrackingLossCount + expectedTransitionLossCount
}

/**
 * Process-scoped tracking history. AR views and ARCore sessions may be recreated while the app
 * remains alive, so counters must not be owned by a renderer instance.
 */
internal class ArTrackingDiagnostics {
    private var sessionGeneration = 0
    private var lifecycleState = ArLifecycleState.INITIALIZED
    private var transitionReason = ArSessionTransitionReason.NONE
    private var expectedSessionTransition = false
    private var trackingFailureReason: String? = null
    private var unexpectedTrackingLossCount = 0
    private var expectedTransitionLossCount = 0
    private var lastRecoveryMillis: Long? = null
    private var lossStartedAtMillis: Long? = null
    private var recoveryCandidateStartedAtMillis: Long? = null
    private var wasTracking = false
    private var expectedTransitionStartedAtMillis: Long? = null
    private var transitionStartedWhileTracking = false

    @Synchronized
    fun snapshot(): ArTrackingDiagnosticsSnapshot = currentSnapshot()

    @Synchronized
    fun updateLifecycle(
        state: ArLifecycleState,
        reason: ArSessionTransitionReason? = null,
        elapsedRealtimeMillis: Long,
    ): ArTrackingDiagnosticsSnapshot {
        lifecycleState = state
        if (reason != null) beginExpectedTransitionLocked(reason, elapsedRealtimeMillis)
        return currentSnapshot()
    }

    @Synchronized
    fun beginExpectedTransition(
        reason: ArSessionTransitionReason,
        elapsedRealtimeMillis: Long,
    ): ArTrackingDiagnosticsSnapshot {
        beginExpectedTransitionLocked(reason, elapsedRealtimeMillis)
        return currentSnapshot()
    }

    @Synchronized
    fun onSessionCreated(
        reason: ArSessionTransitionReason,
        elapsedRealtimeMillis: Long,
    ): ArTrackingDiagnosticsSnapshot {
        sessionGeneration += 1
        beginExpectedTransitionLocked(reason, elapsedRealtimeMillis)
        return currentSnapshot()
    }

    @Synchronized
    fun onTrackingObservation(
        tracking: Boolean,
        failureReason: String?,
        elapsedRealtimeMillis: Long,
    ): ArTrackingDiagnosticsSnapshot {
        expireExpectedTransitionIfNeeded(elapsedRealtimeMillis)
        if (!tracking) {
            recoveryCandidateStartedAtMillis = null
            if (wasTracking && lossStartedAtMillis == null) {
                lossStartedAtMillis = elapsedRealtimeMillis
                if (expectedSessionTransition) {
                    expectedTransitionLossCount += 1
                } else {
                    unexpectedTrackingLossCount += 1
                }
            }
        } else if (lossStartedAtMillis != null) {
            val recoveryCandidate = recoveryCandidateStartedAtMillis
            if (recoveryCandidate == null) {
                recoveryCandidateStartedAtMillis = elapsedRealtimeMillis
                lastRecoveryMillis = elapsedRealtimeMillis - lossStartedAtMillis!!
            } else if (elapsedRealtimeMillis - recoveryCandidate >= RECOVERY_STABILITY_MILLIS) {
                lossStartedAtMillis = null
                recoveryCandidateStartedAtMillis = null
                clearExpectedTransition()
            }
        } else if (!wasTracking && !transitionStartedWhileTracking) {
            clearExpectedTransition()
        }

        wasTracking = tracking
        trackingFailureReason = failureReason?.takeUnless { tracking }
        return currentSnapshot()
    }

    private fun beginExpectedTransitionLocked(
        reason: ArSessionTransitionReason,
        elapsedRealtimeMillis: Long,
    ) {
        transitionReason = reason
        expectedSessionTransition = true
        expectedTransitionStartedAtMillis = elapsedRealtimeMillis
        transitionStartedWhileTracking = wasTracking
    }

    private fun expireExpectedTransitionIfNeeded(elapsedRealtimeMillis: Long) {
        val startedAt = expectedTransitionStartedAtMillis ?: return
        if (elapsedRealtimeMillis - startedAt >= EXPECTED_TRANSITION_GRACE_MILLIS && lossStartedAtMillis == null) {
            clearExpectedTransition()
        }
    }

    private fun clearExpectedTransition() {
        expectedSessionTransition = false
        expectedTransitionStartedAtMillis = null
        transitionStartedWhileTracking = false
    }

    private fun currentSnapshot() = ArTrackingDiagnosticsSnapshot(
        sessionGeneration = sessionGeneration,
        lifecycleState = lifecycleState,
        transitionReason = transitionReason,
        expectedSessionTransition = expectedSessionTransition,
        trackingFailureReason = trackingFailureReason,
        unexpectedTrackingLossCount = unexpectedTrackingLossCount,
        expectedTransitionLossCount = expectedTransitionLossCount,
        lastRecoveryMillis = lastRecoveryMillis,
    )

    private companion object {
        const val EXPECTED_TRANSITION_GRACE_MILLIS = 3_000L
        const val RECOVERY_STABILITY_MILLIS = 500L
    }
}

internal object ArTrackingDiagnosticsStore {
    val process = ArTrackingDiagnostics()
}
