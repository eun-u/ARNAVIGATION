package kr.co.navi.mobility.guidance.fusion

import kr.co.navi.mobility.guidance.contract.HazardObservation
import kr.co.navi.mobility.guidance.contract.PerceptionResult
import kr.co.navi.mobility.guidance.contract.SpatialFrameContext

/** Combines synchronized spatial and perception results without selecting Graph edges. */
interface GuidanceFusion {
    fun fuse(
        spatialContext: SpatialFrameContext,
        perceptionResult: PerceptionResult,
    ): List<HazardObservation>
}

class NoOpGuidanceFusion : GuidanceFusion {
    override fun fuse(
        spatialContext: SpatialFrameContext,
        perceptionResult: PerceptionResult,
    ): List<HazardObservation> {
        require(spatialContext.stamp == perceptionResult.stamp) {
            "Spatial and perception results must describe the same frame"
        }
        return emptyList()
    }
}
