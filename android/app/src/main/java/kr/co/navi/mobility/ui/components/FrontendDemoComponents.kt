package kr.co.navi.mobility.ui.components

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.role
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import kr.co.navi.mobility.ui.theme.NaviBlue
import kr.co.navi.mobility.ui.theme.NaviCanvas
import kr.co.navi.mobility.ui.theme.NaviDimens
import kr.co.navi.mobility.ui.theme.NaviGlass
import kr.co.navi.mobility.ui.theme.NaviInk
import kr.co.navi.mobility.ui.theme.NaviInkMuted
import kr.co.navi.mobility.ui.theme.NaviLine

enum class DemoSymbol {
    Microphone,
    Locate,
    Volume,
    Camera,
    Map,
    Report,
    Close,
    Check,
    Swap,
    Pin,
    Notification,
}

/** Small, font-independent icons used by the ZIP-matched demo screens. */
@Composable
fun DemoVectorIcon(
    symbol: DemoSymbol,
    description: String,
    modifier: Modifier = Modifier.size(24.dp),
    tint: Color = NaviInk,
) {
    Canvas(modifier.semantics { contentDescription = description }) {
        val u = size.minDimension
        val ox = (size.width - u) / 2f
        val oy = (size.height - u) / 2f
        fun p(x: Float, y: Float) = Offset(ox + u * x, oy + u * y)
        val stroke = Stroke(width = u * 0.085f, cap = StrokeCap.Round)
        fun line(x1: Float, y1: Float, x2: Float, y2: Float, color: Color = tint) {
            drawLine(color, p(x1, y1), p(x2, y2), stroke.width, StrokeCap.Round)
        }

        when (symbol) {
            DemoSymbol.Microphone -> {
                drawRoundRect(
                    color = tint,
                    topLeft = p(0.34f, 0.08f),
                    size = Size(u * 0.32f, u * 0.53f),
                    cornerRadius = CornerRadius(u * 0.16f),
                    style = stroke,
                )
                drawArc(tint, 0f, 180f, false, p(0.22f, 0.28f), Size(u * 0.56f, u * 0.48f), style = stroke)
                line(0.50f, 0.76f, 0.50f, 0.91f)
                line(0.34f, 0.91f, 0.66f, 0.91f)
            }
            DemoSymbol.Locate -> {
                drawCircle(tint, u * 0.30f, p(0.50f, 0.50f), style = stroke)
                drawCircle(tint, u * 0.08f, p(0.50f, 0.50f))
                line(0.50f, 0.05f, 0.50f, 0.21f)
                line(0.50f, 0.79f, 0.50f, 0.95f)
                line(0.05f, 0.50f, 0.21f, 0.50f)
                line(0.79f, 0.50f, 0.95f, 0.50f)
            }
            DemoSymbol.Volume -> {
                val speaker = Path().apply {
                    moveTo(p(0.14f, 0.40f).x, p(0.14f, 0.40f).y)
                    lineTo(p(0.34f, 0.40f).x, p(0.34f, 0.40f).y)
                    lineTo(p(0.55f, 0.22f).x, p(0.55f, 0.22f).y)
                    lineTo(p(0.55f, 0.78f).x, p(0.55f, 0.78f).y)
                    lineTo(p(0.34f, 0.60f).x, p(0.34f, 0.60f).y)
                    lineTo(p(0.14f, 0.60f).x, p(0.14f, 0.60f).y)
                    close()
                }
                drawPath(speaker, tint)
                drawArc(tint, -48f, 96f, false, p(0.42f, 0.29f), Size(u * 0.30f, u * 0.42f), style = stroke)
                drawArc(tint, -46f, 92f, false, p(0.40f, 0.16f), Size(u * 0.48f, u * 0.68f), style = stroke)
            }
            DemoSymbol.Camera -> {
                drawRoundRect(tint, p(0.10f, 0.26f), Size(u * 0.80f, u * 0.58f), CornerRadius(u * 0.10f), style = stroke)
                drawCircle(tint, u * 0.17f, p(0.50f, 0.55f), style = stroke)
                drawRoundRect(tint, p(0.28f, 0.14f), Size(u * 0.26f, u * 0.18f), CornerRadius(u * 0.04f))
            }
            DemoSymbol.Map -> {
                val map = Path().apply {
                    moveTo(p(0.10f, 0.22f).x, p(0.10f, 0.22f).y)
                    lineTo(p(0.36f, 0.12f).x, p(0.36f, 0.12f).y)
                    lineTo(p(0.64f, 0.24f).x, p(0.64f, 0.24f).y)
                    lineTo(p(0.90f, 0.14f).x, p(0.90f, 0.14f).y)
                    lineTo(p(0.90f, 0.78f).x, p(0.90f, 0.78f).y)
                    lineTo(p(0.64f, 0.88f).x, p(0.64f, 0.88f).y)
                    lineTo(p(0.36f, 0.76f).x, p(0.36f, 0.76f).y)
                    lineTo(p(0.10f, 0.86f).x, p(0.10f, 0.86f).y)
                    close()
                }
                drawPath(map, tint, style = stroke)
                line(0.36f, 0.12f, 0.36f, 0.76f)
                line(0.64f, 0.24f, 0.64f, 0.88f)
            }
            DemoSymbol.Report -> {
                line(0.25f, 0.10f, 0.25f, 0.90f)
                val flag = Path().apply {
                    moveTo(p(0.28f, 0.17f).x, p(0.28f, 0.17f).y)
                    lineTo(p(0.80f, 0.17f).x, p(0.80f, 0.17f).y)
                    lineTo(p(0.66f, 0.40f).x, p(0.66f, 0.40f).y)
                    lineTo(p(0.80f, 0.61f).x, p(0.80f, 0.61f).y)
                    lineTo(p(0.28f, 0.61f).x, p(0.28f, 0.61f).y)
                    close()
                }
                drawPath(flag, tint, style = stroke)
            }
            DemoSymbol.Close -> {
                line(0.22f, 0.22f, 0.78f, 0.78f)
                line(0.78f, 0.22f, 0.22f, 0.78f)
            }
            DemoSymbol.Check -> {
                drawCircle(tint, u * 0.42f, p(0.50f, 0.50f), style = stroke)
                line(0.28f, 0.52f, 0.44f, 0.68f)
                line(0.44f, 0.68f, 0.74f, 0.34f)
            }
            DemoSymbol.Swap -> {
                line(0.34f, 0.18f, 0.34f, 0.78f)
                line(0.18f, 0.34f, 0.34f, 0.18f)
                line(0.50f, 0.22f, 0.66f, 0.38f)
                line(0.66f, 0.22f, 0.66f, 0.82f)
                line(0.66f, 0.82f, 0.50f, 0.66f)
            }
            DemoSymbol.Pin -> {
                val pin = Path().apply {
                    moveTo(p(0.50f, 0.94f).x, p(0.50f, 0.94f).y)
                    cubicTo(p(0.42f, 0.80f).x, p(0.42f, 0.80f).y, p(0.20f, 0.58f).x, p(0.20f, 0.58f).y, p(0.20f, 0.36f).x, p(0.20f, 0.36f).y)
                    cubicTo(p(0.20f, 0.16f).x, p(0.20f, 0.16f).y, p(0.34f, 0.06f).x, p(0.34f, 0.06f).y, p(0.50f, 0.06f).x, p(0.50f, 0.06f).y)
                    cubicTo(p(0.66f, 0.06f).x, p(0.66f, 0.06f).y, p(0.80f, 0.16f).x, p(0.80f, 0.16f).y, p(0.80f, 0.36f).x, p(0.80f, 0.36f).y)
                    cubicTo(p(0.80f, 0.58f).x, p(0.80f, 0.58f).y, p(0.58f, 0.80f).x, p(0.58f, 0.80f).y, p(0.50f, 0.94f).x, p(0.50f, 0.94f).y)
                    close()
                }
                drawPath(pin, tint)
                drawCircle(Color.White, u * 0.10f, p(0.50f, 0.36f))
            }
            DemoSymbol.Notification -> {
                drawArc(tint, 190f, 160f, false, p(0.20f, 0.20f), Size(u * 0.60f, u * 0.62f), style = stroke)
                line(0.20f, 0.68f, 0.80f, 0.68f)
                line(0.42f, 0.82f, 0.58f, 0.82f)
            }
        }
    }
}

/**
 * frontend/assets/frontend_demo의 390x844 아트보드에 쓰인 공통 배경.
 * 이미지로 굳히지 않고 화면 비율에 맞는 기하학 면으로 그려 접근성 글자 크기에도 대응한다.
 */
@Composable
fun FrontendDemoBackdrop(modifier: Modifier = Modifier) {
    Canvas(modifier.fillMaxSize().background(NaviCanvas)) {
        val w = size.width
        val h = size.height
        fun polygon(color: Color, points: List<Offset>) {
            val path = Path().apply {
                moveTo(points.first().x, points.first().y)
                points.drop(1).forEach { lineTo(it.x, it.y) }
                close()
            }
            drawPath(path, color)
        }

        polygon(
            Color(0xFFD4E1FA).copy(alpha = 0.72f),
            listOf(Offset(0f, 0f), Offset(w * 0.43f, 0f), Offset(w * 0.56f, h * 0.25f),
                Offset(w * 0.15f, h * 0.30f)),
        )
        polygon(
            Color(0xFFB8B8F4).copy(alpha = 0.50f),
            listOf(Offset(w * 0.43f, 0f), Offset(w * 0.72f, 0f), Offset(w * 0.82f, h * 0.24f),
                Offset(w * 0.56f, h * 0.25f)),
        )
        polygon(
            Color(0xFFE0D9FA).copy(alpha = 0.60f),
            listOf(Offset(w * 0.72f, 0f), Offset(w, 0f), Offset(w, h * 0.30f), Offset(w * 0.82f, h * 0.24f)),
        )
        polygon(
            Color.White.copy(alpha = 0.72f),
            listOf(Offset(w * 0.15f, h * 0.30f), Offset(w * 0.56f, h * 0.25f), Offset(w, h * 0.30f),
                Offset(w * 0.83f, h * 0.68f), Offset(w * 0.30f, h * 0.65f)),
        )
        polygon(
            Color(0xFFCBEFF4).copy(alpha = 0.67f),
            listOf(Offset(0f, h * 0.60f), Offset(w * 0.30f, h * 0.65f), Offset(w * 0.25f, h), Offset(0f, h)),
        )
        polygon(
            Color.White.copy(alpha = 0.72f),
            listOf(Offset(w * 0.30f, h * 0.65f), Offset(w * 0.83f, h * 0.68f), Offset(w * 0.68f, h),
                Offset(w * 0.25f, h)),
        )
        polygon(
            Color(0xFFD8DAFA).copy(alpha = 0.72f),
            listOf(Offset(w * 0.83f, h * 0.68f), Offset(w, h * 0.65f), Offset(w, h), Offset(w * 0.68f, h)),
        )
    }
}

@Composable
fun FrontendDemoPage(
    modifier: Modifier = Modifier,
    content: @Composable () -> Unit,
) {
    Box(modifier.fillMaxSize()) {
        FrontendDemoBackdrop()
        content()
    }
}

@Composable
fun FrontendDemoTopBar(
    title: String,
    onBack: (() -> Unit)? = null,
    progress: String? = null,
    trailing: (@Composable () -> Unit)? = null,
) {
    Column(
        Modifier
            .fillMaxWidth()
            .background(NaviGlass.InteractiveFallback.copy(alpha = 0.86f))
            .statusBarsPadding(),
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .height(56.dp)
                .padding(horizontal = 8.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            if (onBack != null) {
                Box(
                    modifier = Modifier
                        .size(48.dp)
                        .clickable(onClick = onBack)
                        .semantics {
                            contentDescription = "이전 화면"
                            role = Role.Button
                        },
                    contentAlignment = Alignment.Center,
                ) {
                    Text("‹", style = MaterialTheme.typography.headlineSmall, color = NaviInk)
                }
            } else {
                Spacer(Modifier.width(12.dp))
            }
            Text(
                text = title,
                modifier = Modifier.weight(1f),
                style = MaterialTheme.typography.titleLarge,
                color = NaviInk,
            )
            if (progress != null) {
                Text(progress, style = MaterialTheme.typography.labelMedium, color = NaviInkMuted)
                Spacer(Modifier.width(12.dp))
            }
            trailing?.invoke()
        }
        Box(Modifier.fillMaxWidth().height(1.dp).background(NaviLine))
    }
}

@Composable
fun DemoGlassCard(
    modifier: Modifier = Modifier,
    radius: Int = 20,
    onClick: (() -> Unit)? = null,
    content: @Composable () -> Unit,
) {
    val shape = RoundedCornerShape(radius.dp)
    Surface(
        modifier = modifier
            .fillMaxWidth()
            .then(
                if (onClick == null) Modifier else Modifier
                    .clickable(onClick = onClick)
                    .semantics { role = Role.Button },
            ),
        color = NaviGlass.SoftFallback,
        shape = shape,
        border = androidx.compose.foundation.BorderStroke(1.dp, NaviGlass.OpticalEdge),
        shadowElevation = 2.dp,
    ) {
        Box(Modifier.padding(16.dp)) { content() }
    }
}

@Composable
fun DemoIconTile(
    glyph: String,
    tint: Color,
    background: Color,
    description: String,
) {
    Box(
        Modifier
            .size(44.dp)
            .background(background, RoundedCornerShape(14.dp))
            .semantics { contentDescription = description },
        contentAlignment = Alignment.Center,
    ) {
        Text(glyph, style = MaterialTheme.typography.titleLarge, color = tint, fontWeight = FontWeight.Bold)
    }
}

@Composable
fun DemoSegment(
    label: String,
    selected: Boolean,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Box(
        modifier = modifier
            .height(44.dp)
            .background(
                if (selected) NaviGlass.FocusFallback else NaviGlass.InteractiveFallback,
                RoundedCornerShape(14.dp),
            )
            .border(
                1.dp,
                if (selected) NaviBlue else NaviGlass.OpticalEdge,
                RoundedCornerShape(14.dp),
            )
            .clickable(onClick = onClick),
        contentAlignment = Alignment.Center,
    ) {
        Text(
            label,
            style = MaterialTheme.typography.labelMedium,
            color = if (selected) NaviBlue else NaviInk,
        )
    }
}

@Composable
fun DemoSectionLabel(text: String, trailing: String? = null) {
    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
        Text(text, modifier = Modifier.weight(1f), style = MaterialTheme.typography.bodySmall, color = NaviInkMuted)
        if (trailing != null) Text(trailing, style = MaterialTheme.typography.labelMedium, color = NaviBlue)
    }
}

@Composable
fun DemoDivider(modifier: Modifier = Modifier) {
    Box(modifier.fillMaxWidth().height(1.dp).background(NaviLine))
}

@Composable
fun DemoDot(color: Color, modifier: Modifier = Modifier) {
    Box(modifier.size(8.dp).background(color, CircleShape))
}

@Composable
fun DemoKeyValueRow(label: String, value: String, emphasized: Boolean = false) {
    Row(
        Modifier.fillMaxWidth(),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.SpaceBetween,
    ) {
        Text(label, style = MaterialTheme.typography.bodyMedium, color = NaviInk)
        Text(
            value,
            style = if (emphasized) MaterialTheme.typography.labelLarge else MaterialTheme.typography.labelMedium,
            color = if (emphasized) NaviBlue else NaviInkMuted,
        )
    }
}
