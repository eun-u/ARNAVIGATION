package kr.co.navi.mobility.ar

import kr.co.navi.mobility.guidance.contract.PerceptionFrameLease
import kr.co.navi.mobility.guidance.contract.SpatialFrameContext

/**
 * Owns the active camera session and publishes timestamp-aligned spatial context and CPU frames.
 * The receiver must finish consuming and close each frame lease before returning it to the source.
 */
interface SpatialFrameSource {
    fun start(onFrame: (SpatialFrameContext, PerceptionFrameLease) -> Unit)
    fun stop()
}
