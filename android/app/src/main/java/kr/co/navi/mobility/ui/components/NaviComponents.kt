package kr.co.navi.mobility.ui.components

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBars
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.windowInsetsTopHeight
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
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
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.role
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import kr.co.navi.mobility.ui.theme.NaviBlue
import kr.co.navi.mobility.ui.theme.NaviBlueSoft
import kr.co.navi.mobility.ui.theme.NaviCaution
import kr.co.navi.mobility.ui.theme.NaviCautionSoft
import kr.co.navi.mobility.ui.theme.NaviCyan
import kr.co.navi.mobility.ui.theme.NaviDimens
import kr.co.navi.mobility.ui.theme.NaviGlass
import kr.co.navi.mobility.ui.theme.NaviIndigo
import kr.co.navi.mobility.ui.theme.NaviInk
import kr.co.navi.mobility.ui.theme.NaviInkMuted
import kr.co.navi.mobility.ui.theme.NaviInkSoft
import kr.co.navi.mobility.ui.theme.NaviLine
import kr.co.navi.mobility.ui.theme.NaviMetricDelta
import kr.co.navi.mobility.ui.theme.NaviMetricPrimary
import kr.co.navi.mobility.ui.theme.NaviMetricSecondary
import kr.co.navi.mobility.ui.theme.NaviMetricUncertainty
import kr.co.navi.mobility.ui.theme.NaviOnDark
import kr.co.navi.mobility.ui.theme.NaviPass
import kr.co.navi.mobility.ui.theme.NaviTextDisabled
import kr.co.navi.mobility.ui.theme.NaviViolet

/*
 * NaVi 디자인 시스템 — 최종본.
 *
 * 규격은 docs/design_tokens.md 가 정본이다. 화면에서 색·반경·그림자를 직접 만들지 않고
 * 여기 있는 컴포넌트를 조합해서 쓴다.
 *
 * 3계층: L0 Content(지도·카메라) → Liquid Glass UI → Stained Glass Accent.
 * 누를 수 있는 것은 brand 하나뿐이고, 의미색은 상태를 설명만 한다.
 */

// ─────────────────────────────────────────────────────────────────────────────
// Glass surfaces
// ─────────────────────────────────────────────────────────────────────────────

/** L1 Soft Glass — 카드, 정보 패널, 상태 표시. */
@Composable
fun SoftGlass(
    modifier: Modifier = Modifier,
    shape: RoundedCornerShape = RoundedCornerShape(NaviDimens.RadiusCard),
    content: @Composable () -> Unit,
) {
    Surface(
        modifier = modifier.fillMaxWidth(),
        color = NaviGlass.SoftFallback,
        shape = shape,
        border = BorderStroke(NaviDimens.OpticalEdgeWidth, NaviGlass.OpticalEdge),
        shadowElevation = 1.dp,
    ) {
        Box(Modifier.padding(NaviDimens.Space16)) { content() }
    }
}

/** L2 Interactive Glass — 툴바, 시트, 눌리는 표면. */
@Composable
fun InteractiveGlass(
    modifier: Modifier = Modifier,
    shape: RoundedCornerShape = RoundedCornerShape(NaviDimens.RadiusControl),
    content: @Composable () -> Unit,
) {
    Surface(
        modifier = modifier,
        color = NaviGlass.InteractiveFallback,
        shape = shape,
        border = BorderStroke(NaviDimens.OpticalEdgeWidth, NaviGlass.OpticalEdge),
        shadowElevation = 2.dp,
    ) {
        Box(Modifier.padding(NaviDimens.Space16)) { content() }
    }
}

/** L3 Focus Glass — 활성 버튼, 선택된 경로, 선택된 탭, AR 주요 안내. */
@Composable
fun FocusGlass(
    modifier: Modifier = Modifier,
    shape: RoundedCornerShape = RoundedCornerShape(NaviDimens.RadiusControl),
    content: @Composable () -> Unit,
) {
    Surface(
        modifier = modifier,
        color = NaviGlass.FocusFallback,
        shape = shape,
        border = BorderStroke(NaviDimens.OpticalEdgeWidth, NaviGlass.FocusEdge),
        shadowElevation = 2.dp,
    ) {
        Box(Modifier.padding(NaviDimens.Space16)) { content() }
    }
}

/** 기존 호출부 호환. 내부는 L1 Soft Glass로 바뀌었다. */
@Composable
fun SectionCard(
    modifier: Modifier = Modifier,
    content: @Composable () -> Unit,
) = SoftGlass(modifier = modifier, content = content)

/** 지도·카메라 위에 얹히는 시트. 상단만 둥글다. */
@Composable
fun GlassSheet(
    modifier: Modifier = Modifier,
    content: @Composable () -> Unit,
) {
    Surface(
        modifier = modifier.fillMaxWidth(),
        color = NaviGlass.InteractiveFallback,
        shape = RoundedCornerShape(
            topStart = NaviDimens.RadiusSheet,
            topEnd = NaviDimens.RadiusSheet,
            bottomStart = 0.dp,
            bottomEnd = 0.dp,
        ),
        shadowElevation = 12.dp,
    ) {
        Column {
            Spacer(Modifier.height(NaviDimens.Space8))
            Box(Modifier.fillMaxWidth(), contentAlignment = Alignment.Center) {
                Box(
                    Modifier
                        .size(width = 40.dp, height = 4.dp)
                        .background(NaviInk.copy(alpha = 0.16f), CircleShape),
                )
            }
            Spacer(Modifier.height(NaviDimens.Space12))
            Box(Modifier.padding(horizontal = NaviDimens.ScreenPadding)) { content() }
        }
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// Brand
// ─────────────────────────────────────────────────────────────────────────────

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
        PrismaticNaviMark(Modifier.size(if (compact) 34.dp else 48.dp))
        Column {
            Text(
                text = "NaVi",
                style = if (compact) MaterialTheme.typography.titleLarge else MaterialTheme.typography.headlineMedium,
                color = NaviInk,
                fontWeight = FontWeight.Bold,
            )
            if (!compact) {
                Text(
                    text = "갈 수 있는 길부터.",
                    style = MaterialTheme.typography.bodySmall,
                    color = NaviInkMuted,
                )
            }
        }
    }
}

/**
 * 기하학적 스테인드글라스 나비 — 겹치는 반투명 면에서 새로운 색이 생긴다.
 * 브랜드가 말하는 자리(스플래시·온보딩·앱바)에만 쓴다.
 */
@Composable
fun PrismaticNaviMark(modifier: Modifier = Modifier) {
    Canvas(
        modifier = modifier.semantics { contentDescription = "나비 모양 지도 핀 로고" },
    ) {
        val w = size.width
        val h = size.height
        fun pane(vararg points: Offset): Path = Path().apply {
            moveTo(points[0].x, points[0].y)
            points.drop(1).forEach { lineTo(it.x, it.y) }
            close()
        }

        // 위쪽 두 날개 — 코발트와 바이올렛
        drawPath(
            pane(
                Offset(w * 0.48f, h * 0.46f),
                Offset(w * 0.10f, h * 0.19f),
                Offset(w * 0.30f, h * 0.06f),
                Offset(w * 0.48f, h * 0.27f),
            ),
            NaviBlue.copy(alpha = 0.86f),
        )
        drawPath(
            pane(
                Offset(w * 0.52f, h * 0.46f),
                Offset(w * 0.90f, h * 0.19f),
                Offset(w * 0.70f, h * 0.06f),
                Offset(w * 0.52f, h * 0.27f),
            ),
            NaviViolet.copy(alpha = 0.86f),
        )
        // 아래쪽 두 날개 — 청록과 인디고
        drawPath(
            pane(
                Offset(w * 0.48f, h * 0.50f),
                Offset(w * 0.16f, h * 0.68f),
                Offset(w * 0.32f, h * 0.83f),
                Offset(w * 0.48f, h * 0.63f),
            ),
            NaviCyan.copy(alpha = 0.76f),
        )
        drawPath(
            pane(
                Offset(w * 0.52f, h * 0.50f),
                Offset(w * 0.84f, h * 0.68f),
                Offset(w * 0.68f, h * 0.83f),
                Offset(w * 0.52f, h * 0.63f),
            ),
            NaviIndigo.copy(alpha = 0.76f),
        )
        // 가운데를 통과하는 빛 — 겹침에서 생기는 밝은 면
        drawPath(
            pane(
                Offset(w * 0.50f, h * 0.24f),
                Offset(w * 0.61f, h * 0.48f),
                Offset(w * 0.50f, h * 0.71f),
                Offset(w * 0.39f, h * 0.48f),
            ),
            Color.White.copy(alpha = 0.62f),
        )
        // 핀 축
        drawPath(
            pane(
                Offset(w * 0.485f, h * 0.70f),
                Offset(w * 0.515f, h * 0.70f),
                Offset(w * 0.515f, h * 0.94f),
                Offset(w * 0.485f, h * 0.94f),
            ),
            NaviInk,
        )
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// Top bar
// ─────────────────────────────────────────────────────────────────────────────

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
            .background(NaviGlass.InteractiveFallback),
    ) {
        Spacer(Modifier.fillMaxWidth().windowInsetsTopHeight(WindowInsets.statusBars))
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .height(56.dp)
                .padding(horizontal = NaviDimens.Space8),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            if (onBack != null) {
                Box(
                    modifier = Modifier
                        .size(NaviDimens.TouchTarget)
                        .clickable(onClick = onBack)
                        .semantics {
                            contentDescription = "이전 화면"
                            role = Role.Button
                        },
                    contentAlignment = Alignment.Center,
                ) {
                    Text("←", style = MaterialTheme.typography.titleLarge, color = NaviInk)
                }
            } else {
                Spacer(Modifier.width(NaviDimens.Space12))
            }
            Text(
                text = title,
                modifier = Modifier
                    .weight(1f)
                    .padding(horizontal = NaviDimens.Space4),
                style = MaterialTheme.typography.titleLarge,
                color = NaviInk,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
            trailing?.invoke()
        }
        Box(Modifier.fillMaxWidth().height(1.dp).background(NaviLine))
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// CTA — 6종. 한 화면에 Primary는 하나뿐이다.
// ─────────────────────────────────────────────────────────────────────────────

private val actionShape = RoundedCornerShape(NaviDimens.RadiusAction)

/** Primary — Brand Glass. 화면의 주 행동. */
@Composable
fun PrimaryActionButton(
    text: String,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
    loading: Boolean = false,
) {
    val active = enabled && !loading
    Button(
        onClick = onClick,
        enabled = active,
        modifier = modifier
            .fillMaxWidth()
            .height(NaviDimens.ActionHeight)
            .background(
                brush = if (active || loading) {
                    Brush.linearGradient(listOf(NaviBlue, NaviViolet))
                } else {
                    Brush.linearGradient(listOf(NaviLine, NaviLine))
                },
                shape = actionShape,
                alpha = if (loading) 0.55f else 1f,
            )
            .semantics { role = Role.Button },
        colors = ButtonDefaults.buttonColors(
            containerColor = Color.Transparent,
            contentColor = NaviOnDark,
            disabledContainerColor = Color.Transparent,
            disabledContentColor = NaviTextDisabled,
        ),
        shape = actionShape,
        contentPadding = ButtonDefaults.ContentPadding,
    ) {
        if (loading) {
            CircularProgressIndicator(
                modifier = Modifier.size(20.dp),
                color = NaviOnDark,
                strokeWidth = 2.5.dp,
            )
            Spacer(Modifier.width(NaviDimens.Space8))
        }
        Text(text, style = MaterialTheme.typography.labelLarge)
    }
}

/** Secondary — Interactive Glass. Primary와 동등한 대안. */
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
            .height(NaviDimens.ActionHeight)
            .semantics { role = Role.Button },
        colors = ButtonDefaults.outlinedButtonColors(
            containerColor = NaviGlass.InteractiveFallback,
            contentColor = NaviInk,
        ),
        shape = actionShape,
        border = BorderStroke(NaviDimens.OpticalEdgeWidth, NaviGlass.OpticalEdge),
    ) {
        Text(text, style = MaterialTheme.typography.labelLarge)
    }
}

/** Tertiary — 면 없음. 보조 진입. */
@Composable
fun TertiaryActionButton(
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
            .height(NaviDimens.ActionHeightCompact)
            .semantics { role = Role.Button },
        colors = ButtonDefaults.outlinedButtonColors(
            containerColor = Color.Transparent,
            contentColor = NaviBlue,
        ),
        shape = actionShape,
        border = null,
    ) {
        Text(text, style = MaterialTheme.typography.labelLarge)
    }
}

/** Destructive — 되돌리기 어려운 행동. 빨강으로 채우지 않는다. */
@Composable
fun DestructiveActionButton(
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
            .height(NaviDimens.ActionHeight)
            .semantics { role = Role.Button },
        colors = ButtonDefaults.outlinedButtonColors(
            containerColor = MaterialTheme.colorScheme.errorContainer,
            contentColor = MaterialTheme.colorScheme.error,
        ),
        shape = actionShape,
        border = BorderStroke(NaviDimens.OpticalEdgeWidth, MaterialTheme.colorScheme.error.copy(alpha = 0.30f)),
    ) {
        Text(text, style = MaterialTheme.typography.labelLarge)
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// 상태 표기 — 색 + 도형 + 글자를 항상 함께 쓴다
// ─────────────────────────────────────────────────────────────────────────────

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
            .background(background, RoundedCornerShape(NaviDimens.RadiusSmall))
            .border(
                NaviDimens.OpticalEdgeWidth,
                foreground.copy(alpha = 0.22f),
                RoundedCornerShape(NaviDimens.RadiusSmall),
            )
            .padding(horizontal = NaviDimens.Space12, vertical = 6.dp),
        horizontalArrangement = Arrangement.spacedBy(6.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(symbol, color = foreground, fontWeight = FontWeight.Bold)
        Text(text, style = MaterialTheme.typography.labelMedium, color = foreground)
    }
}

/** 통행 상태 배지. 축 A(통행 상태)만 표현한다. 축 B(근거)는 캡션으로 분리한다. */
@Composable
fun NaviBadge(
    text: String,
    foreground: Color,
    background: Color,
    modifier: Modifier = Modifier,
    symbol: String? = null,
) = StatusPill(
    symbol = symbol ?: "",
    text = text,
    foreground = foreground,
    background = background,
    modifier = modifier,
)

@Composable
fun TrustBanner(
    text: String,
    modifier: Modifier = Modifier,
    tone: Color = NaviCaution,
    container: Color = NaviCautionSoft,
) {
    Row(
        modifier = modifier
            .fillMaxWidth()
            .background(container, RoundedCornerShape(NaviDimens.RadiusControl))
            .border(
                NaviDimens.OpticalEdgeWidth,
                tone.copy(alpha = 0.20f),
                RoundedCornerShape(NaviDimens.RadiusControl),
            )
            .padding(NaviDimens.Space12),
        verticalAlignment = Alignment.Top,
        horizontalArrangement = Arrangement.spacedBy(NaviDimens.Space8),
    ) {
        Box(
            Modifier.size(20.dp).background(tone, CircleShape),
            contentAlignment = Alignment.Center,
        ) {
            Text("!", color = NaviOnDark, fontWeight = FontWeight.Bold, style = MaterialTheme.typography.labelMedium)
        }
        Text(
            text = text,
            modifier = Modifier.weight(1f),
            style = MaterialTheme.typography.bodySmall,
            color = tone,
        )
    }
}

/** 정보 배너 — 고지가 아니라 안내일 때. */
@Composable
fun InfoBanner(text: String, modifier: Modifier = Modifier) =
    TrustBanner(text = text, modifier = modifier, tone = NaviBlue, container = NaviBlueSoft)

// ─────────────────────────────────────────────────────────────────────────────
// 숫자 체계 — 일반 텍스트와 분리된 4단계
// ─────────────────────────────────────────────────────────────────────────────

/** 화면당 하나. 사용자가 가장 먼저 알아야 할 값. */
@Composable
fun PrimaryMetric(
    value: String,
    unit: String? = null,
    modifier: Modifier = Modifier,
    color: Color = NaviInk,
) {
    Row(modifier = modifier, verticalAlignment = Alignment.Bottom) {
        Text(value, style = NaviMetricPrimary, color = color)
        if (unit != null) {
            Spacer(Modifier.width(2.dp))
            Text(
                unit,
                style = MaterialTheme.typography.titleLarge,
                color = color,
                modifier = Modifier.padding(bottom = 4.dp),
            )
        }
    }
}

/** 거리·도착 예정·개수. */
@Composable
fun SecondaryMetric(value: String, modifier: Modifier = Modifier, color: Color = NaviInk) {
    Text(value, style = NaviMetricSecondary, color = color, modifier = modifier)
}

/** 비교값. 부호를 항상 붙이고 늘어나면 warning, 줄어들면 pass. */
@Composable
fun DeltaMetric(value: String, increased: Boolean, modifier: Modifier = Modifier) {
    Text(
        value,
        style = NaviMetricDelta,
        color = if (increased) NaviCaution else NaviPass,
        modifier = modifier,
    )
}

/** 오차·임계값·조건. 항상 가장 작고 가장 약하다. */
@Composable
fun UncertaintyText(value: String, modifier: Modifier = Modifier) {
    Text(value, style = NaviMetricUncertainty, color = NaviInkMuted, modifier = modifier)
}

/** 라벨 + 수치 한 덩어리. */
@Composable
fun MetricBlock(
    label: String,
    value: String,
    modifier: Modifier = Modifier,
    caption: String? = null,
    color: Color = NaviInk,
) {
    Column(modifier = modifier) {
        Text(label, style = MaterialTheme.typography.labelMedium, color = NaviInkMuted)
        Spacer(Modifier.height(2.dp))
        SecondaryMetric(value, color = color)
        if (caption != null) {
            Spacer(Modifier.height(2.dp))
            UncertaintyText(caption)
        }
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// 하단 목적지 4개
// ─────────────────────────────────────────────────────────────────────────────

/** 하단 탭 하나. selected일 때만 아이콘 뒤에 유리 컨테이너가 붙는다. */
@Composable
fun RowScopeTab(
    modifier: Modifier,
    glyph: String,
    label: String,
    selected: Boolean,
    onClick: () -> Unit,
) {
    val tint = if (selected) NaviBlue else NaviInkMuted
    Column(
        modifier = modifier
            .heightIn(min = NaviDimens.TouchTarget)
            .clickable(onClick = onClick)
            .semantics {
                role = Role.Tab
                contentDescription = label
            }
            .padding(vertical = 6.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center,
    ) {
        Box(
            modifier = Modifier
                .background(
                    if (selected) NaviGlass.FocusFallback else Color.Transparent,
                    RoundedCornerShape(NaviDimens.RadiusSmall),
                )
                .padding(horizontal = NaviDimens.Space12, vertical = 3.dp),
            contentAlignment = Alignment.Center,
        ) {
            Text(glyph, style = MaterialTheme.typography.titleMedium, color = tint)
        }
        Spacer(Modifier.height(3.dp))
        Text(
            label,
            style = MaterialTheme.typography.labelMedium,
            color = tint,
            fontWeight = if (selected) FontWeight.Bold else FontWeight.Normal,
        )
    }
}

/** 상시 목적지 4개. 안내 화면은 이 바를 덮는다. */
@Composable
fun NaviBottomBar(
    selected: String,
    onSelect: (String) -> Unit,
    modifier: Modifier = Modifier,
) {
    Surface(
        modifier = modifier.fillMaxWidth(),
        color = NaviGlass.InteractiveFallback,
        shadowElevation = 8.dp,
    ) {
        Column {
            Box(Modifier.fillMaxWidth().height(1.dp).background(NaviLine))
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .navigationBarsPadding()
                    .padding(vertical = 6.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                NaviDestinations.forEach { destination ->
                    RowScopeTab(
                        modifier = Modifier.weight(1f),
                        glyph = destination.glyph,
                        label = destination.label,
                        selected = selected == destination.route,
                        onClick = { onSelect(destination.route) },
                    )
                }
            }
        }
    }
}

data class NaviDestination(
    val route: String,
    val label: String,
    val glyph: String,
)

/**
 * 홈 · 길찾기 · 제보 · 내 정보.
 * 저장·기록은 목적지가 아니라 홈과 내 정보 안의 화면이다.
 */
val NaviDestinations: List<NaviDestination> = listOf(
    NaviDestination("home", "홈", "⌂"),
    NaviDestination("plan", "길찾기", "◇"),
    NaviDestination("report", "제보", "⚑"),
    NaviDestination("profile", "내 정보", "◔"),
)

// ─────────────────────────────────────────────────────────────────────────────
// 예외 상태 — 모든 실패에는 최소 2개의 다음 행동이 있어야 한다
// ─────────────────────────────────────────────────────────────────────────────

/**
 * 경로 없음 · 재탐색 실패 · 위치 부정확 · 오프라인 · AR 추적 실패 · 경로 이탈 공용 패널.
 *
 * "경로를 찾을 수 없습니다"라고 쓰지 않는다. 무엇이 막았는지 말하고,
 * 앱이 사용자의 Hard Constraint를 임의로 완화하지 않는다.
 */
@Composable
fun ExceptionPanel(
    title: String,
    body: String,
    tone: Color,
    container: Color,
    modifier: Modifier = Modifier,
    blockingReasons: List<String> = emptyList(),
    primaryLabel: String? = null,
    onPrimary: (() -> Unit)? = null,
    secondaryLabel: String? = null,
    onSecondary: (() -> Unit)? = null,
    tertiaryLabel: String? = null,
    onTertiary: (() -> Unit)? = null,
) {
    Column(
        modifier = modifier.fillMaxWidth(),
        verticalArrangement = Arrangement.spacedBy(NaviDimens.Space12),
    ) {
        Box(
            Modifier
                .size(64.dp)
                .background(container, RoundedCornerShape(NaviDimens.RadiusCard)),
            contentAlignment = Alignment.Center,
        ) {
            Text("!", style = MaterialTheme.typography.headlineMedium, color = tone)
        }
        Text(title, style = MaterialTheme.typography.headlineSmall, color = NaviInk)
        Text(body, style = MaterialTheme.typography.bodyLarge, color = NaviInkSoft)

        if (blockingReasons.isNotEmpty()) {
            SoftGlass {
                Column(verticalArrangement = Arrangement.spacedBy(NaviDimens.Space8)) {
                    Text("어디서 막혔나요", style = MaterialTheme.typography.labelMedium, color = NaviInkMuted)
                    blockingReasons.forEach { reason ->
                        Row(
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.spacedBy(NaviDimens.Space8),
                        ) {
                            Box(Modifier.size(6.dp).background(tone, CircleShape))
                            Text(reason, style = MaterialTheme.typography.bodyMedium, color = NaviInkSoft)
                        }
                    }
                }
            }
        }

        if (primaryLabel != null && onPrimary != null) {
            PrimaryActionButton(primaryLabel, onPrimary)
        }
        if (secondaryLabel != null && onSecondary != null) {
            SecondaryActionButton(secondaryLabel, onSecondary)
        }
        if (tertiaryLabel != null && onTertiary != null) {
            TertiaryActionButton(tertiaryLabel, onTertiary)
        }
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// 구분선
// ─────────────────────────────────────────────────────────────────────────────

/**
 * 경로 하이라이트를 연상시키는 얇은 구분선.
 * 스테인드글라스는 희소하게 등장해야 더 강하므로 한 줄로만 남겼다.
 */
@Composable
fun PrismDivider(modifier: Modifier = Modifier) {
    Canvas(modifier.fillMaxWidth().height(3.dp)) {
        drawRect(
            brush = Brush.horizontalGradient(
                listOf(
                    NaviBlue.copy(alpha = 0.55f),
                    NaviViolet.copy(alpha = 0.40f),
                    NaviCyan.copy(alpha = 0.22f),
                    Color.Transparent,
                ),
            ),
        )
    }
}

/** 목록 항목 사이 1px 헤어라인. */
@Composable
fun NaviHairline(modifier: Modifier = Modifier) {
    Box(modifier.fillMaxWidth().height(1.dp).background(NaviLine))
}

/** 화면 가운데 놓이는 짧은 안내 문구. */
@Composable
fun CenteredNote(text: String, modifier: Modifier = Modifier) {
    Text(
        text = text,
        modifier = modifier.fillMaxWidth(),
        style = MaterialTheme.typography.bodySmall,
        color = NaviInkMuted,
        textAlign = TextAlign.Center,
    )
}
