# NaVi 접근성 경로 안내 PoC

NaVi는 스마트폰 카메라와 접근성 경로 엔진을 결합해 휠체어·개인 이동 사용자의 길을 안내하는 모바일 우선 PoC입니다. 일반 최단경로와 접근 가능한 경로를 구분하고, 이동 중 장애물 후보가 생기면 현재 세션의 경로를 다시 계산합니다.

현재 기본 데모는 안양 대표 회랑의 고정 OSM 보행망 스냅샷을 사용합니다. OSM은 실제 공간 데이터지만 보도 전용 정밀망이 아니며, 계단·공사 차단 등 접근성 데모 속성은 기능 검증을 위한 `synthetic`, `verified=false` 데이터입니다.

## 검증 시나리오

| 상태 | 거리 | 설명 |
|---|---:|---|
| 일반 최단경로 | 1,081.9m | 거리만 기준으로 계산 |
| 접근 가능 경로 | 1,302.5m | synthetic 계단 Edge 제외 |
| 데모 Edge 공사 차단 후 | 1,736.3m | 차단 Edge 제외 후 자동 재탐색 |

데모 Edge와 출발·도착 노드는 빌드 과정에서 연결성과 우회 가능성을 확인해 자동 선정되며, `data/processed/anyang_accessibility_graph.geojson`의 `metadata.demo`에 기록됩니다.

## 구현 범위

- OSMnx로 고정 시점 보행망 수집 및 GeoJSON Accessibility Graph 빌드
- NetworkX MultiGraph + Dijkstra 일반/접근성 경로 계산
- 계단, 차단, 엘리베이터, 경사, 폭, 턱 Hard Constraint
- Kotlin + Jetpack Compose 기반 Android 전용 시민 앱
- MapLibre 지도에서 일반·접근 가능·재탐색 경로 비교
- CameraX 실시간 미리보기 위 Prismatic Wayfinding 2D HUD
- 시작 → 경로 계획 → 비교 → 판단 근거 → 지도/카메라 안내 → 현장 제보 → 재탐색 흐름
- 현장 제보 → 현재 세션 임시 차단 → 즉시 재탐색
- 시민 제보는 `pending`, `verified=false`로 저장하고 공용 Graph에는 미반영
- SQLite Edge 현재 상태와 변경 이력 영속화
- 브라우저 탭별 24시간 route session 및 영향 세션 재계산
- ONWAY AI 후보 5건의 `pending → human review → approved/rejected` 워크플로
- 승인된 관찰만 검증 상태로 Graph에 반영

AI 후보는 Graph를 직접 수정하지 않습니다. 점자블록 부재 후보는 승인하더라도 현재 휠체어 Hard Constraint에 임의로 연결하지 않습니다.

## 백엔드 실행

Python 3.11 이상과 PowerShell 기준입니다.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev,geo]"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --reload
```

- 현장 후보 검수: `http://127.0.0.1:8000/review`
- API 문서: `http://127.0.0.1:8000/docs`

SQLite는 기본적으로 `data/runtime/navi.db`에 생성되며 Git에 포함되지 않습니다.

## Android 앱 실행

요구 환경은 Android Studio, JDK 17 이상, Android SDK 36입니다. 에뮬레이터에서는 앱의 기본 서버 주소 `http://10.0.2.2:8000`이 위 백엔드를 가리킵니다.

```powershell
Copy-Item android\local.properties.example android\local.properties
# local.properties의 sdk.dir를 설치된 Android SDK 경로로 수정

cd android
$env:JAVA_HOME='C:\Program Files\Android\Android Studio\jbr'
.\gradlew.bat :app:assembleDebug
.\gradlew.bat :app:installDebug
```

생성 APK는 `android/app/build/outputs/apk/debug/app-debug.apk`입니다. 실기기에서 백엔드에 연결하려면 `android/local.properties`의 `NAVI_BACKEND_URL`을 개발 PC의 LAN 주소로 바꾸고, 백엔드를 `--host 0.0.0.0`으로 실행해야 합니다. 운영용 HTTP 허용은 열어두지 않았으므로 실제 배포는 HTTPS 구성이 필요합니다.

Android Studio에서는 `android/` 폴더를 프로젝트로 열어 `app` 구성을 실행합니다.

## 데이터 재생성

저장소에는 재현 가능한 OSM 스냅샷과 빌드 결과가 포함됩니다. 네트워크를 다시 내려받을 때만 첫 명령이 필요합니다.

```powershell
.\.venv\Scripts\python.exe scripts\fetch_osm.py
.\.venv\Scripts\python.exe scripts\build_graph.py
```

`fetch_osm.py`의 기본 범위와 시점은 메타데이터에 기록됩니다. OSM 데이터는 OpenStreetMap contributors의 ODbL 조건을 따릅니다.

## 공간데이터 평가

로컬에 배치한 수치지형도·DEM·정사영상·정밀도로지도와 안양시 횡단보도 CSV를 현재 Graph 기준으로 일괄 검증합니다. 이 명령은 `data/raw/`와 기존 `anyang_accessibility_graph.geojson`을 읽기만 하며 Graph에 속성을 병합하지 않습니다.

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev,geo]"
.\.venv\Scripts\python.exe scripts\validate_spatial_sources.py
.\.venv\Scripts\python.exe scripts\run_spatial_evaluation.py
```

산출물:

- `data/processed/evaluation/corridor_mask.geojson`: EPSG:5179에서 계산한 30m 회랑·100m 문맥 buffer를 EPSG:4326으로 저장
- `data/processed/evaluation/metrics.json`: 원본 무결성, CRS, Graph coverage, 경고와 hold 사유
- `data/processed/evaluation/evaluation_summary.json`: 수치지형도·DEM·정사영상·정밀도로지도 교차평가와 채택 판정
- `data/processed/evaluation/review_queue.geojson`, `review_queue.csv`: 역할별 최대 30개의 결정론적 Human Review 표본
- `data/processed/evaluation/graph_enrichment/`: 기존 Routing 필드를 바꾸지 않은 Graph 반영 후보 235개와 candidate Graph 사본
- `docs/spatial_data_evaluation_report.md`: 실제 평가 수치와 다음 검수 gate
- `docs/graph_enrichment_candidate_report.md`: 경로 영향 후보와 제외 사유

종료 코드는 `0=검증 실패 없음(pass 또는 제한이 명시된 warning)`, `1=필수 데이터 검증 실패`, `2=CLI 또는 내부 실행 오류`입니다. 전체 평가는 원본 TIFF나 기존 Graph를 수정하지 않습니다. 모든 파생 산출물은 `derived=true`, `verified=false`, `graph_update_allowed=false`이며 Human Review 전에는 공유 Graph에 반영할 수 없습니다. 상세 기준은 [대표회랑 공간데이터 평가 계획](docs/spatial_data_evaluation_plan.md)을 참고하세요.

`data/processed/evaluation/`은 재배포 제한이 있는 NGII 자료의 파생 geometry를 포함할 수 있어 로컬 전용이며 Git에 저장하지 않습니다. 저장소에는 재현 스크립트와 집계 보고서만 포함합니다.

## 테스트

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Android 단위 테스트·빌드·UI 테스트 APK 컴파일:

```powershell
cd android
$env:JAVA_HOME='C:\Program Files\Android\Android Studio\jbr'
.\gradlew.bat :app:testDebugUnitTest :app:assembleDebug :app:assembleDebugAndroidTest
```

연결된 에뮬레이터/기기에서 계측 UI 테스트를 실행하려면 `.\gradlew.bat :app:connectedDebugAndroidTest`를 사용합니다. 수동 실증 순서는 [Android 현장 검증 절차](docs/android_field_test.md)에 기록했습니다.

## 클라이언트 구조

- [Android 아키텍처와 화면 흐름](docs/android_architecture.md)
- [AR·AI 모듈화 및 개발 계획](docs/ar_ai_modularization_plan.md)
- [Android 현장 검증 절차](docs/android_field_test.md)
- [Prismatic Wayfinding 디자인 시스템](docs/frontend_design_system.md)
- 기존 웹 IA·유즈케이스 문서는 초기 탐색 기록으로 `docs/frontend_ia.md`, `docs/use_cases.md`, `docs/page_structure.md`에 보존

Android 앱은 Graph 메타데이터의 `synthetic`, `verified=false` 고지를 그대로 표시합니다. 현장 제보는 현재 세션 재탐색에는 즉시 사용하지만, 승인 전까지 공용 Graph를 수정하지 않습니다.

## 주요 API

- `GET /health`
- `POST /route`
- `POST /route/compare`
- `GET /route/sessions/{session_id}`
- `POST /route/sessions/{session_id}/reroute`
- `GET /edges/{edge_id}`
- `GET /edges/{edge_id}/history`
- `PATCH /edges/{edge_id}/status`
- `GET /observations/candidates`
- `POST /observations/candidates`
- `POST /observations/candidates/{candidate_id}/review`

직접 Edge를 변경할 때 `verified=true`를 사용하려면 확인자 `actor`가 필수입니다. PoC 화면의 수동 차단 실험은 `verified=false`로 저장됩니다.

## 환경 변수

```text
NAVI_GRAPH_PATH=data/processed/anyang_accessibility_graph.geojson
NAVI_DB_PATH=data/runtime/navi.db
```

## 데이터 신뢰도와 한계

- OSM 스냅샷: 실제 공간 출처, 현장 접근성은 미검증
- ONWAY 횡단보도 매핑: 공공데이터 기반 추정 위치, `verified=false`
- AI precheck 5건: 검수 대기 후보, 사실로 취급하지 않음
- synthetic 데모 속성: 경로 차이를 재현하기 위한 실험값
- 실제 턱 높이, 경사, 폭, 엘리베이터 상태를 주장하지 않음
- CameraX 영상은 화면 미리보기에만 사용하며 저장·업로드·AI 판독하지 않음
- 현재 프리즘 경로는 카메라 위 2D HUD이며 ARCore 공간 정합이나 실제 장애물 자동 감지는 아직 연결하지 않음
- 현재 기본 Graph 범위 밖 위치는 Android 앱에서 경로 출발지로 사용하지 않으며, 다른 지역의 실제 경로 검증에는 해당 지역 Graph 빌드가 필요
- 안양 Graph와 접근성 속성은 현장 실측 완료 데이터가 아니므로 실제 안전을 보장하지 않음

전체 구조와 데이터 계약은 [architecture.md](docs/architecture.md), [data_schema.md](docs/data_schema.md), 실험 절차는 [experiment.md](docs/experiment.md)를 참고하세요.
