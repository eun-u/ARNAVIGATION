package kr.co.navi.mobility.ui.theme

import androidx.compose.runtime.Immutable
import androidx.compose.ui.graphics.Color

val NaviCanvas = Color(0xFFF8FAFC)
val NaviSurface = Color(0xFFFFFFFF)
val NaviSurfaceRaised = Color(0xFFF1F5F9)
val NaviInk = Color(0xFF172554)
val NaviInkSoft = Color(0xFF475569)
val NaviInkMuted = Color(0xFF64748B)
val NaviLine = Color(0xFFE2E8F0)
val NaviLineStrong = Color(0xFFCBD5E1)

val NaviBlue = Color(0xFF2563EB)
val NaviBlueDeep = Color(0xFF1D4ED8)
val NaviBlueSoft = Color(0xFFEFF6FF)
val NaviViolet = Color(0xFF7C3AED)
val NaviVioletDeep = Color(0xFF5B21B6)
val NaviVioletSoft = Color(0xFFF3E8FF)

val NaviPass = Color(0xFF007A61)
val NaviPassSoft = Color(0xFFDDF5EC)
val NaviBlock = Color(0xFFC8202F)
val NaviBlockSoft = Color(0xFFFDE8EA)
val NaviCaution = Color(0xFFA85A00)
val NaviCautionSoft = Color(0xFFFFF2D8)
val NaviUnknown = Color(0xFF56657A)
val NaviOnDark = Color(0xFFFFFFFF)
val NaviCameraScrim = Color(0xFF081633)

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
