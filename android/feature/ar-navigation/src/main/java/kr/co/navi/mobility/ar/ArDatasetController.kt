package kr.co.navi.mobility.ar

/**
 * UI-safe command bridge. The AR view remains the sole owner of the ARCore session.
 */
class ArDatasetController {
    @Volatile
    private var attachedView: ArCoreNavigationView? = null

    internal fun attach(view: ArCoreNavigationView) {
        attachedView = view
    }

    internal fun detach(view: ArCoreNavigationView) {
        if (attachedView === view) attachedView = null
    }

    fun startRecording() {
        attachedView?.let { view -> view.post(view::startDatasetRecording) }
    }

    fun stopRecording() {
        attachedView?.let { view -> view.post(view::stopDatasetRecording) }
    }

    fun playLatest() {
        attachedView?.let { view -> view.post(view::playLatestDataset) }
    }

    fun returnToLive() {
        attachedView?.let { view -> view.post(view::returnToLiveSession) }
    }
}
