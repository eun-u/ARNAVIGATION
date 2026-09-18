package kr.co.navi.mobility.ar

import com.google.ar.core.ArCoreApk
import org.junit.Assert.assertEquals
import org.junit.Test

class ArCoreAvailabilityTest {
    @Test
    fun `starts a session only when ARCore is installed`() {
        assertEquals(
            ArCoreStartupDecision.START_SESSION,
            ArCoreApk.Availability.SUPPORTED_INSTALLED.toStartupDecision(),
        )
    }

    @Test
    fun `uses 2D guidance instead of launching an installer`() {
        listOf(
            ArCoreApk.Availability.SUPPORTED_NOT_INSTALLED,
            ArCoreApk.Availability.SUPPORTED_APK_TOO_OLD,
        ).forEach { availability ->
            assertEquals(
                ArCoreStartupDecision.USE_2D_INSTALL_REQUIRED,
                availability.toStartupDecision(),
            )
        }
    }

    @Test
    fun `waits only while availability is actively resolving`() {
        assertEquals(
            ArCoreStartupDecision.WAIT_FOR_RESULT,
            ArCoreApk.Availability.UNKNOWN_CHECKING.toStartupDecision(),
        )
    }

    @Test
    fun `uses 2D guidance for unsupported or failed checks`() {
        listOf(
            ArCoreApk.Availability.UNSUPPORTED_DEVICE_NOT_CAPABLE,
            ArCoreApk.Availability.UNKNOWN_ERROR,
            ArCoreApk.Availability.UNKNOWN_TIMED_OUT,
        ).forEach { availability ->
            assertEquals(
                ArCoreStartupDecision.USE_2D_UNAVAILABLE,
                availability.toStartupDecision(),
            )
        }
    }
}
