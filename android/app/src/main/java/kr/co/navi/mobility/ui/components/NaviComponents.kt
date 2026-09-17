package kr.co.navi.mobility.ui.components

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBars
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.windowInsetsTopHeight
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.drawscope.rotate
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.role
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import kr.co.navi.mobility.ui.theme.NaviBlue
import kr.co.navi.mobility.ui.theme.NaviBlueSoft
import kr.co.navi.mobility.ui.theme.NaviDimens
import kr.co.navi.mobility.ui.theme.NaviInk
import kr.co.navi.mobility.ui.theme.NaviInkMuted
import kr.co.navi.mobility.ui.theme.NaviLine
import kr.co.navi.mobility.ui.theme.NaviLineStrong
import kr.co.navi.mobility.ui.theme.NaviOnDark
import kr.co.navi.mobility.ui.theme.NaviViolet

@Composable
fun NaviBrandLockup(
    modifier: Modifier = Modifier,
    compact: Boolean = false,
) {
    Row(
        modifier = modifier,
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(NaviDimens.Space12),
    ) {
        PrismaticNaviMark(Modifier.size(if (compact) 38.dp else 50.dp))
        Column {
            Text(
                text = "NaVi",
                style = if (compact) MaterialTheme.typography.titleLarge else MaterialTheme.typography.headlineMedium,
                color = NaviInk,
                fontWeight = FontWeight.ExtraBold,
            )
            if (!compact) {
                Text(
                    text = "Navigate, then verify.",
                    style = MaterialTheme.typography.labelMedium,
                    color = NaviInkMuted,
                )
            }
        }
    }
}

@Composable
fun PrismaticNaviMark(modifier: Modifier = Modifier) {
    Canvas(
        modifier = modifier.semantics {
            contentDescription = "나비 모양 지도 핀 로고"
        },
    ) {
        val centre = Offset(size.width / 2f, size.height * 0.47f)
        val leftWing = Path().apply {
            moveTo(centre.x - size.width * 0.06f, centre.y)
            cubicTo(
                size.width * 0.36f,
                size.height * 0.04f,
                size.width * 0.02f,
                size.height * 0.1f,
                size.width * 0.1f,
                size.height * 0.48f,
            )
            cubicTo(
                size.width * 0.18f,
                size.height * 0.72f,
                size.width * 0.38f,
                size.height * 0.62f,
                centre.x - size.width * 0.06f,
                centre.y,
            )
        }
        val rightWing = Path().apply {
            moveTo(centre.x + size.width * 0.06f, centre.y)
            cubicTo(
                size.width * 0.64f,
                size.height * 0.04f,
                size.width * 0.98f,
                size.height * 0.1f,
                size.width * 0.9f,
                size.height * 0.48f,
            )
            cubicTo(
                size.width * 0.82f,
                size.height * 0.72f,
                size.width * 0.62f,
                size.height * 0.62f,
                centre.x + size.width * 0.06f,
                centre.y,
            )
        }
        drawPath(leftWing, NaviBlue)
        drawPath(rightWing, NaviViolet)
        drawCircle(NaviInk, radius = size.width * 0.2f, center = centre)
        drawCircle(NaviOnDark, radius = size.width * 0.075f, center = centre)
        val arrow = Path().apply {
            moveTo(centre.x, size.height * 0.62f)
            lineTo(size.width * 0.36f, size.height * 0.94f)
            lineTo(centre.x, size.height * 0.86f)
            lineTo(size.width * 0.64f, size.height * 0.94f)
            close()
        }
        drawPath(arrow, NaviInk)
    }
}

@Composable
fun NaviTopBar(
    title: String,
    modifier: Modifier = Modifier,
    onBack: (() -> Unit)? = null,
    trailing: (@Composable () -> Unit)? = null,
) {
    Column(
        modifier = modifier
            .fillMaxWidth()
            .background(MaterialTheme.colorScheme.surface),
    ) {
        Spacer(Modifier.fillMaxWidth().windowInsetsTopHeight(WindowInsets.statusBars))
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .height(64.dp)
                .padding(horizontal = NaviDimens.Space16),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            if (onBack != null) {
                OutlinedButton(
                    onClick = onBack,
                    modifier = Modifier
                        .size(NaviDimens.TouchTarget)
                        .semantics { contentDescription = "이전 화면" },
                    shape = CircleShape,
                    contentPadding = ButtonDefaults.TextButtonContentPadding,
                ) {
                    Text("←", style = MaterialTheme.typography.titleLarge)
                }
                Spacer(Modifier.width(NaviDimens.Space12))
            }
            Text(
                text = title,
                modifier = Modifier.weight(1f),
                style = MaterialTheme.typography.titleLarge,
                color = NaviInk,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
            trailing?.invoke()
        }
    }
}

@Composable
fun PrimaryActionButton(
    text: String,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
    loading: Boolean = false,
) {
    Button(
        onClick = onClick,
        enabled = enabled && !loading,
        modifier = modifier
            .fillMaxWidth()
            .height(56.dp)
            .semantics { role = Role.Button },
        colors = ButtonDefaults.buttonColors(
            containerColor = NaviBlue,
            contentColor = NaviOnDark,
        ),
        shape = MaterialTheme.shapes.small,
    ) {
        if (loading) {
            CircularProgressIndicator(
                modifier = Modifier.size(22.dp),
                color = NaviOnDark,
                strokeWidth = 2.5.dp,
            )
            Spacer(Modifier.width(NaviDimens.Space12))
        }
        Text(text, style = MaterialTheme.typography.labelLarge)
    }
}

@Composable
fun TrustBanner(
    text: String,
    modifier: Modifier = Modifier,
) {
    Row(
        modifier = modifier
            .fillMaxWidth()
            .background(NaviBlueSoft, MaterialTheme.shapes.small)
            .border(1.dp, NaviBlue.copy(alpha = 0.18f), MaterialTheme.shapes.small)
            .padding(NaviDimens.Space12),
        verticalAlignment = Alignment.Top,
        horizontalArrangement = Arrangement.spacedBy(NaviDimens.Space8),
    ) {
        Box(
            Modifier
                .size(22.dp)
                .background(NaviBlue, CircleShape),
            contentAlignment = Alignment.Center,
        ) {
            Text("i", color = Color.White, fontWeight = FontWeight.Bold)
        }
        Text(
            text = text,
            modifier = Modifier.weight(1f),
            style = MaterialTheme.typography.bodySmall,
            color = NaviInk,
        )
    }
}

@Composable
fun StatusPill(
    symbol: String,
    text: String,
    foreground: Color,
    background: Color,
    modifier: Modifier = Modifier,
) {
    Row(
        modifier = modifier
            .background(background, CircleShape)
            .border(1.dp, foreground.copy(alpha = 0.18f), CircleShape)
            .padding(horizontal = 12.dp, vertical = 7.dp),
        horizontalArrangement = Arrangement.spacedBy(6.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(symbol, color = foreground, fontWeight = FontWeight.Bold)
        Text(text, style = MaterialTheme.typography.labelMedium, color = foreground)
    }
}

@Composable
fun SectionCard(
    modifier: Modifier = Modifier,
    content: @Composable () -> Unit,
) {
    Surface(
        modifier = modifier.fillMaxWidth(),
        color = MaterialTheme.colorScheme.surface,
        shape = MaterialTheme.shapes.medium,
        border = androidx.compose.foundation.BorderStroke(1.dp, NaviLine),
        tonalElevation = 0.dp,
        shadowElevation = 0.dp,
    ) {
        Box(Modifier.padding(NaviDimens.Space16)) { content() }
    }
}

@Composable
fun PrismDivider(modifier: Modifier = Modifier) {
    Canvas(modifier.fillMaxWidth().height(8.dp)) {
        val segment = size.width / 7f
        repeat(7) { index ->
            val alpha = 0.25f + index * 0.08f
            val path = Path().apply {
                moveTo(index * segment, size.height)
                lineTo((index + 1) * segment, 0f)
                lineTo((index + 1) * segment, size.height)
                close()
            }
            drawPath(path, if (index % 2 == 0) NaviBlue.copy(alpha = alpha) else NaviViolet.copy(alpha = alpha))
        }
    }
}

@Composable
fun SecondaryActionButton(
    text: String,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
) {
    OutlinedButton(
        onClick = onClick,
        enabled = enabled,
        modifier = modifier
            .fillMaxWidth()
            .height(56.dp)
            .semantics { role = Role.Button },
        colors = ButtonDefaults.outlinedButtonColors(
            contentColor = NaviInk,
        ),
        shape = MaterialTheme.shapes.small,
        border = androidx.compose.foundation.BorderStroke(1.dp, NaviLineStrong),
    ) {
        Text(text, style = MaterialTheme.typography.labelLarge)
    }
}
