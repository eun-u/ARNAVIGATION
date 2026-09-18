package kr.co.navi.mobility.ui.screens

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawing
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.FilterChip
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.role
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import kr.co.navi.mobility.data.model.GraphEnrichmentCandidateDto
import kr.co.navi.mobility.data.model.GraphEnrichmentSimulationResponseDto
import kr.co.navi.mobility.ui.GraphCandidateViewModel
import kr.co.navi.mobility.ui.GraphCandidateFilter
import kr.co.navi.mobility.ui.RankedGraphCandidateImpact
import kr.co.navi.mobility.ui.components.GraphCandidateImpactMap
import kr.co.navi.mobility.ui.components.NaviTopBar
import kr.co.navi.mobility.ui.components.SectionCard
import kr.co.navi.mobility.ui.components.StatusPill
import kr.co.navi.mobility.ui.components.TrustBanner
import kr.co.navi.mobility.ui.theme.NaviBlock
import kr.co.navi.mobility.ui.theme.NaviBlockSoft
import kr.co.navi.mobility.ui.theme.NaviBlue
import kr.co.navi.mobility.ui.theme.NaviBlueSoft
import kr.co.navi.mobility.ui.theme.NaviCaution
import kr.co.navi.mobility.ui.theme.NaviCautionSoft
import kr.co.navi.mobility.ui.theme.NaviDimens
import kr.co.navi.mobility.ui.theme.NaviInk
import kr.co.navi.mobility.ui.theme.NaviInkMuted
import kr.co.navi.mobility.ui.theme.NaviLine
import kr.co.navi.mobility.ui.theme.NaviMetricTextStyle
import kr.co.navi.mobility.ui.theme.NaviPass
import kr.co.navi.mobility.ui.theme.NaviPassSoft
import kr.co.navi.mobility.ui.theme.NaviSurfaceRaised
import kr.co.navi.mobility.ui.theme.NaviViolet
import kr.co.navi.mobility.ui.theme.NaviVioletSoft
import kr.co.navi.mobility.ui.rankGraphCandidateImpacts
import kr.co.navi.mobility.ui.filterGraphCandidates
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.doubleOrNull

@Composable
fun GraphCandidateScreen(
    viewModel: GraphCandidateViewModel,
    onBack: () -> Unit,
) {
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()
    val visibleCandidates = filterGraphCandidates(uiState.candidates, uiState.selectedFilter)
    val selectedCandidate = uiState.candidates.firstOrNull {
        it.candidateId == uiState.selectedCandidateId
    }
    val rankedImpacts = rankGraphCandidateImpacts(
        filterGraphCandidates(uiState.candidates, GraphCandidateFilter.IMPACT),
        uiState.simulationsByCandidateId,
    )

    Scaffold(
        contentWindowInsets = WindowInsets.safeDrawing,
        topBar = { NaviTopBar(title = "공간데이터 후보", onBack = onBack) },
    ) { padding ->
        if (uiState.loading) {
            Column(
                modifier = Modifier.fillMaxSize().padding(padding),
                verticalArrangement = Arrangement.Center,
                horizontalAlignment = Alignment.CenterHorizontally,
            ) {
                CircularProgressIndicator(color = NaviViolet)
                Spacer(Modifier.height(NaviDimens.Space12))
                Text("검토 전 후보를 불러오고 있습니다", color = NaviInkMuted)
            }
            return@Scaffold
        }

        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .verticalScroll(rememberScrollState()),
        ) {
            GraphCandidateImpactMap(
                candidates = visibleCandidates,
                selectedCandidateId = uiState.selectedCandidateId,
                baseline = uiState.simulation?.baseline,
                simulated = uiState.simulation?.simulated,
                modifier = Modifier.fillMaxWidth().height(310.dp),
            )
            Column(
                modifier = Modifier.padding(
                    horizontal = NaviDimens.Space20,
                    vertical = NaviDimens.Space20,
                ),
                verticalArrangement = Arrangement.spacedBy(NaviDimens.Space16),
            ) {
                Text(
                    if (uiState.selectedFilter == GraphCandidateFilter.IMPACT) {
                        "후보가 경로를 바꾸는지 시험합니다"
                    } else {
                        "공간 근거를 지도에서 확인합니다"
                    },
                    style = MaterialTheme.typography.headlineSmall,
                    color = NaviInk,
                    modifier = Modifier.semantics { heading() },
                )
                TrustBanner(
                    if (uiState.selectedFilter == GraphCandidateFilter.IMPACT) {
                        "공식 공간자료를 Graph에 연결한 검토 전 후보입니다. " +
                            "경사 계산은 민감도 시험일 뿐이며 공유 Graph를 변경하지 않습니다."
                    } else {
                        "보행공간·횡단시설·연석의 위치 또는 존재 근거입니다. " +
                            "통과 가능 여부나 Routing 속성으로 자동 해석하지 않습니다."
                    },
                )

                uiState.summary?.let { summary ->
                    Column(verticalArrangement = Arrangement.spacedBy(NaviDimens.Space8)) {
                        Row(horizontalArrangement = Arrangement.spacedBy(NaviDimens.Space8)) {
                            StatusPill(
                                symbol = "◇",
                                text = "영향 시험 ${summary.routeAffectingCandidateCount}건",
                                foreground = NaviCaution,
                                background = NaviCautionSoft,
                            )
                            StatusPill(
                                symbol = "△",
                                text = "DEM 진단 ${summary.diagnosticCandidateCount}건",
                                foreground = NaviViolet,
                                background = NaviVioletSoft,
                            )
                        }
                        StatusPill(
                            symbol = "▣",
                            text = "정사영상 참조 ${summary.orthophotoReferencedCandidateCount} / ${summary.candidateCount}",
                            foreground = NaviBlue,
                            background = NaviBlueSoft,
                        )
                    }
                }

                GraphCandidateFilterBar(
                    candidates = uiState.candidates,
                    selected = uiState.selectedFilter,
                    onSelect = viewModel::selectFilter,
                )

                if (visibleCandidates.isEmpty()) {
                    EmptyCandidatePanel()
                } else if (uiState.selectedFilter == GraphCandidateFilter.IMPACT) {
                    GraphCandidateRankingPanel(
                        impacts = rankedImpacts,
                        loading = uiState.rankingLoading,
                        failedCandidateIds = uiState.rankingFailedCandidateIds,
                        selectedCandidateId = uiState.selectedCandidateId,
                        onSelectCandidate = viewModel::selectCandidate,
                    )
                } else {
                    GraphEvidenceCandidatePanel(
                        candidates = visibleCandidates,
                        selectedCandidateId = uiState.selectedCandidateId,
                        onSelectCandidate = viewModel::selectCandidate,
                    )
                }

                if (selectedCandidate == null && visibleCandidates.isNotEmpty()) {
                    SectionCard {
                        Text(
                            if (uiState.selectedFilter == GraphCandidateFilter.IMPACT) {
                                "후보를 선택하면 해당 Edge의 양 끝점에서 현재 경로와 임시 적용 경로를 비교합니다."
                            } else {
                                "근거 후보를 선택하면 원자료 매핑과 정사영상 참조 위치를 확인할 수 있습니다."
                            },
                            style = MaterialTheme.typography.bodyMedium,
                            color = NaviInkMuted,
                        )
                    }
                } else if (selectedCandidate != null) {
                    if (selectedCandidate.simulationAllowed) {
                        GraphCandidateSimulationPanel(
                            candidate = selectedCandidate,
                            simulation = uiState.simulation,
                            loading = uiState.simulating,
                        )
                    }
                    GraphCandidateEvidencePanel(selectedCandidate)
                }

                uiState.error?.let { message ->
                    Surface(
                        color = NaviBlockSoft,
                        shape = MaterialTheme.shapes.small,
                        border = BorderStroke(1.dp, NaviBlock.copy(alpha = 0.22f)),
                    ) {
                        Column(Modifier.fillMaxWidth().padding(NaviDimens.Space16)) {
                            Text("후보 계산을 확인해주세요", color = NaviBlock, fontWeight = FontWeight.Bold)
                            Spacer(Modifier.height(NaviDimens.Space4))
                            Text(message, color = NaviInk, style = MaterialTheme.typography.bodySmall)
                            if (uiState.candidates.isEmpty()) {
                                Spacer(Modifier.height(NaviDimens.Space8))
                                OutlinedButton(onClick = viewModel::loadCandidates) { Text("다시 시도") }
                            }
                        }
                    }
                }
                Spacer(Modifier.height(NaviDimens.Space24))
            }
        }
    }
}

@Composable
private fun GraphCandidateFilterBar(
    candidates: List<GraphEnrichmentCandidateDto>,
    selected: GraphCandidateFilter,
    onSelect: (GraphCandidateFilter) -> Unit,
) {
    val labels = listOf(
        GraphCandidateFilter.IMPACT to "영향 시험",
        GraphCandidateFilter.PEDESTRIAN to "보행공간",
        GraphCandidateFilter.CROSSING to "횡단시설",
        GraphCandidateFilter.CURB to "연석",
    )
    Column(verticalArrangement = Arrangement.spacedBy(NaviDimens.Space8)) {
        Text("지도 레이어", style = MaterialTheme.typography.titleMedium, color = NaviInk)
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .horizontalScroll(rememberScrollState()),
            horizontalArrangement = Arrangement.spacedBy(NaviDimens.Space8),
        ) {
            labels.forEach { (filter, label) ->
                val count = filterGraphCandidates(candidates, filter).size
                FilterChip(
                    selected = selected == filter,
                    onClick = { onSelect(filter) },
                    label = { Text("$label $count") },
                )
            }
        }
    }
}

@Composable
private fun GraphEvidenceCandidatePanel(
    candidates: List<GraphEnrichmentCandidateDto>,
    selectedCandidateId: String?,
    onSelectCandidate: (String) -> Unit,
) {
    val listedCandidates = candidates.take(EVIDENCE_LIST_LIMIT)
    SectionCard {
        Column(verticalArrangement = Arrangement.spacedBy(NaviDimens.Space12)) {
            Text("근거 후보", style = MaterialTheme.typography.titleMedium, color = NaviInk)
            Text(
                "지도에는 ${candidates.size}건 전체를 표시합니다. 목록은 위치순 앞 ${listedCandidates.size}건입니다.",
                style = MaterialTheme.typography.bodySmall,
                color = NaviInkMuted,
            )
            listedCandidates.forEachIndexed { index, candidate ->
                if (index > 0) HorizontalDivider(color = NaviLine)
                Surface(
                    modifier = Modifier
                        .fillMaxWidth()
                        .heightIn(min = 56.dp)
                        .clickable { onSelectCandidate(candidate.candidateId) }
                        .semantics { role = Role.Button },
                    color = if (candidate.candidateId == selectedCandidateId) {
                        NaviBlueSoft
                    } else {
                        MaterialTheme.colorScheme.surface
                    },
                    shape = MaterialTheme.shapes.small,
                    border = if (candidate.candidateId == selectedCandidateId) {
                        BorderStroke(1.5.dp, NaviBlue)
                    } else {
                        null
                    },
                ) {
                    Row(
                        modifier = Modifier.padding(NaviDimens.Space12),
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(NaviDimens.Space12),
                    ) {
                        Text(candidateTypeSymbol(candidate.type), color = candidateTypeColor(candidate.type))
                        Column(Modifier.weight(1f)) {
                            Text(
                                candidateTypeLabel(candidate.type),
                                style = MaterialTheme.typography.titleSmall,
                                color = NaviInk,
                            )
                            Text(
                                "근거 ${candidate.evidenceCount}건 · 영상 ${candidate.visualEvidenceRefs.size}건",
                                style = MaterialTheme.typography.bodySmall,
                                color = NaviInkMuted,
                            )
                        }
                        Text("보기", style = MaterialTheme.typography.labelMedium, color = NaviBlue)
                    }
                }
            }
        }
    }
}

@Composable
fun GraphCandidateRankingPanel(
    impacts: List<RankedGraphCandidateImpact>,
    loading: Boolean,
    failedCandidateIds: Set<String>,
    selectedCandidateId: String?,
    onSelectCandidate: (String) -> Unit,
    modifier: Modifier = Modifier,
) {
    SectionCard(modifier) {
        Column(verticalArrangement = Arrangement.spacedBy(NaviDimens.Space12)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Column(Modifier.weight(1f)) {
                    Text("전체 영향 순위", style = MaterialTheme.typography.titleMedium, color = NaviInk)
                    Text(
                        "R = (경로 단절, 추가 거리, 경로 변경) 순으로 정렬",
                        style = MaterialTheme.typography.bodySmall,
                        color = NaviInkMuted,
                    )
                }
                if (loading) {
                    CircularProgressIndicator(
                        modifier = Modifier.height(22.dp).width(22.dp),
                        color = NaviCaution,
                        strokeWidth = 2.5.dp,
                    )
                } else {
                    StatusPill("!", "미검증 ${impacts.size}건", NaviCaution, NaviCautionSoft)
                }
            }

            val completed = impacts.mapNotNull { it.simulation }
            if (loading) {
                Text(
                    "각 후보 Edge의 양 끝점에서 접근성 경로를 계산하고 있습니다.",
                    style = MaterialTheme.typography.bodySmall,
                    color = NaviInkMuted,
                )
            } else {
                val disconnected = completed.count { it.baseline != null && it.simulated == null }
                val detoured = completed.count { (it.differenceM ?: 0.0) > 0.0 }
                val unchanged = completed.count { !it.routeChanged }
                Text(
                    "경로 단절 $disconnected · 우회 증가 $detoured · 변화 없음 $unchanged" +
                        if (failedCandidateIds.isNotEmpty()) " · 계산 실패 ${failedCandidateIds.size}" else "",
                    style = MaterialTheme.typography.labelMedium,
                    color = NaviInk,
                )
            }

            impacts.forEachIndexed { index, impact ->
                if (index > 0) HorizontalDivider(color = NaviLine)
                GraphCandidateRankingRow(
                    rank = index + 1,
                    impact = impact,
                    failed = impact.candidate.candidateId in failedCandidateIds,
                    selected = impact.candidate.candidateId == selectedCandidateId,
                    onClick = { onSelectCandidate(impact.candidate.candidateId) },
                )
            }
        }
    }
}

@Composable
private fun GraphCandidateRankingRow(
    rank: Int,
    impact: RankedGraphCandidateImpact,
    failed: Boolean,
    selected: Boolean,
    onClick: () -> Unit,
) {
    val badge = impactBadge(impact.simulation, failed)
    Surface(
        modifier = Modifier
            .fillMaxWidth()
            .heightIn(min = 64.dp)
            .clickable(onClick = onClick)
            .semantics { role = Role.Button },
        color = if (selected) NaviVioletSoft else MaterialTheme.colorScheme.surface,
        shape = MaterialTheme.shapes.small,
        border = if (selected) BorderStroke(1.5.dp, NaviViolet) else null,
    ) {
        Row(
            modifier = Modifier.padding(NaviDimens.Space12),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(NaviDimens.Space12),
        ) {
            Surface(
                color = if (selected) NaviViolet else NaviSurfaceRaised,
                shape = CircleShape,
            ) {
                Text(
                    rank.toString(),
                    modifier = Modifier.padding(horizontal = 10.dp, vertical = 5.dp),
                    style = MaterialTheme.typography.labelLarge,
                    color = if (selected) MaterialTheme.colorScheme.onPrimary else NaviInk,
                    fontWeight = FontWeight.Bold,
                )
            }
            Column(Modifier.weight(1f)) {
                Text(
                    candidateTypeLabel(impact.candidate.type),
                    style = MaterialTheme.typography.titleSmall,
                    color = NaviInk,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
                Text(
                    "근거 ${impact.candidate.evidenceCount}건 · ${impact.candidate.edgeId.take(16)}…",
                    style = MaterialTheme.typography.bodySmall,
                    color = NaviInkMuted,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
            }
            StatusPill(badge.symbol, badge.text, badge.foreground, badge.background)
        }
    }
}

private data class ImpactBadge(
    val symbol: String,
    val text: String,
    val foreground: androidx.compose.ui.graphics.Color,
    val background: androidx.compose.ui.graphics.Color,
)

private fun impactBadge(
    simulation: GraphEnrichmentSimulationResponseDto?,
    failed: Boolean,
): ImpactBadge = when {
    failed -> ImpactBadge("×", "계산 실패", NaviBlock, NaviBlockSoft)
    simulation == null -> ImpactBadge("…", "계산 중", NaviCaution, NaviCautionSoft)
    simulation.baseline != null && simulation.simulated == null ->
        ImpactBadge("!", "경로 단절", NaviBlock, NaviBlockSoft)
    (simulation.differenceM ?: 0.0) > 0.0 ->
        ImpactBadge("+", formatCandidateDistance(simulation.differenceM!!), NaviViolet, NaviVioletSoft)
    simulation.routeChanged -> ImpactBadge("↻", "경로 변경", NaviViolet, NaviVioletSoft)
    else -> ImpactBadge("–", "변화 없음", NaviInkMuted, NaviSurfaceRaised)
}

@Composable
fun GraphCandidateEvidencePanel(
    candidate: GraphEnrichmentCandidateDto,
    modifier: Modifier = Modifier,
) {
    SectionCard(modifier) {
        Column(verticalArrangement = Arrangement.spacedBy(NaviDimens.Space12)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Column(Modifier.weight(1f)) {
                    Text("선택 후보 근거", style = MaterialTheme.typography.titleMedium, color = NaviInk)
                    Text(
                        candidate.candidateId,
                        style = MaterialTheme.typography.labelSmall.copy(fontFamily = FontFamily.Monospace),
                        color = NaviInkMuted,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                    )
                }
                StatusPill("!", "검토 전", NaviCaution, NaviCautionSoft)
            }

            Surface(color = NaviCautionSoft, shape = MaterialTheme.shapes.small) {
                Column(
                    modifier = Modifier.fillMaxWidth().padding(NaviDimens.Space12),
                    verticalArrangement = Arrangement.spacedBy(NaviDimens.Space4),
                ) {
                    Text("제안 변경", style = MaterialTheme.typography.labelMedium, color = NaviCaution)
                    Text(
                        candidateAttributeChanges(candidate),
                        style = MaterialTheme.typography.titleSmall,
                        color = NaviInk,
                    )
                    Text(
                        if (candidate.approvalEligible) {
                            "승인 전에는 공유 Graph에 반영할 수 없습니다."
                        } else {
                            "90m DEM 진단값으로, 사람 검토 후에도 이 값 자체를 Graph 속성으로 승인할 수 없습니다."
                        },
                        style = MaterialTheme.typography.bodySmall,
                        color = NaviInkMuted,
                    )
                }
            }

            if (candidate.qualityFlags.isNotEmpty()) {
                Text(
                    "품질 제한 · ${candidate.qualityFlags.joinToString(" · ") { qualityFlagLabel(it) }}",
                    style = MaterialTheme.typography.labelMedium,
                    color = NaviCaution,
                )
            }

            Text(
                "매핑 ${mappingStatusLabel(candidate.mappingStatus)} · ${mappingQualityLabel(candidate.mappingQuality)}",
                style = MaterialTheme.typography.labelMedium,
                color = NaviInk,
            )

            candidate.evidence.forEachIndexed { index, evidence ->
                EvidenceItem(index + 1, evidence)
            }

            if (candidate.evidence.isEmpty()) {
                Text(
                    "상세 근거 레코드가 없습니다.",
                    style = MaterialTheme.typography.bodySmall,
                    color = NaviInkMuted,
                )
            }

            HorizontalDivider(color = NaviLine)
            Text("정사영상 QA 참조", style = MaterialTheme.typography.titleSmall, color = NaviInk)
            if (candidate.visualEvidenceRefs.isEmpty()) {
                Text(
                    "이 후보 위치에 연결된 정사영상 참조가 없습니다.",
                    style = MaterialTheme.typography.bodySmall,
                    color = NaviInkMuted,
                )
            } else {
                candidate.visualEvidenceRefs.forEach { reference ->
                    Surface(color = NaviBlueSoft, shape = MaterialTheme.shapes.small) {
                        Column(
                            modifier = Modifier.fillMaxWidth().padding(NaviDimens.Space12),
                            verticalArrangement = Arrangement.spacedBy(NaviDimens.Space4),
                        ) {
                            Text(
                                "도엽 ${reference.sheetId} · pixel ${reference.pixelCol}, ${reference.pixelRow}",
                                style = MaterialTheme.typography.titleSmall,
                                color = NaviBlue,
                            )
                            Text(
                                "25cm급 시각 QA 위치 참조 · 독립 기준점 RMSE 미측정",
                                style = MaterialTheme.typography.bodySmall,
                                color = NaviInk,
                            )
                            Text(
                                "형상 자동 보정 불가 · Graph 반영 불가",
                                style = MaterialTheme.typography.labelMedium,
                                color = NaviInkMuted,
                            )
                        }
                    }
                }
            }

            Text(
                "후보 생성 ${candidate.createdAt.replace('T', ' ')}",
                style = MaterialTheme.typography.bodySmall,
                color = NaviInkMuted,
            )
        }
    }
}

@Composable
private fun EvidenceItem(index: Int, evidence: JsonObject) {
    val sourceType = evidence.text("source_type")
    val year = evidence.text("source_year") ?: "연도 미상"
    val sheet = evidence.text("source_sheet_id") ?: "도엽 미상"
    val featureCode = evidence.text("source_feature_code") ?: "코드 미상"
    val distance = evidence.number("mapping_distance_m")
    val score = evidence.number("mapping_score")
    Surface(color = NaviSurfaceRaised, shape = MaterialTheme.shapes.small) {
        Column(
            modifier = Modifier.fillMaxWidth().padding(NaviDimens.Space12),
            verticalArrangement = Arrangement.spacedBy(NaviDimens.Space4),
        ) {
            Text(
                "근거 $index · ${sourceTypeLabel(sourceType)}",
                style = MaterialTheme.typography.titleSmall,
                color = NaviInk,
            )
            if (sourceType == "ngii_dem") {
                Text(
                    "파생 경사 ${evidence.number("slope_pct_abs_candidate")?.let { "%.2f%%".format(it) } ?: "미상"}" +
                        " · DEM 해상도 ${evidence.number("dem_resolution_m")?.let { "%.0fm".format(it) } ?: "미상"}",
                    style = MaterialTheme.typography.bodySmall,
                    color = NaviInk,
                )
                Text(
                    "보도 실측값 아님 · Hard Constraint 사용 불가",
                    style = MaterialTheme.typography.bodySmall,
                    color = NaviCaution,
                )
            } else {
                Text(
                    "$year 제작 · 도엽 $sheet · 객체코드 $featureCode",
                    style = MaterialTheme.typography.bodySmall,
                    color = NaviInkMuted,
                )
                Text(
                    "Edge 매칭 거리 ${distance?.let { "%.2fm".format(it) } ?: "미상"}" +
                        " · 매칭 점수 ${score?.let { "%.3f".format(it) } ?: "미상"}",
                    style = MaterialTheme.typography.bodySmall,
                    color = NaviInk,
                )
            }
            evidence.text("source_dataset_id")?.let { datasetId ->
                Text(
                    "dataset $datasetId",
                    style = MaterialTheme.typography.labelSmall.copy(fontFamily = FontFamily.Monospace),
                    color = NaviInkMuted,
                )
            }
            evidence.text("source_feature_id")?.let { featureId ->
                Text(
                    "feature $featureId",
                    style = MaterialTheme.typography.labelSmall.copy(fontFamily = FontFamily.Monospace),
                    color = NaviInkMuted,
                )
            }
        }
    }
}

@Composable
fun GraphCandidateSimulationPanel(
    candidate: GraphEnrichmentCandidateDto,
    simulation: GraphEnrichmentSimulationResponseDto?,
    loading: Boolean,
    modifier: Modifier = Modifier,
) {
    SectionCard(modifier) {
        Column(verticalArrangement = Arrangement.spacedBy(NaviDimens.Space12)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Column(Modifier.weight(1f)) {
                    Text("후보 영향 시뮬레이션", style = MaterialTheme.typography.titleMedium, color = NaviInk)
                    Text(
                        candidateTypeLabel(candidate.type),
                        style = MaterialTheme.typography.bodySmall,
                        color = NaviInkMuted,
                    )
                }
                StatusPill("◇", "미검증", NaviCaution, NaviCautionSoft)
            }

            if (!candidate.approvalEligible) {
                Surface(color = NaviCautionSoft, shape = MaterialTheme.shapes.small) {
                    Text(
                        "민감도 시험 전용 · 이 경사값은 현장 보도 경사로 승인하거나 공유 Graph에 저장하지 않습니다.",
                        modifier = Modifier.fillMaxWidth().padding(NaviDimens.Space12),
                        style = MaterialTheme.typography.bodySmall,
                        color = NaviCaution,
                        fontWeight = FontWeight.SemiBold,
                    )
                }
            }

            if (loading) {
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(NaviDimens.Space12),
                ) {
                    CircularProgressIndicator(modifier = Modifier.width(24.dp), strokeWidth = 2.5.dp)
                    Text("현재 Graph와 후보 적용 결과를 비교하고 있습니다.", color = NaviInkMuted)
                }
            } else if (simulation != null) {
                val baseline = simulation.baseline
                val simulated = simulation.simulated
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(NaviDimens.Space8),
                ) {
                    ImpactMetric(
                        label = "현재 Graph",
                        value = baseline?.distanceM?.let(::formatCandidateDistance) ?: "경로 없음",
                        modifier = Modifier.weight(1f),
                    )
                    ImpactMetric(
                        label = "후보 임시 적용",
                        value = simulated?.distanceM?.let(::formatCandidateDistance) ?: "경로 없음",
                        modifier = Modifier.weight(1f),
                    )
                }
                val resultText = when {
                    simulated == null -> "접근 가능한 경로가 사라질 수 있습니다"
                    simulation.differenceM != null && simulation.differenceM > 0 ->
                        "+${formatCandidateDistance(simulation.differenceM)} 우회"
                    simulation.routeChanged -> "경로 구성이 변경됩니다"
                    else -> "이 출발·도착에서는 경로 변화가 없습니다"
                }
                StatusPill(
                    symbol = if (simulation.routeChanged) "↻" else "–",
                    text = resultText,
                    foreground = if (simulation.routeChanged) NaviViolet else NaviInkMuted,
                    background = if (simulation.routeChanged) NaviVioletSoft else NaviSurfaceRaised,
                )
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .background(NaviPassSoft, MaterialTheme.shapes.small)
                        .padding(NaviDimens.Space12),
                    horizontalArrangement = Arrangement.spacedBy(NaviDimens.Space8),
                ) {
                    Text("✓", color = NaviPass, fontWeight = FontWeight.Bold)
                    Text(
                        "공유 Graph 변경 없음 · SQLite 변경 없음",
                        style = MaterialTheme.typography.bodySmall,
                        color = NaviPass,
                        fontWeight = FontWeight.SemiBold,
                    )
                }
            }
        }
    }
}

@Composable
private fun ImpactMetric(label: String, value: String, modifier: Modifier = Modifier) {
    Column(
        modifier = modifier
            .background(NaviSurfaceRaised, MaterialTheme.shapes.small)
            .padding(NaviDimens.Space12),
    ) {
        Text(label, style = MaterialTheme.typography.labelMedium, color = NaviInkMuted)
        Spacer(Modifier.height(NaviDimens.Space4))
        Text(value, style = NaviMetricTextStyle, color = NaviInk)
    }
}

@Composable
private fun EmptyCandidatePanel() {
    SectionCard {
        Text(
            "현재 Graph와 일치하는 경로 영향 후보가 없습니다.",
            style = MaterialTheme.typography.bodyMedium,
            color = NaviInkMuted,
        )
    }
}

private fun candidateTypeLabel(type: String): String = when (type) {
    "stairs_attribute_candidate" -> "계단 속성 후보"
    "dem_slope_diagnostic_candidate" -> "DEM 경사 민감도 후보"
    "crosswalk_geometry_evidence" -> "횡단보도 위치 근거"
    "curb_presence_evidence" -> "연석 존재 근거"
    "pedestrian_area_evidence" -> "보행공간 근거"
    "grade_separated_crossing_evidence" -> "입체횡단 구조물 근거"
    else -> type.replace('_', ' ')
}

private fun candidateAttributeChanges(candidate: GraphEnrichmentCandidateDto): String =
    candidate.proposedChanges.entries.joinToString(separator = " · ") { (key, proposed) ->
        val currentLabel = jsonValueLabel(candidate.currentValues[key])
        val proposedLabel = jsonValueLabel(proposed)
        val currentDisplay = if (key == "slope" && currentLabel != "unknown") "$currentLabel%" else currentLabel
        val proposedDisplay = if (key == "slope" && proposedLabel != "unknown") "$proposedLabel%" else proposedLabel
        "${attributeLabel(key)} $currentDisplay → $proposedDisplay"
    }.ifBlank { "경로 속성 변경 없음" }

private fun attributeLabel(key: String): String = when (key) {
    "stairs" -> "계단"
    "blocked" -> "통행 차단"
    "slope" -> "경사"
    "curb_height" -> "턱 높이"
    "width" -> "유효 폭"
    else -> key.replace('_', ' ')
}

private fun jsonValueLabel(value: kotlinx.serialization.json.JsonElement?): String =
    (value as? JsonPrimitive)?.contentOrNull ?: "unknown"

private fun mappingStatusLabel(status: String): String = when (status) {
    "unique" -> "단일 Edge"
    "edge_sampled" -> "Edge별 DEM 샘플"
    "ambiguous" -> "복수 후보"
    "unmatched" -> "미매칭"
    else -> status.replace('_', ' ')
}

private fun mappingQualityLabel(quality: String): String = when (quality) {
    "single_source_unique_match" -> "단일 출처 고유 매칭"
    "multi_source_unique_match" -> "복수 출처 고유 매칭"
    "cross_source_consensus" -> "복수 출처 합의"
    "coarse_dem_context" -> "90m 지형 맥락"
    else -> quality.replace('_', ' ')
}

private fun sourceTypeLabel(sourceType: String?): String = when (sourceType) {
    "ngii_topographic_map" -> "국토지리정보원 수치지형도"
    "ngii_dem" -> "국토지리정보원 DEM"
    "ngii_orthophoto" -> "국토지리정보원 정사영상"
    null -> "출처 미상"
    else -> sourceType.replace('_', ' ')
}

private fun qualityFlagLabel(flag: String): String = when (flag) {
    "coarse_90m_dem" -> "90m 격자"
    "not_hard_constraint_eligible" -> "경로 제약 반영 불가"
    else -> flag.replace('_', ' ')
}

private fun candidateTypeSymbol(type: String): String = when (type) {
    "stairs_attribute_candidate" -> "▤"
    "dem_slope_diagnostic_candidate" -> "△"
    "pedestrian_area_evidence" -> "▰"
    "crosswalk_geometry_evidence" -> "═"
    "grade_separated_crossing_evidence" -> "◇"
    "curb_presence_evidence" -> "┆"
    else -> "○"
}

private fun candidateTypeColor(type: String): androidx.compose.ui.graphics.Color = when (type) {
    "stairs_attribute_candidate" -> NaviBlock
    "dem_slope_diagnostic_candidate" -> NaviViolet
    "pedestrian_area_evidence" -> NaviBlue
    "crosswalk_geometry_evidence" -> NaviPass
    "grade_separated_crossing_evidence" -> NaviViolet
    "curb_presence_evidence" -> NaviCaution
    else -> NaviInkMuted
}

private fun JsonObject.text(key: String): String? =
    (get(key) as? JsonPrimitive)?.contentOrNull

private fun JsonObject.number(key: String): Double? =
    (get(key) as? JsonPrimitive)?.doubleOrNull

private fun formatCandidateDistance(metres: Double): String =
    if (metres >= 1_000) "%.2fkm".format(metres / 1_000) else "%.0fm".format(metres)

private const val EVIDENCE_LIST_LIMIT = 12
