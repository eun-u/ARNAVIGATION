# NaVi Graph 반영 후보 결과

생성 시각: `2026-09-18T09:26:23+09:00`

## 결론

현재 자동평가만으로 공유 Graph에 확정 반영한 값은 없습니다. 대신 기존 routing 필드를 유지한 candidate Graph 사본과 Edge별 반영 제안을 생성했습니다.

- 전체 후보: 235개 / 192개 Edge
- 경로 조건 변경 가능 후보: 5개
- 근거 전용 후보: 230개
- 후보 유형: `{"crosswalk_geometry_evidence": 86, "curb_presence_evidence": 12, "grade_separated_crossing_evidence": 2, "pedestrian_area_evidence": 130, "stairs_attribute_candidate": 5}`
- 기준 Graph 변경: `false`
- candidate Graph 경로 회귀 동일: `true`
- 5개 계단 제안 시뮬레이션에서 영향을 받은 후보 Edge OD: 5개

## 자동 제안 가능한 필드

수치지형도 계단 객체가 unique 매칭되고 기존 OSM Edge에 `stairs=true`가 없는 5개 Edge에만 `stairs=true`를 제안했습니다. 이 값은 아직 적용되지 않았으며 승인 전에는 wheelchair 경로에서 제외되지 않습니다.

### 후보 적용 시뮬레이션

대표 데모 OD의 일반 경로 1081.9m와 휠체어 경로 1302.5m는 다섯 후보를 적용해도 변하지 않았습니다. 후보 Edge 양 끝점을 각각 시험하면 다음과 같습니다.

| Edge | 적용 전 휠체어 경로 | 후보 적용 후 | 변화 |
|---|---:|---:|---:|
| OSM_E_379904073_9581b7b371 | 98.1m | 212.2m | +114.1m |
| OSM_E_380194922_e00ee2ab58 | 140.2m | 1346.0m | +1205.8m |
| OSM_E_60819380_fa291dd1d2 | 368.2m | 643.4m | +275.2m |
| OSM_E_82908648_bc495b4b83 | 288.1m | no_accessible_route | 경로 없음 |
| OSM_E_998463214-998463215-998463216_f14383982b | 70.4m | no_accessible_route | 경로 없음 |

이는 실제 계단이라는 확정 결과가 아니라, 후보가 승인될 경우 예상되는 Graph 영향입니다. 특히 두 Edge는 대체 경로가 없어 현장 확인 없이 적용하면 접근 가능한 구역을 잘못 단절할 수 있습니다.

## 근거로만 유지한 객체

- 보도/보행공간: geometry 의미 근거만 기록
- 횡단보도: 위치/교차 근거만 기록
- 정밀도로지도 연석: 연석 존재 근거만 기록하고 높이는 생성하지 않음
- 육교/입체횡단: 구조물 근거만 기록하고 계단 또는 통과 불가로 단정하지 않음

DEM 경사는 90m 해상도 gate 때문에 후보에서 제외했고, 정사영상 geometry 보정은 기준점 RMSE가 없어 제외했습니다. 공공 횡단보도 접근성의 빈 값은 계속 `unknown`입니다.

## 산출물

- `data/processed/evaluation/graph_enrichment/candidate_bundle.json`
- `data/processed/evaluation/graph_enrichment/candidates.csv`
- `data/processed/evaluation/graph_enrichment/route_affecting_candidates.json`
- `data/processed/evaluation/graph_enrichment/anyang_accessibility_graph.candidate.geojson`
- `data/processed/evaluation/graph_enrichment/anyang_accessibility_graph.candidate_simulation.geojson`
- `data/processed/evaluation/graph_enrichment/route_impact_simulation.json`
- `data/processed/evaluation/graph_enrichment/metrics.json`

candidate Graph는 기본 실행 Graph가 아니며 `candidate_enrichments` 주석만 추가합니다. 승인 절차가 생기기 전에는 이 파일을 `NAVI_GRAPH_PATH`로 사용하지 않습니다.

`anyang_accessibility_graph.candidate_simulation.geojson`은 5개 `stairs=true` 제안을 별도 사본에 적용한 영향 시험 전용 파일입니다. 이 파일 역시 실행 Graph나 검증 데이터가 아닙니다.
