# NaVi 프로젝트 현재 체크포인트

기준일: 2026-09-18 18:54 KST

기준 브랜치: `master`

단일 작업 기준: [`project_master_plan.md`](project_master_plan.md)

이 문서는 현재 저장소를 GitHub에 동기화하기 직전의 구현·검증 상태를 요약한다. 날짜가 지난 제안이나 개별 문서와 충돌하면 `project_master_plan.md`의 상태와 `바로 다음 작업`을 우선한다.

## 한눈에 보는 현재 상태

| 영역 | 상태 | 확인된 결과 | 다음 Gate |
|---|---|---|---|
| M0 모듈화 | 완료 | AR·AI·fusion·공통 계약을 독립 Gradle 모듈로 분리 | 계약 변경 시 회귀 테스트 |
| M1 AR | 진행 중 | ARCore pose/depth, 3D route ribbon, 2D fallback, Recording/Playback, telemetry, 20분 soak 완료 | M1-VIS 정적 A/B 후 전북대 25m 현장 정합 3회 |
| E2E-WC | 합성 폐루프 완료·현장 보류 | 경로 A → 세션 차단 → 경로 B → 저정확도 거부 → 3회·2초 자동 도착 통과 | A·B 사람 사전 점검 뒤 현장 1회 |
| M1-VIS | 다음 작업 | 기하 리본 A와 sidewalk-mask 보정 shadow B의 병렬 비교 계획 확정 | 정적 frame harness와 fallback fixture 구현 |
| M2 AI device-free | 별도 작업선 | importer·tracker·평가기 계약과 에뮬레이터 실행 경로 존재 | 실제 라벨 데이터와 모델 비교 |
| 공간자료·Graph 후보 | 자동화 완료·사람 검수 대기 | 후보 247개/196개 Edge, 요청 한정 시뮬레이션 17개 | Human Review 전 Graph 승격 금지 |
| 서비스 Graph | 유지 | 기준 Graph 504 Node/723 Edge, 평가 전후 SHA-256 동일 | 검증된 observation만 별도 승격 |

## 현재 아키텍처와 안전 경계

- `:feature:ar-navigation`이 AR 모드 카메라를 소유하고 timestamp가 있는 frame/pose/depth를 공급한다.
- `:feature:ai-perception`은 탐지·분할·추적 결과만 만들고 AR 렌더링이나 Graph를 변경하지 않는다.
- `:feature:guidance-fusion`은 같은 frame의 공간 정보와 AI 결과를 결합하되 Edge를 확정하거나 공용 Graph를 수정하지 않는다.
- 통과 가능성은 결정론적 Rule/Cost Engine, 경로는 RouteEngine이 계산한다. LLM은 검증된 후보의 설명·비교만 담당한다.
- 자동 관측은 항상 `pending`, `verified=false`, session-local 또는 shadow 상태로 시작한다.
- 안양 데이터는 데모·공간자료 분석용이다. 현재 AR 위치 검증 장소는 전북대학교 전주캠퍼스 내부의 짧은 로컬 OSM 경로다.

## M1 AR 현재 결과

- Samsung SM-S911N, Android 16에서 ARCore session, tracking, `DepthMode.AUTOMATIC`, 3D route ribbon, 2D fallback을 확인했다.
- 20분 연속 실행에서 crash와 camera deadlock 없이 종료했고 최대 thermal status는 2(Moderate)였다.
- Recording/Playback 5회와 telemetry 기록, 추적 손실 사유 및 성능 관측 항목을 구현했다.
- ARCore 또는 후면 카메라가 없는 환경에서는 설치 화면을 자동 실행하지 않고 CameraX/정적 2D 안내로 안전하게 강등한다.
- 실제 보도 위 리본 정합과 접근성 정확도는 전북대 내부 25m 경로의 현장 3회 전까지 미검증이다.

## E2E-WC 합성 Android 폐루프

- 완료 세션: `9393bae7-34bb-4058-9022-efcd0b70a735`
- 경로 A `130.7m`에서 Edge `LOCAL_OSM_0c2997b56763`만 session-local로 차단해 경로 B `153.5m`로 전환했다.
- 우회 증가량은 `22.8m / 17.44%`이며 경로 B geometry는 차단 Edge를 포함하지 않는다.
- 목적지 정확도 `30m` 위치는 거부했고, 정확도 `5m`인 서로 다른 위치 3개를 2초 넘게 주입했을 때만 자동 도착했다.
- 원본 Edge는 `blocked=false`, `verified=false`, Graph revision은 전후 모두 `0`이다.
- 관측 후보 `MOB_3C690B2E8C7D`는 `pending`, `verified=false`로만 저장됐다.
- 로컬 증거는 Git 제외 경로 `data/runtime/local-field-tests/jbnu-jeonju-e2e-wheelchair/evidence/20260918-1822/`에 있으며 `field_verified=false`다.

이 결과는 선분 선택·세션 재탐색·도착 gate의 소프트웨어 흐름을 검증한 것이다. 실제 GPS/AR 정합, 휠체어 통행 가능성 또는 현장 안전을 증명하지 않는다.

## 현재 UI와 지도 상태

- Android 최종 디자인 화면과 경로·재탐색·도착 흐름을 연결했다.
- 일부 화면에는 안양 데모용 고정 문구와 수치가 남아 있다. backend session 연결 전에는 이를 전북대 실증 결과로 해석하지 않는다.
- Android 지도는 현재 MapLibre/OSM을 사용한다.
- Kakao JavaScript/REST 키는 로컬 `.env`에만 있으며 Git에 포함하지 않는다. 이 키들은 Android 네이티브 지도 키가 아니다.

## GitHub 동기화 전 회귀 검증

2026-09-18 18:54 KST 기준 결과:

- Python/backend: `60 tests`, 전부 통과
- `:core:guidance-contract`: `13 tests`, failure 0
- `:feature:ar-navigation`: `17 tests`, failure 0
- `:feature:ai-perception`: `28 tests`, failure 0
- `:app`: `20 tests`, failure 0
- `:app:assembleDebug`, `:app:assembleDebugAndroidTest` 성공
- `:app:lintDebug`, `:feature:ar-navigation:lintDebug` 성공

경고는 기존 라이브러리 deprecation과 테스트용 raster georeference 경고이며 실패는 없다.

## Git 제외 원칙

- 실제 API 키가 든 `.env`
- 촬영 원본 MP4·CSV와 ARCore dataset
- 모델 파일과 M2 실행 결과
- SQLite와 `data/runtime/` 현장·에뮬레이터 증거
- 재배포 제한이 있는 NGII 원자료 및 제한 geometry 파생물

## 바로 다음 작업

`M1-VIS-1`: 같은 정적 거리 frame에 현재 기하 리본 A와 외부 sidewalk mask 기반 shadow 리본 B를 투영하는 비교 harness를 만든다. timestamp 불일치, stale mask, 저신뢰 mask는 모두 A fallback으로 귀결되도록 golden fixture로 검증한다. B는 안내·재탐색·Graph를 변경하지 않는다.

세부 계획은 [`ar_ai_parallel_alignment_spike.md`](ar_ai_parallel_alignment_spike.md), 전북대 현장 절차는 [`m1_local_field_route_jbnu.md`](m1_local_field_route_jbnu.md), 재탐색 폐루프는 [`e2e_wc_jbnu_route.md`](e2e_wc_jbnu_route.md)를 따른다.
