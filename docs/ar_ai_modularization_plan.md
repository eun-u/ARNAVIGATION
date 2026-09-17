# NaVi AR·AI 모듈화 및 개발 계획

## 문서 상태

- 결정: AR과 AI를 독립 Gradle 모듈로 개발한다.
- 현재 단계: M0 모듈 골격과 공통 계약 완료. ARCore·AI 런타임 도입은 아직 시작하지 않았다.
- 기준 구현: Android 네이티브 앱과 FastAPI 경로 서버.
- 핵심 원칙: 인식, 공간화, 통행 정책, 경로 계산, 자연어 설명을 서로 다른 책임으로 유지한다.

## 현재 기준선

현재 Android 카메라 화면은 CameraX 미리보기 위에 나침반 방위 차이로 리본을 그리는 2D HUD다. 이 구현은 `:feature:ar-navigation`으로 이동했고, 공통 계약·AI·융합 모듈 골격도 생성했다. 카메라 분석 use case, ARCore 공간 정합, 실제 온디바이스 모델은 아직 연결되어 있지 않다. 백엔드는 Edge의 접근성 Hard Constraint를 판정하고 Dijkstra로 경로를 계산하며, route session 단위 임시 차단과 `Candidate → Human Review → Approved Observation` 검수 경계를 이미 제공한다.

이번 모듈화는 현재 동작을 보존하면서 다음 기능을 독립적으로 개발하기 위한 준비다.

1. ARCore 기반 pose, depth, 공간 앵커와 경로 렌더링
2. 객체 탐지, 세그멘테이션, 추적과 접근성 관측 생성
3. 관측을 Graph Edge에 연결하고 현재 세션 경로를 결정론적으로 재계산
4. 유효한 경로 후보를 LLM이 설명하고 비교하는 선택적 보조 기능

## 목표 아키텍처

```text
Android

 :app  ─────────────────────────────────────────────────────┐
   │  화면 전환, 권한, lifecycle, 구현체 조립               │
   │                                                        │
   ├── :feature:ar-navigation                               │
   │     ARCore/CameraX, pose/depth, 경로 렌더링, HUD fallback
   │              │ SpatialFrameContext                     │
   │              ▼                                         │
   ├── :feature:ai-perception                               │
   │     객체 탐지/세그멘테이션/추적, PerceptionResult      │
   │              │                                         │
   │              ▼                                         │
   ├── :feature:guidance-fusion                             │
   │     frame 동기화, 공간화, 지속성 판정, HazardObservation
   │              │                                         │
   └── :core:guidance-contract ◄────────────────────────────┘
                  │ 검증된 직렬화 계약
                  ▼
FastAPI
  ObservationMapper → Session Policy → RouteEngine
        │                    │               │
        │ Edge 후보/오차      │ warn/penalty/ │ Hard Constraint
        │                    │ session block │ + Dijkstra
        ▼                    ▼               ▼
  pending candidate     session overlay   route alternatives
                                                │
                                                ▼
                                  선택적 LLM 설명·비교 계층
```

## Android Gradle 모듈

### `:core:guidance-contract`

Android SDK와 특정 ML/AR SDK에 의존하지 않는 Kotlin 모듈이다. 모듈 사이에 전달할 최소 모델과 인터페이스만 둔다.

포함:

- `FrameId`, monotonic timestamp
- `ImageCoordinate`, `GeoCoordinate`, `LocalPose`
- `PoseAccuracy`, `TrackingQuality`
- `SpatialFrameContext`
- `PerceptionResult`, `DetectedRegion`, `TrackId`
- `HazardObservation`, `ObservationEvidence`
- `GuidanceStep`, `RouteAlternative`
- 테스트용 `FrameSource`, `PerceptionEngine`, `ObservationSink` 포트

금지:

- ARCore, CameraX, MediaPipe, LiteRT 타입 노출
- Compose UI와 HTTP DTO
- Graph 변경 또는 재탐색 호출
- bitmap, mask, depth buffer를 장기 보관하는 도메인 모델

대용량 mask와 depth buffer는 프로세스 안에서 수명이 제한된 frame lease로 전달하고, 서버에는 파생된 측정값과 근거만 전송한다.

### `:feature:ar-navigation`

카메라와 공간 좌표계의 단일 소유자다.

책임:

- ARCore session과 카메라 lifecycle
- camera pose, geospatial pose, depth와 정확도 산출
- 경로 geometry를 로컬 AR 좌표로 변환
- 앵커, 경로 리본, 가림 처리와 debug overlay 렌더링
- ARCore 미지원, 추적 손실, 낮은 위치 정확도 시 기존 2D HUD fallback
- AI가 사용할 timestamp가 일치하는 CPU frame 공급

출력:

- `SpatialFrameContext`
- 수명이 제한된 CPU frame lease
- `TrackingQuality`와 capability 상태

금지:

- 객체 종류 또는 통행 가능 여부 판정
- AI 모델 의존성
- Graph Edge 선택과 API 재탐색 호출
- 공용 Graph 상태 변경

카메라는 이 모듈이 소유한다. AR 모드에서는 ARCore CPU frame을 AI에 공급하고, 비 AR fallback에서만 CameraX `ImageAnalysis` 구현을 사용한다. AR과 AI가 각각 카메라를 여는 구조는 허용하지 않는다.

### `:feature:ai-perception`

이미지에서 관측 가능한 의미를 추출한다. AR 좌표계와 Graph를 알지 못한다.

책임:

- MediaPipe/LiteRT 모델 로딩과 delegate 선택
- 객체 탐지, 의미론적 세그멘테이션과 temporal tracking
- 모델 입력 전처리와 화면 회전 보정
- frame별 `PerceptionResult` 생성
- 모델 버전, 추론 시간, confidence와 track ID 기록
- 녹화 영상·정지 이미지 기반 offline replay 테스트

초기 클래스 후보:

- 사람, 차량, 자전거·킥보드
- 공사 가림막, 적치물, 통행로 장애물
- road, sidewalk, terrain

턱 높이, 잔여 폭, 경사, 점자블록 유무는 범용 객체 클래스처럼 확정하지 않는다. 필요한 데이터와 검증 기준이 확보된 뒤 별도 모델 또는 기하 계산으로 추가한다.

금지:

- ARCore 앵커와 pose 직접 생성
- `edge_id` 생성 또는 선택
- 통행 가능/불가 최종 결정
- 재탐색과 공용 Graph 변경
- LLM 호출

### `:feature:guidance-fusion`

AR과 AI 사이의 유일한 결합 지점이다. 가능한 부분은 순수 Kotlin으로 구현하고 SDK adapter만 Android 계층에 둔다.

책임:

- `frame_id`와 timestamp로 pose/depth/AI 결과 동기화
- mask 또는 bounding region을 depth·pose와 결합해 위치와 크기 추정
- 여러 frame의 track을 합쳐 일시적 객체와 지속 장애물 구분
- 잔여 통행 폭, 거리, 관찰 지속시간과 불확실성 계산
- 서버 전송용 `HazardObservation` 생성

금지:

- Graph Edge 확정
- 사용자 프로필별 차단 정책
- 경로 계산
- 공용 Graph 쓰기

## 서버 경계

### `ObservationMapper`

권위 있는 최신 Graph와 현재 route session을 이용해 `HazardObservation`을 Edge 후보에 연결한다.

- 입력: 위치, 위치 오차, 진행 방향, 관측 종류, 측정값, 현재 session ID
- 우선 검색: 현재 경로의 전방 Edge
- 보조 검색: 관측 오차 반경과 교차하는 인접 Edge
- 출력: `edge_id`, mapping confidence, 대안 Edge, 매핑 실패 사유
- 낮은 confidence 또는 복수 후보는 자동 차단하지 않는다.

AI가 `edge_id`를 직접 보내지 않는 이유는 모델이 Graph revision과 도로 topology를 알아서는 안 되기 때문이다.

### `SessionPolicy`

구조화된 사실을 사용자 프로필에 따라 결정론적으로 해석한다.

가능한 action:

```text
ignore | warn | add_penalty | temporary_block | request_confirmation
```

예시:

- 움직이는 사람·차량: 기본 `warn`, 일정 시간 뒤 만료
- 고정 장애물 + 충분한 지속시간 + 높은 공간 정확도: `temporary_block`
- 잔여 폭이 프로필 임계값에 근접: `add_penalty` 또는 `request_confirmation`
- 낮은 위치·모델 confidence: `request_confirmation`

Hard Constraint는 Edge를 제거하고, soft preference는 가중 비용을 추가한다. 현재 길이 전용 Dijkstra는 다음 형태의 결정론적 비용으로 확장할 수 있다.

```text
cost = length
     + slope_penalty
     + narrowness_penalty
     + uncertainty_penalty
     + dynamic_hazard_penalty
```

모든 임계값과 가중치는 버전이 있는 profile 설정으로 관리한다. LLM이 임의 숫자를 생성해 적용하지 않는다.

### 관측 API 초안

기존 `temporary_blocked_edge_ids` API는 수동 제보 호환용으로 유지한다. 자동 관측은 별도 endpoint를 사용한다.

```text
POST /route/sessions/{session_id}/observations
```

요청 핵심 필드:

```text
observation_id, observed_at, type,
lat, lon, horizontal_accuracy_m,
distance_m, remaining_width_m,
persistence_ms, is_dynamic,
perception_confidence, model_version,
pose_source, evidence_summary
```

응답 핵심 필드:

```text
mapping_status, mapped_edge_id, mapping_confidence,
policy_action, policy_reasons,
route_affected, route_changed,
recalculated_route, candidate_id
```

같은 `observation_id`의 재전송은 멱등해야 한다. 매핑과 정책 결정 근거는 감사 가능하도록 저장한다.

## LLM 경계

LLM은 선택 기능이며 AR/AI 모듈의 선행 조건이 아니다.

허용:

- RouteEngine이 계산한 유효한 후보 경로의 비교·설명
- 자연어 선호를 허용된 profile preset 또는 제한된 가중치 범위로 변환
- 낮은 confidence 관측에 대한 사용자 확인 질문 생성
- 검수 대기 후보 요약

금지:

- 노드·Edge 경로 직접 생성
- Hard Constraint 우회
- 자유 텍스트로 Graph 또는 session 상태 변경
- 검증되지 않은 관측을 사실로 승격

LLM 출력은 schema validation을 통과해야 하며, 실패·시간 초과 시 결정론적 기본 문구와 기본 profile로 복귀한다. LLM을 끈 상태에서도 AR 안내, 경고, 재탐색은 모두 동작해야 한다.

## 의존성 규칙

```text
:app
 ├─ depends on :core:guidance-contract
 ├─ depends on :feature:ar-navigation
 ├─ depends on :feature:ai-perception
 └─ depends on :feature:guidance-fusion

:feature:ar-navigation  ──► :core:guidance-contract
:feature:ai-perception  ──► :core:guidance-contract
:feature:guidance-fusion ─► :core:guidance-contract
```

- AR과 AI 모듈은 서로 직접 의존하지 않는다.
- 구현체 조립과 lifecycle 연결은 `:app`에서 한다.
- feature 모듈의 외부 공개 표면은 interface와 immutable model로 제한한다.
- 모델 asset과 MediaPipe/LiteRT 의존성은 AI 모듈 밖으로 노출하지 않는다.
- ARCore 의존성과 renderer 구현은 AR 모듈 밖으로 노출하지 않는다.
- backend DTO는 Android 내부 계약과 분리하고 repository adapter에서 변환한다.

## 기존 파일 이동 상태

1단계에서는 동작을 바꾸지 않는 기계적 이동만 한다.

| 대상 | 목표 위치 | 상태·비고 |
|---|---|---|
| `CameraHud.kt` | `:feature:ar-navigation` | 완료. 기존 2D HUD를 fallback renderer로 유지 |
| `HeadingTracker.kt` | `:feature:ar-navigation` | 완료. 추후 AR pose fallback 입력 |
| `RouteMath.kt` | `:core:guidance-contract` | 완료. 좌표·bearing 함수와 테스트 이동 |
| `NaviScreens.kt`의 Camera 화면 | `:app` 유지 | 완료. AR feature public API만 호출 |
| `NaviViewModels.kt`의 센서 제어 | `:app` orchestration | 현재 유지. AR runtime 도입 시 controller 경계 재검토 |
| 신규 모델 런타임 | `:feature:ai-perception` | 계약 골격 완료, 실제 모델 미구현 |
| 신규 frame/관측 융합 | `:feature:guidance-fusion` | 계약과 frame 동기화 guard 완료, 실제 융합 미구현 |

`NaviSessionStore`, repository, HTTP client와 MapLibre 지도는 이번 1차 모듈 분리 범위에 포함하지 않는다. AR·AI 경계가 안정된 뒤 필요할 때 별도 data/feature 모듈화를 검토한다.

## 개발 단계

기간은 Android/백엔드 담당 1~2명이 병행하고, 신규 전용 데이터셋 학습 기간을 제외한 기술 스파이크 기준이다.

### M0. 계약과 모듈 골격 — 완료

- Gradle 모듈과 dependency graph 생성
- 공통 계약, fake 구현, contract test 작성
- 기존 Camera HUD와 heading 코드를 AR 모듈로 이동
- 앱 동작과 API 계약은 변경하지 않음

검증 결과:

- 공통 계약·융합 단위 테스트 통과
- 기존 app 단위 테스트 통과
- debug APK assemble 통과

완료 조건:

- 기존 Android 단위 테스트와 debug build 통과
- AR 모듈을 fake로 교체한 app test 가능
- AI/AR SDK 타입이 공통 계약에 노출되지 않음
- 순환 의존성 없음

### M1. AR 기술 스파이크 — 1~2주

- ARCore capability, pose, tracking state와 depth 연결
- 현재 route geometry의 전방 guidance step 생성
- 고정된 안양 실증 구간에서 로컬 경로 리본 렌더링
- 낮은 정확도와 미지원 기기에서 2D HUD fallback
- ARCore Recording/Playback 기반 반복 테스트 자료 생성

측정:

- tracking loss 횟수와 회복 시간
- 위치·yaw accuracy 분포
- 프레임 시간, 배터리·발열
- 경로 리본의 횡방향 오차

완료 조건:

- AI 없이 AR 모듈 단독 데모 가능
- 추적 품질이 낮을 때 잘못 고정된 리본 대신 fallback 전환
- 20분 연속 세션에서 crash와 camera deadlock 없음

### M2. AI 기술 스파이크 — 진행 중, 1~2주

현재 상태:

- M2-A 평가 코어 완료: codec·모델 런타임과 분리된 `OfflineReplayHarness` 구현
- 라벨+IoU 기반 전체/클래스별 TP·FP·FN, precision·recall·F1 산출
- 모델 보고 지연시간의 mean·p50·p95·max와 실패 프레임 기록
- 한 번에 하나의 frame lease만 열고 성공·실패 모두 close하는 bounded replay 보장
- 남은 M2-A 입출력: 실제 녹화 프레임/annotation manifest decoder와 JSON/CSV reporter
- 남은 M2-B: MediaPipe/LiteRT baseline 구현 및 현장 데이터 비교

- 먼저 녹화 영상으로 offline inference harness 구축
- Scene Semantics 또는 범용 detector/segmenter baseline 비교
- MediaPipe/LiteRT live stream 연결
- temporal tracking과 model telemetry 추가
- 실증 구간의 최소 라벨링·평가 세트 구성

측정:

- 클래스별 precision/recall과 특히 false negative
- p50/p95 inference latency와 처리 FPS
- 서로 다른 조도·날씨·기기에서 성능 변화
- 20분 구동 시 발열과 throttling

완료 조건:

- AR 없이 저장 영상과 fake frame으로 재현 테스트 가능
- reference device에서 UI를 막지 않는 비동기 추론
- 성능 기준 미달 frame은 backlog 대신 drop하는 bounded pipeline

### M3. 공간 융합과 Map Matching — 1~2주

- 동일 frame의 AI region, pose와 depth 결합
- 위치·크기·잔여 폭·지속시간 추정
- `HazardObservation` API와 idempotency 구현
- 서버 `ObservationMapper`와 debug review 화면 구현
- 이 단계에서는 자동 재탐색하지 않고 shadow mode로 기록

측정:

- 정답 Edge 대비 top-1/top-k 매핑 정확도
- 위치 오차에 따른 오매핑 비율
- 정적·동적 객체 분류와 track 안정성

완료 조건:

- 모든 관측에 model/pose/mapping provenance 존재
- 낮은 mapping confidence가 자동 차단으로 이어지지 않음
- 녹화 세션 replay 결과가 결정론적으로 재현됨

### M4. 룰 기반 세션 재탐색 — 1주

- `SessionPolicy` action과 만료 시간 구현
- hard block과 soft penalty 분리
- 후보 경로 비교와 no-route fallback
- 자동 관측도 `pending`, `verified=false` candidate로 병행 저장

완료 조건:

- 동일 입력과 profile은 동일 경로·근거를 반환
- 자동 관측은 현재 session 밖으로 전파되지 않음
- 공용 Graph는 사람 승인 전 변경되지 않음
- 오매핑·중복·만료·경로 없음 회귀 테스트 통과

### M5. LLM 설명·제안 — 3~5일

- RouteEngine 후보와 policy reason만 LLM 입력으로 허용
- 구조화 출력 schema와 timeout/fallback 구현
- 자연어 선호를 허용된 preset으로 변환
- LLM on/off A/B 검증

완료 조건:

- LLM 비활성 상태에서도 기능 손실 없이 재탐색 가능
- 유효하지 않은 출력은 상태를 변경하지 않고 폐기
- 거리, 제외 Edge와 경로 근거는 서버 계산값만 표시

### M6. 현장 검증 — 1~2주

- 안양 대표 회랑의 시간대·날씨·기기별 반복 주행
- 휠체어 사용자 관점의 경고 시점과 확인 UX 평가
- false reroute, missed hazard, tracking loss 기록
- 자동 차단 임계값을 shadow 결과를 근거로 조정

출시 판단은 평균 정확도 하나가 아니라 false negative, 잘못된 Edge 차단, 위치 추적 실패와 fallback 성공률을 함께 본다.

## 테스트 전략

- 공통 계약: 순수 Kotlin serialization, equality, timestamp와 단위 테스트
- AR: fake pose/depth, ARCore Recording/Playback, capability matrix
- AI: 고정 평가 영상과 golden result, 모델 버전별 회귀 비교
- Fusion: 기록된 frame/pose/depth/perception replay
- Backend: Map Matching, 정책 테이블, session overlay, idempotency 테스트
- End-to-end: 관측 → 매핑 → policy → 후보 경로 → 설명 전체 replay

실제 영상을 Git에 직접 추가하기 전 개인정보, 얼굴·차량번호 비식별화, 보존 기간과 동의 범위를 먼저 정한다.

## 주요 위험과 완화

| 위험 | 영향 | 완화 |
|---|---|---|
| ARCore/VPS 오차가 보도 폭보다 큼 | 잘못된 Edge와 리본 정렬 | accuracy gate, 전방 route Edge 우선 매핑, 2D HUD fallback |
| AR과 AI가 카메라를 경쟁 | camera deadlock·검은 화면 | AR 모듈 단일 소유, 동일 CPU frame 공유 |
| detector는 객체를 찾지만 통행 폭을 모름 | 잘못된 차단 | depth·pose 융합, 잔여 폭 측정, 낮은 confidence 확인 요청 |
| 긴 Graph Edge의 일부만 막힘 | 과도한 우회 | Edge 세분화 또는 구간 단위 dynamic overlay 도입 |
| 모델 domain shift | 날씨·야간에서 누락 | 현장 평가 세트, telemetry, class별 threshold와 shadow mode |
| 연속 AR+AI의 발열 | FPS 저하·배터리 소모 | 낮은 inference FPS, frame drop, 해상도와 delegate 조정 |
| LLM의 잘못된 판단 | 위험 경로 제안 | 후보 경로 밖 생성 금지, schema validation, 결정론적 fallback |

## 당장 실행할 작업 순서

1. M0에서 Gradle 골격과 계약을 먼저 만든다.
2. 기존 HUD를 AR 모듈로 이동한 뒤 build·UI 회귀를 끝낸다.
3. AR과 AI는 각각 fake 상대 모듈로 독립 개발한다.
4. AR 녹화 세션을 AI 평가 입력으로 재사용한다.
5. M3 shadow mode 데이터가 쌓이기 전에는 자동 재탐색을 활성화하지 않는다.
6. LLM은 M4의 결정론적 재탐색이 안정된 뒤에만 추가한다.

## 기술 참고

- [Android 앱 모듈화 가이드](https://developer.android.com/topic/modularization)
- [Android 모듈 의존성 역전 패턴](https://developer.android.com/topic/modularization/patterns)
- [ARCore 카메라 frame을 ML 입력으로 사용](https://developers.google.com/ar/develop/java/machine-learning)
- [ARCore Depth](https://developers.google.com/ar/develop/depth)
- [ARCore Scene Semantics](https://developers.google.com/ar/develop/scene-semantics)
- [MediaPipe Android Object Detector](https://developers.google.com/edge/mediapipe/solutions/vision/object_detector/android)
- [MediaPipe Android Image Segmenter](https://developers.google.com/edge/mediapipe/solutions/vision/image_segmenter/android)
