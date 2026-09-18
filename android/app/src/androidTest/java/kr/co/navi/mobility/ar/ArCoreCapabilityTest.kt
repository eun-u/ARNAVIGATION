package kr.co.navi.mobility.ar

import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import com.google.ar.core.ArCoreApk
import com.google.ar.core.Config
import com.google.ar.core.Session
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class ArCoreCapabilityTest {
    @Test
    fun referenceDeviceCreatesSessionAndSupportsAutomaticDepth() {
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        val availability = ArCoreApk.getInstance().checkAvailability(context)
        assertTrue("ARCore is not supported: $availability", availability.isSupported)

        val session = Session(context)
        try {
            assertTrue(
                "Reference device must support ARCore automatic depth",
                session.isDepthModeSupported(Config.DepthMode.AUTOMATIC),
            )
            session.configure(
                session.config.apply {
                    depthMode = Config.DepthMode.AUTOMATIC
                    focusMode = Config.FocusMode.AUTO
                },
            )
        } finally {
            session.close()
        }
    }
}
