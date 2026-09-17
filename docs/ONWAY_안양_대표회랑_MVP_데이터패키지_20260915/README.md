# ON:WAY 안양 대표 회랑 MVP 데이터 패키지

기준일: 2026-09-15  
대상: 안양역–안양청년1번가–안양1동 남부 생활권(분석 중심선 약 1.38km)

## 현재 완성된 범위

- 안양1동 횡단보도 40건, 양단 접근부 80개 생성
- 접근부별 최근 카카오 로드뷰 촬영점 80/80개 확보(이미지는 판독 참고용, 패키지 미포함)
- AI 사전판독 1차 80개 및 지정 접근부 반복판독 40개 완료
- 최종 AI 사전판독: pass 25 / block 후보 5 / unknown 50
- AI 반복판독 단순일치율 95.0%, Cohen's κ 0.91
- 사람 검수 및 사람 승인: 0건. 따라서 공식 C 경로는 B와 동일
- 동일 출발·도착 10쌍 A/B/C 30개 경로행 유지; A 대비 B 5개 경로 변경, 최대 물리거리 증분 0.60%
- C* 스트레스테스트: block 후보 5개를 모두 승인했다고 가정했을 때 B 대비 9/10 경로 변경(공식 C 아님)

## 판독 규칙

- `pass`: 낮춤/무단차, 점자블록, 통행공간이 모두 영상에서 선명하게 확인됨
- `block`: 물리적 차단 또는 점자블록 부재가 선명하게 보이는 후보
- `unknown`: 착지부 가림, 카메라 직하부, 또는 추정 지오메트리와 실제 횡단부 불일치
- AI 두 번째 판독과 불일치하면 최종 AI 결과를 자동으로 `unknown`으로 내림
- AI 사전판독은 사람 2인의 독립 검수를 대체하지 않으며 `ai_human_approved`는 비워 둠

## A/B/C 정의

- A: OSM 중심선 대체망에서 거리만 최소화
- B: 공공데이터 명시 위험 엣지 차단 + 공란 횡단보도 연결 대체엣지 1.15배 가중
- C: B + 사람 승인 AI 후보 차단. 현재 승인 0건이므로 B와 동일
- C*: AI block 후보 5건을 모두 승인했다고 가정한 비공식 민감도 분석. 실제 경로안내 사용 금지

## 핵심 파일

- `ai_precheck_80.csv`: 80개 AI 1차, 지정 40개 AI 반복판독, 보수적 최종 AI 사전판독
- `approaches_80_review_queue.csv`: 사람 검수 입력란을 비워 둔 공식 검수 대장
- `route_comparison_10od_abc.csv`: 공식 A/B/C 기준선
- `route_comparison_ai_candidate_scenario.csv`: 미승인 후보 전부 승인 가정 C* 스트레스테스트
- `roadview_evidence/approaches/approach_view_metadata.csv`: 접근부별 촬영일·촬영점 거리·링크 메타데이터
- `selected_crosswalks_40.csv`, `edge_mapping_40.csv`, `onway_anyang_corridor_mvp.geojson`, `run_manifest.json`

## 다음 실행 순서

1. 팀원 1이 `ai_precheck_80.csv`와 로드뷰 링크를 참고해 80개를 사람 1차 판독한다.
2. 다른 팀원이 지정된 40개를 AI 결과와 1차 사람 결과를 보지 않고 독립 판독한다.
3. 불일치를 조정하고 AI 후보의 사람 승인 여부를 기록한다.
4. 승인 후보만 공식 C 경로에 반영한다.

## 출처·한계

- 안양시 횡단보도 공공데이터: https://www.data.go.kr/data/15042415/fileData.do
- OpenStreetMap: https://www.openstreetmap.org/copyright (© OpenStreetMap contributors, ODbL)
- 접근부 좌표는 추정값이고 OSM 도로 중심선은 실제 보도 그래프가 아니다.
- 로드뷰 이미지는 수동 판독 참고용이며 저장·학습·재배포 권리는 별도 검토가 필요하다.
