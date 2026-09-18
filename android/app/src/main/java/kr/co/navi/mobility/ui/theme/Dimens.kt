package kr.co.navi.mobility.ui.theme

import androidx.compose.ui.unit.dp

/**
 * 간격 · 반경 · 터치 규격. 8pt 기본, 4pt 보조.
 * 화면마다 여백을 새로 정하지 않는다.
 */
object NaviDimens {
    // space.1 … space.8
    val Space4 = 4.dp
    val Space8 = 8.dp
    val Space12 = 12.dp
    val Space16 = 16.dp
    val Space20 = 20.dp
    val Space24 = 24.dp
    val Space32 = 32.dp

    /** 화면 좌우 여백 — 고정값 */
    val ScreenPadding = 20.dp

    /** 최소 터치 타깃. 안내 중 단일 행동은 [ActionHeight] 이상 */
    val TouchTarget = 48.dp
    /** 목록 항목 최소 높이 */
    val ListItemHeight = 60.dp
    /** Primary / Secondary / Destructive 버튼 높이 */
    val ActionHeight = 56.dp
    /** Tertiary 버튼 높이 */
    val ActionHeightCompact = 48.dp

    // radius.*
    val RadiusSmall = 10.dp
    val RadiusControl = 16.dp
    val RadiusCard = 20.dp
    val RadiusAction = 18.dp
    val RadiusSheet = 26.dp
    val RadiusPill = 999.dp

    /** 얇은 광학 엣지 */
    val OpticalEdgeWidth = 1.dp
}

/**
 * Fluid Optical Motion — 모션이 눈에 띄는 것이 아니라
 * 재질이 실제로 움직였다고 느껴지는 것이 목표다.
 *
 * 시스템 설정이 "움직임 줄이기"면 반복 애니메이션을 중지하고
 * 전환은 opacity만 [ReducedMs] 이하로 쓴다.
 */
object NaviMotion {
    const val PressMs = 140
    const val ChipMs = 180
    const val ScreenMs = 220
    const val SheetMs = 280
    const val RouteMs = 380
    const val ReducedMs = 120

    /** 눌림 스케일 — 모든 버튼 공통 */
    const val PressScale = 0.985f

    /** 재탐색 4단계 시퀀스의 각 구간 시작 시각(ms) */
    const val RerouteFadeAt = 0
    const val RerouteHighlightAt = 120
    const val RerouteDrawAt = 240
    const val RerouteCountUpAt = 400
}
