package kr.co.navi.mobility.ar

import kr.co.navi.mobility.guidance.contract.TrackingQuality

enum class ArRuntimeMode {
    CHECKING,
    INSTALL_REQUIRED,
    TRACKING,
    DEGRADED,
    UNAVAILABLE,
}

data class ArRuntimeState(
    val mode: ArRuntimeMode = ArRuntimeMode.CHECKING,
    val trackingQuality: TrackingQuality = TrackingQuality.WAITING,
    val depthSupported: Boolean = false,
    val depthActive: Boolean = false,
    val routeAligned: Boolean = false,
    val trackingLossCount: Int = 0,
    val lastRecoveryMillis: Long? = null,
    val frameTimeMillis: Float? = null,
    val message: String? = null,
) {
    val shouldUse2dFallback: Boolean
        get() = mode != ArRuntimeMode.TRACKING || !routeAligned
}
