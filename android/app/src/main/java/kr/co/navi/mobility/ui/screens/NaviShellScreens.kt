package kr.co.navi.mobility.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.role
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import kr.co.navi.mobility.data.NaviSessionState
import kr.co.navi.mobility.ui.components.CenteredNote
import kr.co.navi.mobility.ui.components.ExceptionPanel
import kr.co.navi.mobility.ui.components.FocusGlass
import kr.co.navi.mobility.ui.components.InfoBanner
import kr.co.navi.mobility.ui.components.NaviBrandLockup
import kr.co.navi.mobility.ui.components.NaviHairline
import kr.co.navi.mobility.ui.components.NaviTopBar
import kr.co.navi.mobility.ui.components.PrimaryActionButton
import kr.co.navi.mobility.ui.components.SectionCard
import kr.co.navi.mobility.ui.components.SoftGlass
import kr.co.navi.mobility.ui.components.StatusPill
import kr.co.navi.mobility.ui.components.TrustBanner
import kr.co.navi.mobility.ui.components.UncertaintyText
import kr.co.navi.mobility.ui.theme.NaviBlock
import kr.co.navi.mobility.ui.theme.NaviBlockSoft
import kr.co.navi.mobility.ui.theme.NaviBlue
import kr.co.navi.mobility.ui.theme.NaviCanvas
import kr.co.navi.mobility.ui.theme.NaviCaution
import kr.co.navi.mobility.ui.theme.NaviCautionSoft
import kr.co.navi.mobility.ui.theme.NaviDimens
import kr.co.navi.mobility.ui.theme.NaviInk
import kr.co.navi.mobility.ui.theme.NaviInkMuted
import kr.co.navi.mobility.ui.theme.NaviPass
import kr.co.navi.mobility.ui.theme.NaviPassSoft
import kr.co.navi.mobility.ui.theme.NaviUnknown
import kr.co.navi.mobility.ui.theme.NaviUnknownSoft

/*
 * 탭 목적지 화면과 예외 상태 화면.
 *
 * 정보 위계는 모든 경로 화면에서 동일하다.
 *   L1 갈 수 있는가 → L2 얼마나 걸리는가 → L3 무엇이 제외됐는가
 *   → L4 왜 이 경로인가 → L5 원시 데이터
 */

// ─────────────────────────────────────────────────────────────────────────────
// 홈 — 브랜드 강도 Medium
// ─────────────────────────────────────────────────────────────────────────────

@Composable
fun HomeScreen(
    session: NaviSessionState,
    onFindRoute: () -> Unit,
    onResumeGuidance: () -> Unit,
    onEditProfile: () -> Unit,
) {
    val bootstrap = session.bootstrap
    val activeRoute = session.activeRoute

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(NaviCanvas)
            .statusBarsPadding()
            .verticalScroll(rememberScrollState())
            .padding(horizontal = NaviDimens.ScreenPadding),
    ) {
        Spacer(Modifier.height(NaviDimens.Space16))
        Row(
            modifier = Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            NaviBrandLockup(compact = true, modifier = Modifier.weight(1f))
            StatusPill(
                symbol = "●",
                text = if (bootstrap != null) "실데이터 연결" else "연결 대기",
                foreground = if (bootstrap != null) NaviPass else NaviUnknown,
                background = if (bootstrap != null) NaviPassSoft else NaviUnknownSoft,
            )
        }

        if (activeRoute != null) {
            Spacer(Modifier.height(NaviDimens.Space16))
            FocusGlass(
                modifier = Modifier
                    .fillMaxWidth()
                    .clickable(onClick = onResumeGuidance)
                    .semantics { role = Role.Button },
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Column(Modifier.weight(1f)) {
                        Text(
                            "안내가 진행 중이에요",
                            style = MaterialTheme.typography.titleMedium,
                            color = NaviBlue,
                        )
                        UncertaintyText("남은 ${formatDistanceShort(activeRoute.distanceM)} · 약 ${activeRoute.estimatedMinutes}분")
                    }
                    Text("›", style = MaterialTheme.typography.headlineSmall, color = NaviBlue)
                }
            }
        }

        Spacer(Modifier.height(NaviDimens.Space24))
        Text(
            text = "오늘도\n갈 수 있는 길부터 볼게요.",
            style = MaterialTheme.typography.headlineMedium,
            color = NaviInk,
            modifier = Modifier.semantics { heading() },
        )

        Spacer(Modifier.height(NaviDimens.Space20))
        SoftGlass(
            modifier = Modifier
                .fillMaxWidth()
                .clickable(onClick = onFindRoute)
                .semantics { role = Role.Button },
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text("⌕", style = MaterialTheme.typography.titleLarge, color = NaviInkMuted)
                Spacer(Modifier.width(NaviDimens.Space12))
                Text(
                    "어디로 갈까요?",
                    style = MaterialTheme.typography.bodyLarge,
                    color = NaviInkMuted,
                    fontWeight = FontWeight.SemiBold,
                )
            }
        }

        Spacer(Modifier.height(NaviDimens.Space12))
        SectionCard(
            modifier = Modifier
                .clickable(onClick = onEditProfile)
                .semantics { role = Role.Button },
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text("내 이동 조건", style = MaterialTheme.typography.labelMedium, color = NaviInkMuted)
                    Spacer(Modifier.height(2.dp))
                    Text(
                        text = if (session.profile == "wheelchair") "휠체어 · 계단 제외" else "일반 보행 · 거리 우선",
                        style = MaterialTheme.typography.titleMedium,
                        color = NaviInk,
                    )
                }
                Text("수정", style = MaterialTheme.typography.labelLarge, color = NaviBlue)
            }
        }

        Spacer(Modifier.height(NaviDimens.Space20))
        Text("최근 경로", style = MaterialTheme.typography.labelMedium, color = NaviInkMuted)
        Spacer(Modifier.height(NaviDimens.Space8))
        if (bootstrap == null) {
            SoftGlass {
                Column {
                    Text("아직 이동 기록이 없어요", style = MaterialTheme.typography.bodyLarge, color = NaviInk)
                    Spacer(Modifier.height(NaviDimens.Space4))
                    UncertaintyText("첫 경로를 찾아보세요")
                }
            }
        } else {
            SoftGlass {
                Column {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Box(Modifier.size(8.dp).background(NaviBlue, CircleShape))
                        Spacer(Modifier.width(NaviDimens.Space12))
                        Column(Modifier.weight(1f)) {
                            Text(
                                "${bootstrap.origin.name} → ${bootstrap.destination.name}",
                                style = MaterialTheme.typography.bodyLarge,
                                color = NaviInk,
                            )
                            UncertaintyText(bootstrap.areaName)
                        }
                    }
                }
            }
        }

        Spacer(Modifier.height(NaviDimens.Space20))
        TrustBanner(
            text = bootstrap?.disclaimer
                ?: "현재 데이터는 실증 구역 기준이며 일부는 미검증입니다.",
        )
        Spacer(Modifier.height(NaviDimens.Space32))
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// 제보 탭 — 작성 진입과 내 제보 상태
// ─────────────────────────────────────────────────────────────────────────────

@Composable
fun ReportHubScreen(
    session: NaviSessionState,
    onWriteReport: () -> Unit,
) {
    val candidate = session.observation
    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(NaviCanvas),
    ) {
        NaviTopBar(title = "제보")
        Column(
            modifier = Modifier
                .fillMaxSize()
                .verticalScroll(rememberScrollState())
                .padding(NaviDimens.ScreenPadding),
            verticalArrangement = Arrangement.spacedBy(NaviDimens.Space16),
        ) {
            InfoBanner(
                "제보는 검수 후보로 저장돼요. 사람 검수를 통과해야 다른 사용자의 경로에 반영됩니다. " +
                    "내 이번 이동에는 바로 적용돼요.",
            )

            Row(horizontalArrangement = Arrangement.spacedBy(NaviDimens.Space8)) {
                ReviewCountCard(
                    modifier = Modifier.weight(1f),
                    count = if (candidate != null) 1 else 0,
                    label = "검수 대기",
                    tone = NaviCaution,
                    container = NaviCautionSoft,
                )
                ReviewCountCard(
                    modifier = Modifier.weight(1f),
                    count = 0,
                    label = "반영됨",
                    tone = NaviPass,
                    container = NaviPassSoft,
                )
                ReviewCountCard(
                    modifier = Modifier.weight(1f),
                    count = 0,
                    label = "반려",
                    tone = NaviUnknown,
                    container = NaviUnknownSoft,
                )
            }

            Text("내 제보", style = MaterialTheme.typography.labelMedium, color = NaviInkMuted)
            if (candidate == null) {
                SoftGlass {
                    Column {
                        Text("아직 보낸 제보가 없어요", style = MaterialTheme.typography.bodyLarge, color = NaviInk)
                        Spacer(Modifier.height(NaviDimens.Space4))
                        UncertaintyText("이동 중 길이 막혔다면 바로 알려주세요")
                    }
                }
            } else {
                SoftGlass {
                    Column {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Text(
                                text = candidate.type,
                                style = MaterialTheme.typography.titleMedium,
                                color = NaviInk,
                                modifier = Modifier.weight(1f),
                            )
                            StatusPill(
                                symbol = "!",
                                text = candidate.status,
                                foreground = NaviCaution,
                                background = NaviCautionSoft,
                            )
                        }
                        Spacer(Modifier.height(NaviDimens.Space4))
                        UncertaintyText("구간 ${candidate.edgeId} · 검수 통과 전까지 공용 경로에 반영되지 않아요")
                    }
                }
            }

            PrimaryActionButton("현장 제보하기", onWriteReport)
            CenteredNote("제보가 승인되면 알림으로 알려드려요.")
            Spacer(Modifier.height(NaviDimens.Space24))
        }
    }
}

@Composable
private fun ReviewCountCard(
    count: Int,
    label: String,
    tone: Color,
    container: Color,
    modifier: Modifier = Modifier,
) {
    Box(
        modifier = modifier
            .background(container, RoundedCornerShape(NaviDimens.RadiusControl))
            .padding(NaviDimens.Space12),
    ) {
        Column {
            Text("$count", style = MaterialTheme.typography.headlineSmall, color = tone)
            Text(label, style = MaterialTheme.typography.labelMedium, color = tone)
        }
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// 내 정보 — 이동 조건 · 저장과 기록 · 안내 · 접근성 · 데이터
// ─────────────────────────────────────────────────────────────────────────────

@Composable
fun ProfileScreen(
    session: NaviSessionState,
    onEditProfile: () -> Unit,
) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(NaviCanvas),
    ) {
        NaviTopBar(title = "내 정보")
        Column(
            modifier = Modifier
                .fillMaxSize()
                .verticalScroll(rememberScrollState())
                .padding(NaviDimens.ScreenPadding),
            verticalArrangement = Arrangement.spacedBy(NaviDimens.Space16),
        ) {
            FocusGlass(
                modifier = Modifier
                    .fillMaxWidth()
                    .clickable(onClick = onEditProfile)
                    .semantics { role = Role.Button },
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Column(Modifier.weight(1f)) {
                        Text("내 이동 조건", style = MaterialTheme.typography.labelMedium, color = NaviInkMuted)
                        Spacer(Modifier.height(2.dp))
                        Text(
                            text = if (session.profile == "wheelchair") "휠체어 · 계단 제외" else "일반 보행",
                            style = MaterialTheme.typography.titleMedium,
                            color = NaviInk,
                        )
                    }
                    Text("›", style = MaterialTheme.typography.headlineSmall, color = NaviBlue)
                }
            }

            SettingsGroup("안내") {
                SettingsRow("음성 안내", "회전·위험 구간을 소리로 알려줘요", "켜짐")
                NaviHairline()
                SettingsRow("회전·위험 구간 진동", "화면을 보지 않아도 구분되는 패턴", "켜짐")
                NaviHairline()
                SettingsRow("안내 시작 시 AR 자동 전환", "카메라 권한이 있을 때만", "꺼짐")
            }

            SettingsGroup("접근성") {
                SettingsRow("글자 크기", "앱이 시스템 설정을 덮어쓰지 않아요", "시스템 따름")
                NaviHairline()
                SettingsRow("움직임 줄이기", "반복 애니메이션을 중지해요", "시스템 따름")
                NaviHairline()
                SettingsRow("고대비 모드", "유리 효과를 불투명 면으로 바꿔요", "시스템 따름")
            }

            SettingsGroup("데이터") {
                SettingsRow(
                    title = "데이터 모드",
                    caption = session.bootstrap?.source ?: "연결 대기",
                    value = if (session.bootstrap != null) "실데이터" else "—",
                )
                NaviHairline()
                SettingsRow(
                    title = "서비스 범위",
                    caption = "이 범위 밖에서는 경로를 계산하지 않아요",
                    value = session.bootstrap?.areaName ?: "—",
                )
            }

            TrustBanner(
                "카메라 영상은 화면 표시에만 쓰고 저장·전송하지 않아요. 위치는 앱 사용 중에만 받습니다.",
            )
            Spacer(Modifier.height(NaviDimens.Space24))
        }
    }
}

@Composable
private fun SettingsGroup(
    title: String,
    content: @Composable () -> Unit,
) {
    Column {
        Text(title, style = MaterialTheme.typography.labelMedium, color = NaviInkMuted)
        Spacer(Modifier.height(NaviDimens.Space8))
        SoftGlass { Column { content() } }
    }
}

@Composable
private fun SettingsRow(
    title: String,
    caption: String,
    value: String,
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .heightIn(min = NaviDimens.ListItemHeight)
            .padding(vertical = NaviDimens.Space8),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Column(Modifier.weight(1f)) {
            Text(title, style = MaterialTheme.typography.bodyLarge, color = NaviInk)
            UncertaintyText(caption)
        }
        Spacer(Modifier.width(NaviDimens.Space12))
        Text(value, style = MaterialTheme.typography.labelMedium, color = NaviBlue)
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// 예외 상태 — 앱은 사용자의 Hard Constraint를 임의로 완화하지 않는다
// ─────────────────────────────────────────────────────────────────────────────

/** U-1 · 현재 조건을 모두 만족하는 경로가 없음. */
@Composable
fun NoAccessibleRouteScreen(
    blockingReasons: List<String>,
    onEditConditions: () -> Unit,
    onOpenMap: () -> Unit,
    onBack: () -> Unit,
) = ExceptionScaffold(title = "경로 결과", onBack = onBack) {
    ExceptionPanel(
        title = "현재 조건을 모두 만족하는\n경로가 없어요.",
        body = "조건을 대신 완화하지 않았어요. 어떻게 할지 직접 정해 주세요.",
        tone = NaviBlock,
        container = NaviBlockSoft,
        blockingReasons = blockingReasons,
        primaryLabel = "이동 조건 수정하기",
        onPrimary = onEditConditions,
        secondaryLabel = "지도에서 직접 확인",
        onSecondary = onOpenMap,
    )
}

/** U-2 · 재탐색했는데도 갈 수 있는 길이 없음. */
@Composable
fun RerouteFailedScreen(
    onGoBackAndRetry: () -> Unit,
    onRelaxConditions: () -> Unit,
    onFinish: () -> Unit,
    onBack: () -> Unit,
) = ExceptionScaffold(title = "재탐색", onBack = onBack) {
    ExceptionPanel(
        title = "지금 위치에서 갈 수 있는\n다른 길이 없어요.",
        body = "앞은 방금 제보하신 구간이고, 남은 우회로도 조건을 만족하지 않아요. 조건을 대신 풀지 않았습니다.",
        tone = NaviBlock,
        container = NaviBlockSoft,
        primaryLabel = "되돌아가서 다시 찾기",
        onPrimary = onGoBackAndRetry,
        secondaryLabel = "조건을 잠시 완화하기",
        onSecondary = onRelaxConditions,
        tertiaryLabel = "안내 종료",
        onTertiary = onFinish,
    )
}

/** U-3 · 위치가 흔들려 방향 안내를 멈춘 상태. */
@Composable
fun LocationUncertainPanel(
    accuracyMeters: Float?,
    onPickOnMap: () -> Unit,
    onRetry: () -> Unit,
    modifier: Modifier = Modifier,
) {
    ExceptionPanel(
        modifier = modifier,
        title = "현재 위치가 정확하지 않아요",
        body = "위치가 흔들리는 동안 틀릴 수 있는 안내를 그럴듯하게 보여주지 않습니다. " +
            "경로와 남은 거리는 마지막으로 확인된 위치 기준이에요.",
        tone = NaviCaution,
        container = NaviCautionSoft,
        blockingReasons = listOfNotNull(
            accuracyMeters?.let { "오차 ±${it.toInt()}m · 건물 사이에서는 흔한 일이에요" },
            "하늘이 보이는 곳으로 이동하면 정확도가 올라가요",
        ),
        primaryLabel = "다시 시도",
        onPrimary = onRetry,
        secondaryLabel = "지도에서 위치 지정",
        onSecondary = onPickOnMap,
    )
}

/** U-4 · 네트워크가 끊겨 저장된 경로로만 안내하는 상태. */
@Composable
fun OfflineCachedPanel(
    onRetryConnection: () -> Unit,
    modifier: Modifier = Modifier,
) {
    ExceptionPanel(
        modifier = modifier,
        title = "저장된 경로로 안내 중이에요",
        body = "지금은 재탐색을 할 수 없어요. 길이 막혀도 새 경로를 계산하지 못합니다. " +
            "제보는 기기에 저장했다가 연결되면 보낼게요.",
        tone = NaviUnknown,
        container = NaviUnknownSoft,
        primaryLabel = "다시 연결",
        onPrimary = onRetryConnection,
    )
}

/** U-5 · 카메라가 주변을 인식하지 못하는 상태. 추측해서 그리지 않는다. */
@Composable
fun ArTrackingLostPanel(
    onSwitchToMap: () -> Unit,
    onRetryCamera: () -> Unit,
    modifier: Modifier = Modifier,
) {
    ExceptionPanel(
        modifier = modifier,
        title = "카메라가 주변을 인식하지 못해요",
        body = "방향을 추측해서 그리지 않습니다. 정확하지 않은 화살표를 보여주는 것보다 " +
            "지금 정확하지 않다고 알리는 것이 안전해요.",
        tone = NaviCaution,
        container = NaviCautionSoft,
        blockingReasons = listOf(
            "음성 안내 · 진동 · 남은 거리 계산은 계속돼요",
            "카메라 위 방향 오버레이만 중단했어요",
        ),
        primaryLabel = "지도 안내로 계속",
        onPrimary = onSwitchToMap,
        tertiaryLabel = "카메라 다시 시도",
        onTertiary = onRetryCamera,
    )
}

/** U-6 · 안내 경로에서 벗어난 상태. 자동으로 다시 계산하지 않는다. */
@Composable
fun OffRoutePanel(
    distanceFromRouteMeters: Int,
    onReturnToRoute: () -> Unit,
    onRerouteHere: () -> Unit,
    modifier: Modifier = Modifier,
) {
    ExceptionPanel(
        modifier = modifier,
        title = "안내 경로에서 벗어났어요",
        body = "자동으로 다시 계산하지 않았어요. 지금 위치에서 새로 찾으면 조건을 만족하는 경로가 더 길어질 수 있어요.",
        tone = NaviCaution,
        container = NaviCautionSoft,
        blockingReasons = listOf("경로에서 약 ${distanceFromRouteMeters}m 떨어져 있어요"),
        primaryLabel = "여기서 재탐색",
        onPrimary = onRerouteHere,
        secondaryLabel = "경로로 복귀",
        onSecondary = onReturnToRoute,
    )
}

@Composable
private fun ExceptionScaffold(
    title: String,
    onBack: () -> Unit,
    content: @Composable () -> Unit,
) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(NaviCanvas),
    ) {
        NaviTopBar(title = title, onBack = onBack)
        Column(
            modifier = Modifier
                .fillMaxSize()
                .verticalScroll(rememberScrollState())
                .padding(NaviDimens.ScreenPadding),
        ) {
            Spacer(Modifier.height(NaviDimens.Space16))
            content()
            Spacer(Modifier.height(NaviDimens.Space32))
        }
    }
}

private fun formatDistanceShort(value: Double): String = if (value >= 1_000) {
    "%.1fkm".format(value / 1_000)
} else {
    "${value.toInt()}m"
}
