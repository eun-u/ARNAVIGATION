# NaVi 공간데이터 평가 결과

생성 시각: `2026-09-18T16:00:00+09:00`

## 결론

이번 배치는 원본 데이터와 기존 Accessibility Graph를 변경하지 않았다. 모든 후보는 `derived=true`, `verified=false`, `graph_update_allowed=false`이며, Human Review 승인 전에는 공유 Graph에 반영할 수 없다.

| 데이터 | 판정 | 현재 허용 용도 | 금지/보류 |
|---|---|---|---|
| 수치지형도 | 조건부 채택 | 보도·횡단보도·계단 등 공간 검수 후보 | 자동 Graph 편입 |
| 공개 DEM 90m | 부분 채택 | 거시 지형 맥락·승인 불가 경로 민감도 진단 | Edge 경사 hard constraint·verified 값 승격 |
| 정사영상 25cm | 부분 채택 | 시각 QA | 기준점 RMSE 전 자동 좌표 보정 |
| 정밀도로지도 | 부분 채택 | 보도·횡단보도·연석 geometry QA | 연석 높이·통과 가능성 추론 |
| 안양시 횡단보도 | 부분 채택 | 위치 교차검증 | 빈 접근성 값을 false로 간주 |

## 공통 검증

- 상태: `warning`
- 검증 대상: 7개
- pass/warning/fail/hold: 3/3/0/1
- 기준 Graph: 723 edges, SHA-256 `b6c746a47c80d516bc506473335e0177eade52d82b8b635d1cb0f8ce2d9cac78`
- 실행 후 Graph SHA-256: `b6c746a47c80d516bc506473335e0177eade52d82b8b635d1cb0f8ce2d9cac78` (변경 없음: `true`)

## 수치지형도

- 대표 회랑 평가 객체: 1351개
- 코드별 객체: `{"A0033320": 1011, "A0043325": 127, "A0063321": 5, "C0390000": 206, "C0463374": 2}`
- unique / ambiguous / unmatched: 390 / 450 / 511
- unique match rate: 28.868%
- 신규 객체 검수 후보: 309개
- 판정: 80% 자동 매핑 gate 미달이므로 Human Review 필요

## DEM

- 해상도: 90.0m
- Edge coverage: 100.0%
- 3개 미만 DEM cell을 사용하는 Edge: 596 / 723
- hard constraint 적용 가능 Edge: 0개
- 판정: 지형 맥락과 `approval_eligible=false` 경로 민감도 진단에는 사용 가능하나 보도 Edge 경사 판정에는 부적합

## 정사영상

- 대표 회랑 타일: 4개
- 복원 픽셀 크기: 0.25097~0.251553m
- Graph 길이 coverage: 100.0%
- 시각 검수 후보: 402개
- 기준점 RMSE: 미측정(`null`), 따라서 geometry correction 보류

## 정밀도로지도 및 횡단보도 교차검증

- 회랑 문맥 내 HD 객체: `{"concrete_curb_line": 29, "crosswalk_polygon": 22, "sidewalk_polygon": 23}`
- 공공 횡단보도 검수점: 402개
- HD 횡단보도 대응 결과: `{"matched_near": 12, "nearby_review": 6, "outside_hd_coverage": 192, "unmatched": 192}`
- 접근성 값이 하나 이상 빈 행: 357개
- 판정: 정밀도로지도는 필요하지만 부분 coverage의 보조 QA 자료이며 OSM 대체재가 아님

## Human Review 패키지

- 표본 후보: 414개
- GeoJSON: `data/processed/evaluation/review_queue.geojson`
- CSV: `data/processed/evaluation/review_queue.csv`
- 초기 상태: 전부 `pending`

## 채택 Gate

1. 수치지형도: 역할별 30개 표본의 위치·의미 정확도를 사람이 확인한다.
2. DEM: 더 정밀한 고도원 또는 현장 측정 전에는 slope hard constraint를 활성화하지 않는다.
3. 정사영상: 독립 기준점으로 RMSE를 산출하기 전에는 Graph geometry를 이동하지 않는다.
4. 정밀도로지도/횡단보도: coverage 밖의 부재를 객체 부재로 해석하지 않는다.
5. 승인된 관측만 별도 verified observation으로 변환한 뒤 Graph 갱신 절차에 전달한다.
