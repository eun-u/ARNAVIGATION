# NaVi 데이터 스키마

## Graph GeoJSON

FeatureCollection의 `metadata`에는 OSM 시점·범위·해시·라이선스와 데모 노드/Edge/예상 거리를 기록합니다.

Node 핵심 필드:

```text
node_id, lat/lon(Point geometry), name, node_type,
source, confidence, verified, display_selectable
```

Edge 핵심 필드:

```text
edge_id, from_node, to_node, length, geometry,
stairs, slope, width, curb_height, surface,
elevator_required, elevator_status,
blocked, block_reason, wheelchair_accessible,
accessibility_status, source, accessibility_source,
confidence, verified, updated_at
```

`source=osm`은 공간 형상의 출처입니다. `accessibility_source=synthetic`은 같은 Edge의 접근성 속성이 실험용임을 뜻합니다. 두 출처를 합쳐 실제 검증 데이터처럼 표현하지 않습니다.

## SQLite

- `app_meta`: schema version, graph revision
- `edge_state`: Graph 원본 위에 적용할 현재 overlay
- `edge_status_history`: 변경 전/후 JSON, actor, source, observation ID, 시각
- `observation_candidates`: AI 또는 수동 현장 후보 payload와 현재 검수 상태
- `observation_reviews`: 사람 판정, 관찰 시각, 근거, 선택 측정값
- `route_sessions`: 요청, 최근 route/comparison, 세션 임시 차단 Edge, graph revision, 24시간 만료

## 접근성 상태

```text
unknown | candidate | verified_pass | verified_block | stale
```

검수 결정은 다음과 같습니다.

```text
pending | approved | rejected | needs_more_evidence
```

후보의 `confidence`는 AI 후보 신뢰도일 뿐 통과 가능 확률이나 검증 완료를 의미하지 않습니다. Android 수동 현장 제보는 AI 추정값이 아니므로 `source=manual_camera`, `confidence=null`, `status=pending`, `verified=false`로 저장합니다.

## 공간데이터 Graph 반영 후보

자동 공간평가 결과는 기존 `ObservationCandidate`와 같은 승인 경계를 따르되, 공유 Graph와 분리된 sidecar에 먼저 기록합니다.

```text
candidate_id
edge_id
type
priority
routing_impact
mapping_quality
candidate_class
simulation_allowed
approval_eligible
quality_flags[]
proposed_changes
current_values
evidence[]
visual_evidence_refs[]
status=pending
verified=false
graph_update_allowed=false
requires_human_review=true
```

현재 후보 유형은 다음과 같습니다.

- `stairs_attribute_candidate`: 공식 수치지형도 계단 객체가 unique 매칭된 Edge에 `stairs=true`를 제안합니다. 승인 전에는 실제 Edge 필드를 바꾸지 않습니다.
- `dem_slope_diagnostic_candidate`: 90m DEM에서 실험 임계값 8%를 넘는 `coarse_context_only` Edge의 절대 경사를 제안값처럼 담되, `candidate_class=diagnostic_sensitivity`, `approval_eligible=false`로 고정합니다. 현장 보도 경사 사실이나 승인 가능한 Graph 속성이 아니며 경로 영향 민감도 시험에만 사용합니다.
- `pedestrian_area_evidence`: 보도/보행공간 geometry 근거이며 통과 가능 판정이 아닙니다.
- `crosswalk_geometry_evidence`: 횡단보도 위치 근거이며 턱 낮춤이나 접근 가능 판정이 아닙니다.
- `curb_presence_evidence`: 연석 존재 근거이며 `curb_height`를 생성하지 않습니다.
- `grade_separated_crossing_evidence`: 육교 등 구조물 근거이며 계단 또는 통행 불가로 단정하지 않습니다.

`data/processed/evaluation/graph_enrichment/anyang_accessibility_graph.candidate.geojson`은 각 Edge에 `candidate_enrichments` 주석만 붙인 비실행 사본입니다. `stairs`, `slope`, `curb_height`, `blocked` 등 Routing 필드는 기준 Graph와 동일하며 기본 `NAVI_GRAPH_PATH`로 사용하지 않습니다.

런타임은 `candidate_bundle.json`의 `baseline_graph_sha256`이 현재 Graph 파일과 정확히 일치할 때만 이 sidecar를 조회용으로 엽니다. 후보 ID 중복, 알 수 없는 Edge, `pending/verified=false/graph_update_allowed=false/requires_human_review=true` 경계 위반, 지원하지 않는 제안 필드가 있으면 서버 시작 시 거부합니다.

`POST /graph-enrichment/simulate`는 클라이언트가 임의 속성값을 보내는 API가 아닙니다. 서버 sidecar에 존재하고 `simulation_allowed=true`인 `candidate_id`만 선택할 수 있습니다. 현재 허용 필드는 `stairs: bool`과 `slope: 0..100`이며, DEM `slope`는 오직 진단 overlay입니다. `proposed_changes={}`인 근거 전용 후보는 시뮬레이션에도 사용할 수 없습니다. 계산은 요청 한정 Edge overlay에만 적용되며 Graph 파일, 메모리 원본, SQLite와 graph revision은 바뀌지 않습니다.

`visual_evidence_refs[]`는 정사영상 원본을 복제하지 않고 후보 위치를 찾아가기 위한 sidecar 참조입니다. `sheet_id`, `pixel_row`, `pixel_col`, raster SHA-256, georeferencing sidecar 경로를 기록합니다. 현재 독립 기준점 RMSE가 없으므로 모든 참조는 `visual_qa_only_provisional_georeferencing`, `geometry_correction_allowed=false`, `verified=false`, `graph_update_allowed=false`입니다. 전체 참조 목록은 `data/processed/evaluation/orthophoto/qa_evidence_manifest.json`에 기록합니다.

Route session의 `temporary_blocked_edges_json`은 해당 사용자의 즉시 우회에만 사용합니다. 공용 `edge_state`를 변경하지 않으며 세션이 만료되면 공유 상태로 승격되지 않습니다.

## 프로필

`backend/app/config/profiles.json`에서 실험 임계값을 변경합니다. `max_slope=8.0`, `min_width=0.9`, `max_curb_height=0.03`은 법적 기준으로 주장하지 않는 PoC 설정값입니다. OSM Edge는 공간망 연결을 위해 허용하지만 미검증 경고를 응답에 포함합니다.
