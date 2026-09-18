# NaVi Android PoC 아키텍처

AR과 AI를 독립 Gradle 모듈로 분리하는 목표 구조, 공통 계약과 마일스톤은 [AR·AI 모듈화 및 개발 계획](ar_ai_modularization_plan.md)을 기준으로 합니다. M0에서 Gradle 모듈 골격과 기존 카메라 HUD·heading 코드의 AR 모듈 이동을 완료했습니다.

## 목적

시민용 화면을 모바일 웹이 아닌 Android 네이티브 앱으로 제공한다. 이번 범위는 자동차 내비게이션처럼 `지도 안내 ↔ 카메라 안내`를 전환하고, 사용자가 앞 구간의 장애를 입력하면 현재 세션의 접근 가능 경로가 즉시 바뀌는 것을 증명하는 것이다.

카메라 영상은 저장하거나 서버로 전송하지 않는다. CameraX 미리보기 위의 경로 표시는 2D HUD이며 ARCore 공간 정합 또는 자동 장애물 인식으로 표현하지 않는다.

## 모듈 경계

```text
Android App
├─ Compose UI
│  ├─ 경로 설정 / 비교 / 판단 근거
│  ├─ MapLibre 지도 안내
│  ├─ 공간데이터 후보 지도 / 경로 영향 시뮬레이션
│  └─ 현장 장애 제보 / 재탐색 결과
├─ ViewModel + NaviSessionStore
├─ NaviRepository
├─ HTTP API Client
├─ core:guidance-contract
├─ feature:ar-navigation
│  └─ CameraX 카메라 HUD + heading
├─ feature:ai-perception
│  └─ 인식 계약 골격, 실제 모델 미연결
└─ feature:guidance-fusion
   └─ 공간·인식 융합 계약, 실제 융합 미연결
          │
          ▼
FastAPI
├─ Accessibility Graph
├─ Dijkstra Route Engine
├─ Route Session 임시 차단
├─ ObservationCandidate 검수 대기열
├─ Graph Enrichment read-only 후보 카탈로그
└─ SQLite 상태 / 이력
```

Android 앱의 기본 서버 주소는 에뮬레이터 호스트 별칭인 `http://10.0.2.2:8000`이다. `android/local.properties`의 `NAVI_BACKEND_URL`로 로컬 설정할 수 있으며 이 파일은 Git에 포함하지 않는다.

## 화면 흐름

```text
경로 설정
  → 일반/접근 가능 경로 비교
       → 공간데이터 후보 지도
       → 후보 Edge 전·후 경로 시뮬레이션
  → 판단 근거
  → 지도 안내
       ↔ 카메라 HUD
  → 앞 구간 통과 불가 입력
  → 현재 route session 임시 차단
  → 접근 가능 경로 재계산
  → 변경 경로 안내
```

하단 탭은 사용하지 않는다. 이동 중 주 작업을 한 화면에 하나씩 두고, `카메라 안내`와 `통과 불가`를 큰 고정 버튼으로 제공한다.

## 상태 변경 경계

현장 제보에는 서로 다른 두 동작이 있다.

1. `POST /route/sessions/{session_id}/reroute`는 현재 세션에만 Edge를 임시 차단하고 즉시 재탐색한다.
2. `POST /observations/candidates`는 `source=manual_camera`, `status=pending`, `verified=false`, `confidence=null`인 후보를 만든다.

두 번째 동작이 성공해도 공용 Graph의 `blocked` 값은 바뀌지 않는다. 관리자 검수에서 승인한 뒤에만 검증 데이터로 전환할 수 있다. 앱은 부분 실패도 구분한다. 재탐색이 성공하고 후보 저장이 실패하면 새 경로는 유지하되 제보 저장 실패를 명시한다.

공간평가 후보 화면은 별도의 읽기 전용 경계다. `GET /graph-enrichment/summary`와 `GET /graph-enrichment/candidates`로 경로 민감도 후보와 근거 전용 후보를 함께 읽는다. 화면은 `영향 시험 / 보행공간 / 횡단시설 / 연석`으로 필터링하며 지도에는 선택 레이어의 전체 후보를 표시한다. 시뮬레이션이 허용된 17건만 각 Edge geometry의 양 끝점을 `POST /graph-enrichment/simulate`에 병렬 전달한다. 한 후보의 실패가 다른 후보 계산을 중단시키지 않으며 실패 건만 1회 자동 재시도한다. 완료 결과는 `경로 단절 → 추가 우회거리 → 경로 구성 변경 → 변화 없음` 순으로 정렬해 선택 시 재사용한다. 응답의 `baseline`과 `simulated`만 화면에 그리며 `GraphStore`, SQLite, route session을 갱신하지 않는다. 근거 전용 230건은 서버에서 시뮬레이션을 거부한다.

후보 상세에는 `current_values`, `proposed_changes`, `mapping_status`, `mapping_quality`, `evidence[]`를 표시한다. 수치지형도 제작연도·도엽·객체코드·매칭 거리·매칭 점수는 출처 추적 정보이며, 접근성 사실이나 현장 검증 결과로 표현하지 않는다. DEM 경사 12건은 90m 셀 기반 민감도 진단이라 승인 대상이 아니며 실제 보도 종단경사로 표시하지 않는다. 모든 후보에는 2025 정사영상 도엽·pixel 시각 QA 참조가 연결되지만 독립 기준점 RMSE가 없으므로 geometry 자동 보정이나 Graph 반영에는 쓰지 않는다.

## 디자인 언어

- Navy/blue/violet을 경로와 브랜드의 주 색으로 사용한다.
- 스테인드글라스 개념은 다각 분할선, 반투명 보라색, 카메라 경로 리본에만 사용한다.
- 통과 가능은 녹색, 차단은 적색, 검수 대기는 주황색으로 의미를 고정한다.
- 본문 장식보다 거리·시간·경로 상태와 주 행동 버튼의 대비를 우선한다.
- 최소 48dp 조작 영역, 상태를 색만으로 전달하지 않는 텍스트 라벨, 시스템 안전 영역을 지킨다.

## 현재 구현 파일

- `android/app/src/main/java/kr/co/navi/mobility/MainActivity.kt`: 앱 진입점과 MapLibre 초기화
- `ui/NaviApp.kt`: 화면 Navigation과 공유 ViewModel 수명
- `ui/screens/NaviScreens.kt`: 기본 여정 7개 시민 화면
- `ui/screens/GraphCandidateScreen.kt`: 영향 시험·보행공간·횡단시설·연석 필터, 출처·정사영상 근거, 전·후 거리 및 비변경 고지
- `ui/components/RouteMap.kt`: MapLibre 경로·후보 레이어와 오프라인 Canvas 폴백
- `feature/ar-navigation/.../ui/CameraHud.kt`: CameraX 미리보기와 프리즘 경로 HUD
- `feature/ar-navigation/.../sensors/HeadingTracker.kt`: 기존 방향 센서 fallback
- `core/guidance-contract/`: AR·AI·융합 공통 모델과 순수 경로 수학
- `feature/ai-perception/`: 이미지 좌표 인식 엔진 경계
- `feature/guidance-fusion/`: 동일 frame의 공간·인식 결과 결합 경계
- `ui/NaviViewModels.kt`: API 호출, 센서 수명, 제보/재탐색 상태
- `data/remote/NaviApiClient.kt`: FastAPI 계약
- `data/NaviSessionStore.kt`: 현재 여정의 단일 메모리 상태

## 의도적으로 제외한 범위

- ARCore 기반 실제 도로 평면 정합
- 영상 저장·업로드·스트리밍
- 온디바이스 장애물 자동 판독 모델
- 백그라운드 위치 추적과 음성 턴바이턴 안내
- 계정, 푸시, 결제, 운영용 오프라인 지도 패키지
