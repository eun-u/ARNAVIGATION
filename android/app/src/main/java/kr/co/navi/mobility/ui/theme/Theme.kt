package kr.co.navi.mobility.ui.theme

import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Shapes
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.ReadOnlyComposable
import androidx.compose.runtime.staticCompositionLocalOf

private val NaviLightColorScheme = lightColorScheme(
    primary = NaviBlue,
    onPrimary = NaviOnDark,
    primaryContainer = NaviBlueSoft,
    onPrimaryContainer = NaviBlueDeep,
    secondary = NaviViolet,
    onSecondary = NaviOnDark,
    secondaryContainer = NaviVioletSoft,
    onSecondaryContainer = NaviVioletDeep,
    background = NaviCanvas,
    onBackground = NaviInk,
    surface = NaviSurface,
    onSurface = NaviInk,
    surfaceVariant = NaviSurfaceRaised,
    onSurfaceVariant = NaviInkSoft,
    error = NaviBlock,
    onError = NaviOnDark,
    errorContainer = NaviBlockSoft,
    onErrorContainer = NaviBlock,
    outline = NaviLineStrong,
    outlineVariant = NaviLine,
    scrim = NaviCameraScrim,
)

private val NaviShapes = Shapes(
    extraSmall = RoundedCornerShape(NaviDimens.RadiusSmall),
    small = RoundedCornerShape(NaviDimens.RadiusControl),
    medium = RoundedCornerShape(NaviDimens.RadiusCard),
    large = RoundedCornerShape(NaviDimens.RadiusSheet),
    extraLarge = RoundedCornerShape(NaviDimens.RadiusSheet),
)

private val LocalNaviExtendedColors = staticCompositionLocalOf { NaviLightExtendedColors }

val MaterialTheme.naviColors: NaviExtendedColors
    @Composable
    @ReadOnlyComposable
    get() = LocalNaviExtendedColors.current

@Composable
fun NaviTheme(content: @Composable () -> Unit) {
    CompositionLocalProvider(LocalNaviExtendedColors provides NaviLightExtendedColors) {
        MaterialTheme(
            colorScheme = NaviLightColorScheme,
            typography = NaviTypography,
            shapes = NaviShapes,
            content = content,
        )
    }
}
