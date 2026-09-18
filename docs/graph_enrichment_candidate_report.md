# NaVi Graph 반영 후보 결과

생성 시각: `2026-09-18T16:00:00+09:00`

## 결론

현재 자동평가만으로 공유 Graph에 확정 반영한 값은 없습니다. 대신 기존 routing 필드를 유지한 candidate Graph 사본과 Edge별 반영 제안을 생성했습니다.

- 전체 후보: 247개 / 196개 Edge
- 경로 영향 시뮬레이션 후보: 17개
- 이 중 90m DEM 경사 민감도 진단: 12개 (`approval_eligible=false`)
- 근거 전용 후보: 230개
- 정사영상 QA 참조가 연결된 후보: 247개
- 후보 유형: `{"crosswalk_geometry_evidence": 86, "curb_presence_evidence": 12, "dem_slope_diagnostic_candidate": 12, "grade_separated_crossing_evidence": 2, "pedestrian_area_evidence": 130, "stairs_attribute_candidate": 5}`
- 기준 Graph 변경: `false`
- candidate Graph 경로 회귀 동일: `true`
- 국소 Edge OD에서 경로가 달라진 시뮬레이션: 16개

## 후보 유형과 사용 경계

- 수치지형도 계단 객체 5건은 `stairs=true` 제안이며 사람 검토 전에는 반영되지 않습니다.
- DEM 12건은 `slope` 값을 가정해 경로 민감도만 계산합니다. 90m 격자이므로 현장 보도 종단경사로 승인하거나 Hard Constraint에 자동 반영할 수 없습니다.
- 보행공간·횡단시설·연석 230건은 위치/존재 근거이며 Routing 속성을 만들지 않습니다.
- 모든 후보는 `pending`, `verified=false`, `graph_update_allowed=false`입니다.

### 후보 적용 시뮬레이션

각 후보 Edge의 양 끝점을 출발·도착으로 두고 후보 하나만 요청 한정 overlay로 적용했습니다. 아래 결과는 후보가 사실이라는 판정이 아니라 영향 크기를 보는 진단입니다.

| 후보 ID | 유형 | Edge | 적용 전 휠체어 경로 | 후보 적용 후 | 변화 |
|---|---|---|---:|---:|---:|
| GEC-6D02B1ABC8D18556 | DEM 경사 진단 | OSM_E_1150608720_f11c33de91 | 356.1m | no_accessible_route | 경로 없음 |
| GEC-2B62714A72341401 | DEM 경사 진단 | OSM_E_1323539454_861f3a9b41 | 431.5m | no_accessible_route | 경로 없음 |
| GEC-E87317E9CF753C18 | DEM 경사 진단 | OSM_E_1323539455_834b368dd3 | 188.4m | no_accessible_route | 경로 없음 |
| GEC-4C7729164AD257DD | DEM 경사 진단 | OSM_E_1417492465_a7cdf32987 | 190.6m | no_accessible_route | 경로 없음 |
| GEC-2C8A74F4C7D4BCF8 | DEM 경사 진단 | OSM_E_379904055_d0cd1f0846 | 134.8m | no_accessible_route | 경로 없음 |
| GEC-22B39AB22E368810 | DEM 경사 진단 | OSM_E_379904066_b76b13ac6e | 155.2m | no_accessible_route | 경로 없음 |
| GEC-61063192388228C2 | 계단 제안 | OSM_E_379904073_9581b7b371 | 98.1m | 212.2m | +114.1m |
| GEC-456C3271E69E7EDF | 계단 제안 | OSM_E_380194922_e00ee2ab58 | 140.2m | 1346.0m | +1205.8m |
| GEC-CE1DCD49F1BE0C70 | DEM 경사 진단 | OSM_E_484348850_d12ea5bb0b | 171.3m | 361.2m | +189.9m |
| GEC-4B67AFFBA04FD5B5 | 계단 제안 | OSM_E_60819380_fa291dd1d2 | 368.2m | 643.4m | +275.2m |
| GEC-BB519916545ADC77 | DEM 경사 진단 | OSM_E_651748871_f4f90f059a | 742.7m | no_accessible_route | 경로 없음 |
| GEC-AA1AA0D8B04665A5 | DEM 경사 진단 | OSM_E_814055254_472f20a0dd | 133.4m | 295.0m | +161.6m |
| GEC-FBBAF132F25B1E46 | DEM 경사 진단 | OSM_E_82908648_bc495b4b83 | 288.1m | no_accessible_route | 경로 없음 |
| GEC-FEF1A7A50FC72885 | 계단 제안 | OSM_E_82908648_bc495b4b83 | 288.1m | no_accessible_route | 경로 없음 |
| GEC-342EFF0B3899D4EC | DEM 경사 진단 | OSM_E_878652488-878652489-878652491-878652492-878652539_585a2d0492 | no_accessible_route | no_accessible_route | 경로 없음 |
| GEC-45362D521C02CB4A | DEM 경사 진단 | OSM_E_927242296_81ea59492a | 114.0m | 314.4m | +200.4m |
| GEC-2A42B3C84090E7F6 | 계단 제안 | OSM_E_998463214-998463215-998463216_f14383982b | 70.4m | no_accessible_route | 경로 없음 |

`no_accessible_route` 결과가 다수이므로, 특히 자동 반영하면 접근 가능한 구역을 잘못 단절할 위험이 큽니다. DEM 행은 승인 대상조차 아니며 더 정밀한 고도자료 또는 현장 측정의 우선순위를 정하는 데만 사용합니다.

## 근거로만 유지한 객체

- 보도/보행공간: geometry 의미 근거만 기록
- 횡단보도: 위치/교차 근거만 기록
- 정밀도로지도 연석: 연석 존재 근거만 기록하고 높이는 생성하지 않음
- 육교/입체횡단: 구조물 근거만 기록하고 계단 또는 통과 불가로 단정하지 않음

## 정사영상 QA 참조

25cm 정사영상의 임시 도엽 affine을 이용해 후보별 `sheet_id`, `pixel_row`, `pixel_col` 참조를 만들었습니다. 전 후보가 적어도 한 도엽에 연결됐지만 독립 기준점 RMSE는 `null`입니다. 따라서 이미지는 사람의 시각 QA 위치 찾기에만 쓰고 geometry 자동 보정이나 Graph 반영에는 쓰지 않습니다.

## 산출물

- `data/processed/evaluation/graph_enrichment/candidate_bundle.json`
- `data/processed/evaluation/graph_enrichment/candidates.csv`
- `data/processed/evaluation/graph_enrichment/route_affecting_candidates.json`
- `data/processed/evaluation/graph_enrichment/anyang_accessibility_graph.candidate.geojson`
- `data/processed/evaluation/graph_enrichment/anyang_accessibility_graph.candidate_simulation.geojson`
- `data/processed/evaluation/graph_enrichment/route_impact_simulation.json`
- `data/processed/evaluation/graph_enrichment/metrics.json`
- `data/processed/evaluation/orthophoto/qa_evidence_manifest.json`

candidate Graph는 기본 실행 Graph가 아니며 `candidate_enrichments` 주석만 추가합니다. 승인 절차가 생기기 전에는 이 파일을 `NAVI_GRAPH_PATH`로 사용하지 않습니다.

`anyang_accessibility_graph.candidate_simulation.geojson`은 계단 5건과 DEM 진단 12건을 별도 사본에 적용한 영향 시험 전용 파일입니다. 이 파일 역시 실행 Graph나 검증 데이터가 아닙니다.
