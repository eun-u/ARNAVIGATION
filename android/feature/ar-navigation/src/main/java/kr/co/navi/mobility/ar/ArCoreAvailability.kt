package kr.co.navi.mobility.ar

import com.google.ar.core.ArCoreApk

internal enum class ArCoreStartupDecision {
    START_SESSION,
    WAIT_FOR_RESULT,
    USE_2D_INSTALL_REQUIRED,
    USE_2D_UNAVAILABLE,
}

internal fun ArCoreApk.Availability.toStartupDecision(): ArCoreStartupDecision = when (this) {
    ArCoreApk.Availability.SUPPORTED_INSTALLED -> ArCoreStartupDecision.START_SESSION
    ArCoreApk.Availability.SUPPORTED_NOT_INSTALLED,
    ArCoreApk.Availability.SUPPORTED_APK_TOO_OLD,
    -> ArCoreStartupDecision.USE_2D_INSTALL_REQUIRED

    ArCoreApk.Availability.UNKNOWN_CHECKING -> ArCoreStartupDecision.WAIT_FOR_RESULT
    ArCoreApk.Availability.UNKNOWN_ERROR,
    ArCoreApk.Availability.UNKNOWN_TIMED_OUT,
    ArCoreApk.Availability.UNSUPPORTED_DEVICE_NOT_CAPABLE,
    -> ArCoreStartupDecision.USE_2D_UNAVAILABLE
}
