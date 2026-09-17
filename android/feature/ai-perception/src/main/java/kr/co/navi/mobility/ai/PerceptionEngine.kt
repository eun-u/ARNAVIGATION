package kr.co.navi.mobility.ai

import kr.co.navi.mobility.guidance.contract.PerceptionFrameLease
import kr.co.navi.mobility.guidance.contract.PerceptionResult

/**
 * Produces image-space observations only. Implementations must not retain frame buffers or choose
 * route edges. The caller closes each frame lease after this call returns.
 */
interface PerceptionEngine : AutoCloseable {
    suspend fun analyze(frame: PerceptionFrameLease): PerceptionResult
}
