package kr.co.navi.mobility.ai.offline

import android.content.Context
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import java.io.File
import kotlinx.coroutines.runBlocking
import kr.co.navi.mobility.ai.PerceptionEngine
import kr.co.navi.mobility.ai.mediapipe.MediaPipeObjectDetectorEngine
import kr.co.navi.mobility.ai.tracking.TrackingPerceptionEngine
import org.junit.Assert.assertTrue
import org.junit.Assume.assumeTrue
import org.junit.Test
import org.junit.runner.RunWith

/** CLI entry point used by scripts/run_m2_device_free.ps1 on an Android emulator. */
@RunWith(AndroidJUnit4::class)
class DeviceFreeOfflineEvaluationTest {
    @Test
    fun evaluateManifestFromExternalFiles() = runBlocking {
        val context = ApplicationProvider.getApplicationContext<Context>()
        val filesRoot = context.filesDir.canonicalFile
        val arguments = InstrumentationRegistry.getArguments()
        assumeTrue(
            "CLI-only M2 evaluation requires the 'manifest' instrumentation argument",
            arguments.getString("manifest") != null,
        )
        val manifest = requireExternalFile(
            filesRoot,
            requireNotNull(arguments.getString("manifest")) {
                "instrumentation argument 'manifest' is required"
            },
        )
        val output = requireExternalDirectory(
            filesRoot,
            requireNotNull(arguments.getString("outputDir")) {
                "instrumentation argument 'outputDir' is required"
            },
        )
        val useTracker = arguments.getString("tracker")?.toBooleanStrictOrNull() ?: true
        val allowFailures = arguments.getString("allowFailures")?.toBooleanStrictOrNull() ?: false

        var engine: PerceptionEngine = MediaPipeObjectDetectorEngine(context)
        if (useTracker) engine = TrackingPerceptionEngine(engine)
        val artifacts = try {
            OfflineEvaluationRunner().run(
                manifestFile = manifest,
                outputDirectory = output,
                engine = engine,
            )
        } finally {
            engine.close()
        }

        File(output, "m2-run-complete.txt").writeText(
            "dataset=${artifacts.report.datasetId}\n" +
                "frames=${artifacts.report.evaluation.frameCount}\n" +
                "failures=${artifacts.report.evaluation.failedFrames.size}\n",
            Charsets.UTF_8,
        )
        if (!allowFailures) {
            assertTrue(
                "offline replay failed frames: ${artifacts.report.evaluation.failedFrames}",
                artifacts.report.evaluation.failedFrames.isEmpty(),
            )
        }
    }

    private fun requireExternalFile(root: File, relativePath: String): File =
        File(root, relativePath).canonicalFile.also { file ->
            require(file.toPath().startsWith(root.toPath())) {
                "manifest must stay under app files: $file"
            }
            require(file.isFile) { "manifest does not exist: $file" }
        }

    private fun requireExternalDirectory(root: File, relativePath: String): File =
        File(root, relativePath).canonicalFile.also { directory ->
            require(directory.toPath().startsWith(root.toPath())) {
                "outputDir must stay under app files: $directory"
            }
            require(directory.exists() || directory.mkdirs()) {
                "could not create outputDir: $directory"
            }
            require(directory.isDirectory)
        }
}
