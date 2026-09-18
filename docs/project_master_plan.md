# NaVi 프로젝트 마스터 계획과 현재 상태

마지막 갱신: 2026-09-18 15:29 KST
현재 활성 작업: M1-LOCAL — 전북대학교 전주캠퍼스 정문 25m 구간 현장 3회 측정 대기

이 문서는 NaVi 개발의 **단일 작업 기준**이다. 날짜가 붙은 체크포인트, 초기 제안서, 개별 모듈 문서와 상태가 충돌하면 이 문서의 `현재 상태`, `결정 사항`, `바로 다음 작업`을 우선한다. 세부 설계와 원시 결과는 링크된 문서에 남기되, 작업을 마칠 때마다 이 문서에 완료 근거와 다음 시작점을 반영한다.

## 작업 종료 시 갱신 규칙

각 작업을 종료하기 전에 반드시 다음을 수행한다.

1. 상태 표를 `미착수 / 진행 중 / 보류 / 완료` 중 하나로 갱신한다.
2. 실행한 테스트, 실기기 결과, 생성한 보고서의 경로를 기록한다.
3. 실패·편차·미해결 위험을 숨기지 않고 `남은 문제`에 기록한다.
4. 다음 세션이 설명 없이 시작할 수 있도록 `바로 다음 작업`을 한 개로 고정한다.
5. 다른 채팅 소유 파일과 작업 경계를 다시 확인한다.

## 고정 결정 사항

- AR과 AI는 별도 모듈로 유지한다.
- `:feature:ar-navigation`이 ARCore 카메라 세션을 단독 소유하고 timestamp가 있는 frame/pose/depth를 공급한다.
- `:feature:ai-perception`은 탐지·분할·추적 결과만 만들며 AR 렌더링, Edge 선택, Graph 변경을 하지 않는다.
- `:feature:guidance-fusion`은 동일 timestamp 결과를 결합하지만 공용 Graph를 수정하지 않는다.
- 결정론적 Rule/Cost Engine이 통과 가능성을 판정하고 RouteEngine이 경로를 계산한다.
- LLM은 계산된 후보의 설명·비교·제한된 프로필 변환만 담당한다.
- 자동 관측은 `pending`, `verified=false`, session-local 또는 shadow mode를 유지한다.
- 안양 현장 방문은 현재 계획에 없다. 안양 자료는 공모전 데모·공간자료 분석·synthetic 시나리오에만 사용한다.
- 위치 기반 AR 검증은 사용자 생활권의 작은 임시 OSM 보행망에서 수행한다. 로드뷰는 후보 사전 확인용이며 Ground Truth가 아니다.

## 전체 단계 상태

| 단계 | 상태 | 현재 근거 | 다음 조건 |
|---|---|---|---|
| M0 계약·모듈 골격 | 완료 | `guidance-contract`, `ar-navigation`, `ai-perception`, `guidance-fusion` 분리 및 빌드·계약 테스트 | 경계 변경 시 회귀 테스트 |
| M1 AR 기술 스파이크 | 진행 중 | ARCore pose/tracking, Depth, route ribbon, 2D fallback, Recording/Playback, telemetry, 20분 soak, Playback 5회, M1-OBS·M1-PERF 완료, 전북대 로컬 25m 경로 준비 | 현장 정합 3회 측정 |
| M2 AI device-free | 별도 채팅 소유 | 이 채팅에서는 AI importer/tracker/segmentation/evaluation 파일을 수정하지 않음 | 별도 채팅 결과를 계약으로 인계 |
| 공간데이터·Graph 후보 | 자동화 완료·사람 검수 대기 | 247개 후보/196개 Edge, 요청 한정 시뮬레이션 17개, 근거 전용 230개, 정사영상 참조 247/247 | 계단 후보 검수·정사영상 RMSE 확보 전 Graph 승격 금지 |
| M3 공간 융합·Map Matching | 미착수 | 공통 계약과 기존 backend 경로 엔진은 존재 | M1 frame/pose/depth와 M2 perception 출력 준비 |
| M4 세션 룰·재탐색 | 기반 존재 | backend에 deterministic constraint, Dijkstra, session temporary block 존재 | M3 observation을 shadow mode로 연결 |
| M5 LLM 설명·제안 | 미착수 | 역할과 금지 경계만 확정 | M4 결정론적 결과 안정화 |
| M6 검증 | 계획 수정 | 안양 방문 계획 폐기 | 생활권 로컬 OSM 시험과 별도 사람 검수 증거 사용 |

## M1 실험 현황

### 완료

- Samsung SM-S911N, Android 16에서 ARCore 세션과 `DepthMode.AUTOMATIC` 확인.
- ARCore MP4와 telemetry CSV 녹화, 전체 Playback, live camera 복귀 확인.
- 20분 live AR soak: 1,200.2초, crash 0, process death 0, fatal exception 0.
- soak 결과: tracking 210/225, degraded 15/225, Depth active 209/225, 관측 loss 최대 1회, 복구 866ms.
- 성능 결과: frame 평균 2.09ms/p95 6.198ms, 배터리 최고 42.3°C, thermal status 최고 2.
- 동일 dataset Playback 5회 모두 `PLAYBACK_FINISHED`; 프로세스 종료와 fatal error 없음.
- 화면 자동 꺼짐 가설은 `keepScreenOn=true`, display ON 로그를 근거로 배제.

### 실험 순서에서 누락된 항목

원래 합의한 순서는 `계측 보강 → 반복 Playback → 원인별 통제 실험`이었다. 실제로는 계측 보강 전에 Playback 5회를 먼저 실행했다. 따라서 5회 결과는 재생 안정성을 입증하지만 loss 원인을 분류하지 못한다.

현재 telemetry는 ARCore `trackingFailureReason`을 UI message로만 전달한다. CSV와 진단 로그에는 lifecycle, 화면 상태, session generation, 전환 원인이 구조화되어 있지 않으며 View 재생성 시 카운터 수명도 명확하지 않다.

## 완료 작업: M1-OBS 추적 손실 관측성 보강

완료 범위:

1. telemetry와 CSV에 다음 필드를 추가했다.
   - `tracking_failure_reason`
   - `lifecycle_state`
   - `display_interactive`
   - `session_generation`
   - `dataset_mode`
   - `transition_reason`
   - `expected_session_transition`
   - 실제 tracking loss와 예상된 session-transition loss의 분리 카운터
2. 카운터와 session generation이 View 재생성을 넘어 앱 프로세스 동안 유지되게 했다.
3. 상태 전환 로그와 CSV escaping/계약 단위 테스트를 추가했다.
4. SM-S911N에 빌드·설치하고 Playback → live 1회로 새 로그 계약을 확인했다.
5. 다음 통제 실험을 각각 1회 이상 수행했다.
   - 화면 잠금 → 해제
   - 저조도 또는 카메라 가림
   - 급격한 기기 움직임
6. 원인, lifecycle, 화면 상태, 실제/예상 loss, 복구 시간을 아래 표로 기록했다.

20분 soak와 Playback 5회는 반복하지 않는다. AR session/rendering 코드 또는 기준 기기·빌드 유형이 바뀔 때만 soak를 다시 수행한다.

### M1-OBS 완료 기록 — 2026-09-18

- 구현 완료: `tracking_failure_reason`, lifecycle, display interactive, session generation, dataset mode, transition reason, expected transition, 실제/예상 loss 분리.
- process-scoped diagnostics store로 View와 ARCore session 재생성 사이에 generation과 카운터를 유지한다.
- CSV에는 기존 열을 보존하고 구조화 진단 열을 뒤에 추가했다.
- AR 단위 테스트 9개 통과, AR lint 통과, debug APK 빌드 통과, `git diff --check` 오류 없음.
- SM-S911N에 최신 APK를 설치했다.
- Playback → live 1회 검증:
  - Playback 시작 loss: expected 1, unexpected 0, 복구 669ms.
  - live 복귀 loss: expected 2 누적, unexpected 0, 복구 1,618ms.
  - session generation `1 → 2`, fatal error 없음.
- 통제 실험 결과:

| 자극 | 관측 결과 | 실제/예상 loss | 복구 | 판정 |
|---|---|---|---|---|
| 화면 잠금 → 해제 | `interactive=false`, `PAUSED → STOPPED → STARTED → RESUMED`; 복귀 중 `INSUFFICIENT_FEATURES → EXCESSIVE_MOTION → NONE` | unexpected 0 / expected 누적 3 | 4,938ms | 정상 session 전환으로 분리 성공 |
| 카메라 완전 가림 약 8초 | 계속 `TRACKING`, Depth active | unexpected 0 / expected 변화 없음 | 손실 없음 | 이 자극에서는 손실 미발생 |
| 카메라 가림 + 느린 좌우 회전 약 15초 | 계속 `TRACKING`, Depth active | unexpected 0 / expected 변화 없음 | 손실 없음 | 관성 추적 유지 |
| 급격한 좌우·상하 움직임 약 5초 | 계속 `TRACKING`, Depth active | unexpected 0 / expected 변화 없음 | 손실 없음 | 이 자극에서는 손실 미발생 |

- 잠금 해제 뒤 별도의 앱 background/foreground 전환도 expected loss 누적 4, unexpected 0, 3,470ms 복구로 분류됐다.
- 모든 통제 실험 뒤 앱 PID 2258이 유지됐고 fatal exception은 없었다.
- 실험 직후 ARCore 네이티브 로그에 `spherical_rectifier.cc:161`과 `FEATURE_DSP_CAM_IMU_DESYNC` 경고가 반복됐지만 앱 상태는 `TRACKING`, Depth active였다. 제품 오류인지 기기/ARCore 진단 로그인지 성능 측정과 함께 분리 확인한다.

## 완료 작업: M1-PERF debug/benchmark 성능 기준선

- soak 스크립트의 CPU를 누적 `dumpsys cpuinfo`에서 `top` 순간 표본으로 교정하고 새 구조화 telemetry 계약에 맞췄다.
- release 설정을 상속하는 로컬 전용 non-debuggable `benchmark` 빌드 타입을 추가했다. production `release` 서명 정책은 변경하지 않았다.
- 동일 실내 장면의 1분 비교에서 두 빌드 모두 tracking/Depth 전 표본 정상, 실제 loss 0, fatal/process death 0이었다.
- debug → benchmark 결과:
  - CPU 평균 `99.829% → 70.829%` (29.0% 상대 감소)
  - frame 평균 `2.819ms → 1.647ms` (41.6% 상대 감소)
  - frame p95 `6.249ms → 3.179ms` (49.1% 상대 감소)
  - 평균 PSS `423,581KB → 354,851KB` (16.2% 상대 감소)
- benchmark 스레드 6표본에서 `ms_late_stage`가 평균 33.92%로 가장 높아 ARCore motion-stereo/Depth가 주 부하라는 정황을 확인했다.
- 상세 결과: `docs/m1_ar_performance_baseline_20260918.md`

## 완료 작업: M1-LOCAL 현장 경로 준비

- 사용자가 제시한 공개 랜드마크인 전북대학교 전주캠퍼스 정문을 기준으로 로컬 전용 경로를 준비했다. 이는 기존 안양 Graph를 옮긴 것이 아니며 안양 방문 계획도 아니다.
- `scripts/prepare_local_ar_route.py`가 최신 OSM 보행망을 조회하고 계단·횡단·실내·사유지·보행 금지 way를 제외한 뒤 20~30m 구간을 선택한다.
- 현재 선택 결과는 OSM way `1072205323`, `highway=footway`, `footway=sidewalk`, 길이 `25.0m`, 방위 `343.3°`다.
- 정확한 좌표와 원본 GraphML·route GeoJSON·manifest는 `data/runtime/local-field-tests/jbnu-jeonju-main-gate/`에 있으며 `.gitignore`로 제외했다.
- 접근성 값은 모두 `unknown`, `verified=false`, `field_test_only=true`, `shared_graph_mutation_allowed=false`다. OSM 형상만 사용하며 휠체어 통행 가능성을 주장하지 않는다.
- 전용 backend 계약 검증: Graph `2 nodes / 1 edge`, pending observation `0`, 일반/접근 가능 경로 모두 `25.0m`, 미검증 Edge `1`.
- SM-S911N debug APK에서 홈 → 경로 비교 → 안내 화면까지 확인했다. 화면에는 `OSM 로컬 스냅샷`, `접근성 속성 미확인·미검증`, `공용 Graph에는 반영하지 않습니다`가 표시되고 이전 안양 synthetic 문구는 나타나지 않는다.
- 회귀 검증: backend 전체 `56 passed`, Android `:app:testDebugUnitTest :app:assembleDebug` 성공, `git diff --check` 오류 없음, 세 로컬 runtime 산출물의 Git 제외 확인.
- 현재 기기는 현장에 있지 않아 AR 화면의 `route_aligned=false`가 정상이다. 실제 리본 정합 정확도는 아직 검증하지 않았다.
- 상세 실행 절차: `docs/m1_local_field_route_jbnu.md`

## 완료 작업: 공간데이터 Graph 후보와 Android 검토 화면

- 수치지형도·DEM·정사영상·정밀도로지도 평가 결과를 기존 안양 Graph에 직접 병합하지 않고 read-only 후보 bundle로 분리했다.
- 후보는 총 247개/196개 Edge다.
  - 승인 검토 가능한 계단 속성 제안 5개
  - 90m DEM 기반 `approval_eligible=false` 경사 민감도 진단 12개
  - 보행공간·횡단시설·연석 근거 전용 230개
- Android 후보 화면은 `영향 시험 / 보행공간 / 횡단시설 / 연석` 레이어를 분리하고, 시뮬레이션 가능한 17개만 요청 한정 overlay로 계산한다.
- 전 후보 247개에 정사영상 도엽·pixel QA 참조 305개를 연결했다. 독립 기준점 RMSE가 없으므로 geometry 자동 보정과 Graph 반영은 금지한다.
- DEM 후보 `GEC-CE1DCD49F1BE0C70` 실서버 검증에서 `171.3m → 361.2m`, `+189.9m` 우회를 확인했다. 호출 전후 Graph SHA-256, SQLite revision, pending observation 수는 동일했다.
- 기준 Graph는 504 Node/723 Edge이며 평가 전후 SHA-256은 `b6c746a47c80d516bc506473335e0177eade52d82b8b635d1cb0f8ce2d9cac78`로 동일하다.
- 전체 공간평가는 pass 176/warning 7/hold 1/fail 0이다. hold는 정사영상 독립 기준점 RMSE 미확보를 명시한 의도된 보류다.
- 최종 회귀 검증: backend 56개, Android app 11개, AR 모듈 9개 단위 테스트 통과. app·AR lint, debug·benchmark·androidTest APK 빌드 통과.
- 상세 결과: `docs/graph_enrichment_candidate_report.md`, `docs/spatial_data_evaluation_report.md`, `docs/android_field_test.md`

## 바로 다음 작업

### M1-LOCAL: 전북대 정문 현장 정합 3회 측정

1. 전북대학교 전주캠퍼스 정문 시험 구간에 도착한 뒤, 보행로 공사·차량·혼잡 여부를 먼저 육안으로 확인한다.
2. 로컬 전용 backend를 `route.geojson`으로 실행하고 USB reverse `tcp:8001 → tcp:8002`를 설정한다.
3. 이동 중 화면을 조작하지 않고 각 회차 사이 안전한 정지 지점에서 기록한다.
4. 같은 25m 구간을 3회 수행하며 GPS 횡오차, 리본 횡방향 오차, compass/yaw 편차, tracking/fallback, Depth 상태를 기록한다.
5. 3회 결과가 끝날 때까지 `field_verified=false`를 유지한다. 결과가 좋아도 접근성 속성이나 공용 Graph를 자동 승인하지 않는다.

## 작업 경계

현재 M1 작업에서는 다음 M2 소유 경로를 수정하지 않는다.

- `android/feature/ai-perception/**`
- `data/ai-evaluation/**`
- AI recording importer, tracker, segmentation evaluator 및 관련 보고서
- `docs/ai_offline_evaluation_plan.md`

## 근거 문서와 결과

- M1 구현·실험 기록: `docs/m1_ar_spike.md`
- M1 성능 기준선: `docs/m1_ar_performance_baseline_20260918.md`
- M1 전북대 로컬 시험 절차: `docs/m1_local_field_route_jbnu.md`
- 20분 soak 요약: `android/app/build/reports/ar-soak/20260917_235940/summary.json`
- 20분 원시 AR 로그: `android/app/build/reports/ar-soak/20260917_235940/navi-ar-logcat.txt`
- 자동 soak 스크립트: `scripts/ar_soak_test.ps1`
- AR/AI 전체 설계: `docs/ar_ai_modularization_plan.md`
- 프로젝트 체크포인트: `docs/project_checkpoint_20260918.md`
- 공간 데이터 평가: `docs/spatial_data_evaluation_report.md`
- Graph 후보와 경로 영향: `docs/graph_enrichment_candidate_report.md`
- Android 후보 화면 검증: `docs/android_field_test.md`

## 남은 문제

- non-debuggable benchmark도 CPU 평균 약 70.8%로 높고, ARCore motion-stereo/Depth 관련 스레드가 주 부하라는 정황만 확인했다. Depth on/off 인과 비교는 아직 하지 않았다.
- ARCore 네이티브 로그의 반복적인 depth rectifier 및 camera/IMU desync 경고가 사용자 가시 오류나 성능 저하로 이어지는지는 미확정이다.
- 실제 보도 정합과 접근성 정확도는 생활권 로컬 시험 및 사람 검수 전까지 미검증이다.
- 전북대 25m 경로는 앱·backend 연결까지만 검증됐다. 현장 3회 측정 전에는 AR 리본 정합 성공으로 간주하지 않는다.
- 90m DEM 경사는 실제 보도 종단경사가 아니며 승인 가능한 Graph 속성이 아니다. 더 정밀한 고도원이나 현장 측정 전에는 민감도 진단으로만 사용한다.
- 정사영상 참조는 독립 기준점 RMSE가 없으므로 시각 QA 위치 찾기에만 사용하고 geometry를 자동 이동하지 않는다.
