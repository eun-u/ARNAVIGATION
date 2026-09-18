# NaVi PoC 아키텍처

ARCore 공간 안내와 온디바이스 인식을 도입하기 위한 차기 모듈 경계와 단계별 계획은 [AR·AI 모듈화 및 개발 계획](ar_ai_modularization_plan.md)에 정의합니다. 현재 문서는 구현되어 있는 PoC 기준선입니다.

## 실행 흐름

```text
Android CameraX + GPS/나침반 센서
              ↓
 Compose 지도/카메라 안내 + 현장 입력
              ↓
고정 OSM 보행망 + ONWAY 추정 매핑
              ↓
       Accessibility MultiGraph
              ↓
    Hard Constraint 필터 + Dijkstra
              ↓
 일반 경로 / 접근 가능 경로 / 근거
              ↓
 SQLite Edge 상태·이력 + 24h Route Session 임시 차단
              ↓
 현재 세션 접근 가능 경로 즉시 재계산
              ↓
 MapLibre 지도 + Prismatic Camera HUD
```

기본 그래프는 `data/processed/anyang_accessibility_graph.geojson`이며 동일 노드 쌍의 OSM Edge를 보존하기 위해 `networkx.MultiGraph`로 로드합니다. 거리 비용이 같은 경우 `edge_id` 순으로 결정해 결과를 재현 가능하게 합니다.

## 검수 경계

```text
AI Candidate(pending)
  → Human Review
  → approved / rejected / needs_more_evidence
  → Approved Observation
  → SQLite history + Graph overlay
  → Route recalculation
```

후보 생성만으로 Graph를 갱신하는 경로는 없습니다. 승인된 공사 차단 후보는 검증 차단으로 반영할 수 있지만, 점자블록 부재는 휠체어 통행 불가와 동치가 아니므로 현재 Hard Constraint를 자동 변경하지 않습니다.

## 런타임 구성

- `GraphStore`: GeoJSON 로드, Edge ID 인덱스, 동시성 잠금, SQLite overlay 적용
- `RouteEngine`: 좌표 스냅, 일반/접근 경로 탐색, 근거·출처 요약
- `RouteService`: 세션 저장, 세션 임시 차단, Edge 변경, 후보 생성·검수
- `GraphEnrichmentCatalog`: 공간평가 sidecar 무결성 검증, 후보 조회, 안전한 시뮬레이션 overlay 생성
- `GraphEnrichmentService`: 현재 요청의 Graph 사본에서만 후보 적용 전·후 접근성 경로 비교
- `Database`: Python `sqlite3`, WAL, 상태/이력/검수/세션 저장
- `FastAPI`: Android용 JSON API와 관리자 검수 화면 제공
- `android/`: Compose, MapLibre, CameraX 기반 시민 앱
- `frontend/review.html`: 공유 접근성 데이터의 사람 검수 화면

기존 웹 시민 화면은 초기 프로토타입으로 보존하지만 현재 시민용 기준 구현은 Android 앱입니다. 현장 입력은 현재 route session에는 즉시 적용하고, 동시에 `pending`, `verified=false` 후보로 서버에 저장합니다. 후보 생성만으로 공용 Graph를 수정하지 않습니다.

DB는 그래프 원본을 복제하지 않고 변경 overlay만 저장합니다. 재시작 시 GeoJSON을 먼저 읽고 저장된 overlay를 적용합니다.

공간평가 후보 조회·시뮬레이션은 검수 DB 워크플로와 분리되어 있습니다. sidecar의 기준 Graph SHA-256이 현재 파일과 일치해야 하며, `POST /graph-enrichment/simulate`는 저장된 후보의 제안값을 `RouteEngine`의 요청 한정 snapshot에만 합성합니다. 이 경로에는 GraphStore 갱신, SQLite insert/update, session 저장 코드가 없습니다. 따라서 경로 영향은 시험할 수 있지만 후보가 승인되거나 공유 Graph 사실로 승격되지는 않습니다.

Android 클라이언트의 영향 시험 순위는 각 후보 Edge의 양 끝점을 출발·도착으로 사용한 국소 민감도 비교입니다. `경로 단절`을 먼저, 같은 상태에서는 추가 거리를 큰 순서로 배치합니다. 계단 후보와 90m DEM 경사 진단 후보만 계산하며, 후자는 `approval_eligible=false`라 Graph 승인 경로가 없습니다. 이 값은 대표 여정 전체의 위험도나 후보 정확도 점수가 아닙니다.

보행공간·횡단시설·연석 후보는 별도 지도 레이어로 조회합니다. 이 객체들은 위치/존재 근거만 표현하고 Routing 값을 만들지 않습니다. 각 후보에는 2025 정사영상 도엽과 pixel 위치를 가리키는 시각 QA 참조가 붙지만, 독립 기준점 RMSE가 없으므로 자동 geometry 보정은 계속 보류합니다. Android 화면의 레이어 필터와 이미지 참조 표시는 조회 전용이며 SQLite 또는 GraphStore 쓰기 경로와 연결되지 않습니다.

## 세션

`POST /route`와 `POST /route/compare`는 UUID session을 발급합니다. Android 앱은 `POST /route/sessions/{session_id}/reroute`로 해당 세션의 `temporary_blocked_edge_ids`만 갱신합니다. 세션 만료는 마지막 계산에서 24시간이며 이 임시 차단은 다른 사용자와 공용 Graph에 전파되지 않습니다. 관리자 승인 등 공유 Edge 상태 변경은 별도 흐름으로 처리합니다.

## 의도적으로 제외한 범위

현재 카메라 화면은 CameraX 미리보기 위 2D HUD입니다. 영상은 저장·전송하지 않습니다. 실제 온디바이스 모델, 장애물 자동 판독, ARCore 공간 정합, 실내 측위, 전 시역 정밀 보도망, 인증/권한, 운영급 분산 서버는 이번 PoC 범위가 아닙니다.

실시간 개인 안내와 공유 Graph는 분리합니다. 향후 온디바이스 AI 감지는 현재 사용자의 세션 overlay에는 즉시 반영할 수 있지만, 공용 Graph에는 `Candidate → Human Review → Approved Observation` 절차 없이는 반영하지 않습니다.
