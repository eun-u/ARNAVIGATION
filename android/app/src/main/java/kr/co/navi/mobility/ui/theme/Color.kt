package kr.co.navi.mobility.ui.theme

import androidx.compose.runtime.Immutable
import androidx.compose.ui.graphics.Color

/**
 * NaVi 최종 색 토큰.
 *
 * 이름은 디자인 토큰 명세(docs/design_tokens.md)의 Figma Variable 이름과 1:1로 대응한다.
 * 화면에서 새 색을 만들지 않는다. 필요한 색이 여기 없으면 토큰을 먼저 추가한다.
 *
 * 규칙
 *  - 누를 수 있는 요소의 색은 brand 계열 하나뿐이다.
 *  - semantic 계열(pass/caution/block/unknown)은 상태 표기 전용이며 버튼이 되지 않는다.
 *  - 상태는 색 + 아이콘 + 글자를 항상 함께 쓴다.
 */

// ── surface ────────────────────────────────────────────────────────────────
/** surface.base — 앱 화면의 기본 바탕 */
val NaviCanvas = Color(0xFFF4F6FA)
/** surface.solid — 유리를 쓸 수 없는 불투명 면 */
val NaviSurface = Color(0xFFFFFFFF)
/** 묶음 블록 / 유리 폴백 바탕 */
val NaviSurfaceRaised = Color(0xFFEDF0F6)

// ── text ───────────────────────────────────────────────────────────────────
/** text.strong — 표제와 강조 본문. 흰 바탕 대비 17.9:1 */
val NaviInk = Color(0xFF10131A)
/** text.body — 본문과 목록. 10.2:1 */
val NaviInkSoft = Color(0xFF3D4453)
/** text.muted — 보조 설명과 라벨. 4.6:1, 13sp 이상에서만 사용 */
val NaviInkMuted = Color(0xFF737D8C)
/** text.disabled — 비활성. 정보 전달에 쓰지 않는다 */
val NaviTextDisabled = Color(0xFFA8AFBC)

// ── line ───────────────────────────────────────────────────────────────────
/** line.hairline — 목록 구분선 */
val NaviLine = Color(0xFFE5E8EE)
val NaviLineStrong = Color(0xFFD3D8E0)

// ── brand ──────────────────────────────────────────────────────────────────
/** color.brand.primary — 유일한 행동 색 */
val NaviBlue = Color(0xFF2A5FE8)
/** 눌림 상태 */
val NaviBlueDeep = Color(0xFF1E49BE)
/** 선택된 칩·연한 바탕 */
val NaviBlueSoft = Color(0xFFE9EFFD)
/** color.brand.violet */
val NaviViolet = Color(0xFF5A3FD6)
val NaviVioletDeep = Color(0xFF432BA8)
val NaviVioletSoft = Color(0xFFEDE9FB)
/** color.brand.indigo — 스테인드글라스 면에서만 등장 */
val NaviIndigo = Color(0xFF4A47E0)
/** color.brand.cyan — 스테인드글라스 면에서만 등장 */
val NaviCyan = Color(0xFF3FC8E4)

// ── semantic — 상태 표기 전용 ───────────────────────────────────────────────
/** semantic.pass — 통과 확인 */
val NaviPass = Color(0xFF0E8F72)
val NaviPassSoft = Color(0xFFE2F3EE)
/** semantic.danger — 통행 제한 */
val NaviBlock = Color(0xFFC4283C)
val NaviBlockSoft = Color(0xFFFAE7E9)
/** semantic.warning — 확인 필요 */
val NaviCaution = Color(0xFFA9660B)
val NaviCautionSoft = Color(0xFFFAEEDC)
/** semantic.unknown — 정보 없음 */
val NaviUnknown = Color(0xFF6B7480)
val NaviUnknownSoft = Color(0xFFEDEFF3)

val NaviOnDark = Color(0xFFFFFFFF)
/** 안내·AR 화면의 어두운 콘텐츠 층 */
val NaviCameraScrim = Color(0xFF0E1117)

/**
 * Liquid Glass 재질 수치 — docs/design_tokens.md "Glass" 절과 같은 값.
 *
 * Compose에서 backdrop blur를 직접 쓸 수 없는 구간에서는 [SoftFallback] 계열의
 * 불투명 대체값으로 내려간다. 흐림이 사라져도 구조와 위계는 그대로 유지되어야 한다.
 */
object NaviGlass {
    /** L1 Soft Glass — 카드, 정보 패널, 상태 표시 */
    const val SoftBlurDp = 16
    const val SoftAlpha = 0.72f
    val SoftFallback = Color(0xEBFFFFFF)

    /** L2 Interactive Glass — 버튼, 세그먼트, 툴바, 바텀시트 */
    const val InteractiveBlurDp = 20
    const val InteractiveAlpha = 0.82f
    val InteractiveFallback = Color(0xF5FFFFFF)

    /** L3 Focus Glass — 활성 버튼, 선택된 경로, 선택된 탭, AR 주요 안내 */
    const val FocusBlurDp = 22
    const val FocusAlpha = 0.92f
    val FocusFallback = Color(0xFFECF1FF)

    /** 얇은 광학 엣지와 스펙큘러 하이라이트 */
    val OpticalEdge = Color(0x1210131A)
    val FocusEdge = Color(0x522A5FE8)
    val Specular = Color(0xF2FFFFFF)
}

@Immutable
data class NaviExtendedColors(
    val routeStandard: Color,
    val routeAccessible: Color,
    val routeRerouted: Color,
    val pass: Color,
    val passContainer: Color,
    val block: Color,
    val blockContainer: Color,
    val caution: Color,
    val cautionContainer: Color,
    val unknown: Color,
    val cameraScrim: Color,
    val unknownContainer: Color = NaviUnknownSoft,
    val textDisabled: Color = NaviTextDisabled,
    /** Primary CTA의 브랜드 글래스 그라데이션 양 끝 */
    val brandGradientStart: Color = NaviBlue,
    val brandGradientEnd: Color = NaviViolet,
    val focusEdge: Color = NaviGlass.FocusEdge,
    val opticalEdge: Color = NaviGlass.OpticalEdge,
)

val NaviLightExtendedColors = NaviExtendedColors(
    routeStandard = NaviUnknown,
    routeAccessible = NaviBlue,
    routeRerouted = NaviViolet,
    pass = NaviPass,
    passContainer = NaviPassSoft,
    block = NaviBlock,
    blockContainer = NaviBlockSoft,
    caution = NaviCaution,
    cautionContainer = NaviCautionSoft,
    unknown = NaviUnknown,
    cameraScrim = NaviCameraScrim.copy(alpha = 0.82f),
)
