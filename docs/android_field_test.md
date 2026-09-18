# NaVi Android 현장 검증 절차

## 검증 범위 구분

현재 기본 경로 Graph는 안양역–안양1동 데모 구역이다. M1 실제 AR 정합 시험에서는 이 Graph를 사용하지 않고, 전북대학교 전주캠퍼스 정문 주변의 25m 로컬 전용 OSM Graph를 명시적으로 선택한다. 앱은 선택한 Graph 범위 밖 현재 위치를 출발지로 적용하지 않고 이 한계를 알린다.

따라서 검증을 두 부분으로 나눈다.

- 기능 검증: 에뮬레이터 또는 사용자의 생활권에서 카메라/센서/제보 흐름 확인
- 데모 검증: 안양 synthetic 시나리오로 경로 차이와 후보 영향 확인
- M1 공간 정합: 전북대 정문 로컬 OSM 25m Graph로 GPS/AR 리본 정합만 확인

로드뷰는 현장 후보를 미리 확인하는 참고 자료로만 사용한다. 로드뷰 이미지에서 추정한 턱·경사·통행 가능 여부를 검증 완료 데이터로 등록하지 않는다.

## 사전 준비

1. 백엔드를 실행한다.
2. Android 앱의 서버 주소를 확인한다.
3. 에뮬레이터는 `10.0.2.2:8000`을 사용한다. USB 실기기는 ADB reverse를 우선하며 Wi-Fi 디버깅은 보조 수단이다.
4. SM-S911N이 `adb devices -l`에서 `device` 상태인지 확인한다.
5. 실제 이동 테스트 전에는 보호자 동행과 안전한 정지 지점을 정한다. 이동 중 조작하지 않는다.

## 자동 검증

```powershell
.\.venv\Scripts\python.exe -m pytest

cd android
$env:JAVA_HOME='C:\Program Files\Android\Android Studio\jbr'
.\gradlew.bat :app:testDebugUnitTest :app:assembleDebug :app:assembleDebugAndroidTest
```

## 시나리오 A — 일반/접근 가능 경로 비교

1. 앱을 열고 휠체어 프로필을 선택한다.
2. 기본 출발지 A와 목적지 B로 `접근 가능한 길 찾기`를 누른다.
3. 일반 최단경로 `1,081.9m`와 접근 가능 경로 `1,302.5m`를 확인한다.
4. 우회 이유에 `계단 구간 제외`가 표시되는지 확인한다.
5. 화면에 synthetic·미검증 고지가 있는지 확인한다.

## 시나리오 B — 카메라 HUD

1. `이 경로로 안내 시작` → `카메라 안내 보기`를 누른다.
2. 카메라 권한을 허용한다.
3. 영상 위에 파랑/보라 프리즘 경로 리본이 보이는지 확인한다.
4. 기기를 회전했을 때 나침반 기준 안내 방향이 바뀌는지 확인한다.
5. 영상이 파일 또는 서버에 저장되지 않는지 확인한다.

지원 기기에서는 ARCore local pose에 경로 리본을 고정한다. GPS 정확도, 경로 횡오차, heading 또는 tracking 조건이 기준을 넘으면 2D HUD로 자동 강등한다. 실제 보도 정합 정확도는 현장 3회 측정 전까지 검증된 것으로 간주하지 않는다.

## 시나리오 C — 현장 장애와 즉시 재탐색

1. 지도 또는 카메라 안내에서 `앞 구간 통과 불가`를 누른다.
2. `공사`, `높은 턱`, `계단` 등 사유를 선택한다.
3. `이 구간을 피해 다시 찾기`를 누른다.
4. 현재 세션이 즉시 우회 적용 상태가 되는지 확인한다.
5. 변경 경로가 `1,736.3m`이며 보라색으로 표시되는지 확인한다.
6. 제보 상태가 `pending`, 공용 Graph가 `아직 변경되지 않음`인지 확인한다.

확인 API:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
Invoke-RestMethod http://127.0.0.1:8000/edges/OSM_E_915477950_ab67cf4d52
Invoke-RestMethod 'http://127.0.0.1:8000/observations/candidates?status=pending'
```

세션 재탐색 뒤에도 위 Edge의 `blocked`는 `false`여야 한다. 새 수동 후보는 `source=manual_camera`, `confidence=null`, `verified=false`여야 한다.

## 시나리오 D — 공간데이터 후보 경로 영향

1. 경로 비교 화면에서 `후보 지도와 경로 영향 보기`를 누른다.
2. `영향 시험 17` 필터에서 계단 5건은 적색, DEM 경사 진단 12건은 보라색으로 표시되는지 확인한다.
3. 영향 계산 완료 후 현재 bundle 기준 `경로 단절 10 · 우회 증가 6 · 변화 없음 1`이 표시되는지 확인한다.
4. 아래 대표 결과가 표시되는지 확인한다.

| 후보 | 유형 | 기대 결과 |
|---|---|---|
| `GEC-61063192388228C2` | 계단 속성 후보 | `98.1m → 212.2m`, `+114.1m` 우회 |
| `GEC-CE1DCD49F1BE0C70` | DEM 경사 진단 | `171.3m → 361.2m`, `+189.9m` 우회 |
| `GEC-45362D521C02CB4A` | DEM 경사 진단 | `114.0m → 314.4m`, `+200.4m` 우회 |

5. 계단 후보 상세에 `계단 false → true`, 제작연도·도엽·매칭 거리 등 provenance가 표시되는지 확인한다.
6. DEM 후보 상세에 `90m DEM`, `민감도 진단 전용`, `승인 대상 아님`이 표시되고 실제 보도 경사로 단정하지 않는지 확인한다.
7. `보행공간 130`, `횡단시설 88`, `연석 12` 필터에서 각 레이어가 별도 색과 범례로 표시되는지 확인한다.
8. 근거 전용 후보를 선택해 정사영상 도엽과 pixel 위치, `RMSE 미측정`, `형상 자동 보정 불가 · Graph 반영 불가` 고지를 확인한다.
9. 영향 시험 지도에서 현재 Graph는 회색 점선, 후보 임시 적용은 보라색 경로로 구분되는지 확인한다.
10. `공유 Graph 변경 없음 · SQLite 변경 없음` 고지를 확인한다.

확인 API:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/graph-enrichment/summary
Invoke-RestMethod 'http://127.0.0.1:8000/graph-enrichment/candidates?route_affecting=true'
Invoke-RestMethod http://127.0.0.1:8000/edges/OSM_E_379904073_9581b7b371
```

마지막 Edge 응답의 `stairs`, `blocked`, `verified`는 모두 `false`여야 한다. 이 단계는 후보의 경로 민감도 확인이지 현장 사실 승인 절차가 아니다.

## 사용자 생활권으로 확장할 때

지역 독립형 M1 정합 경로는 `scripts/prepare_local_ar_route.py`로 만든다. 이 스크립트는 계단·횡단·실내·사유지·보행 금지 way를 제외하고 20~30m 구간을 만들지만, OSM 형상만 선택할 뿐 접근성을 검증하지 않는다. 현재 전북대 정문 산출물은 `data/runtime/local-field-tests/jbnu-jeonju-main-gate/`에 있고 Git에서 제외된다.

지역 독립형 Graph 빌더는 아래 입력과 경계를 명시적으로 유지한다.

- origin/destination 좌표
- OSM source, 조회 시점, 원본 hash
- `source`, `confidence=null`, `verified=false`
- `field_test_only=true`, `shared_graph_mutation_allowed=false`

실제 턱·경사·폭은 현장 측정 또는 사람 검수 전까지 `unknown`으로 유지한다.

## 시나리오 E — 전북대 정문 M1 로컬 AR 정합

전체 준비값과 기록표는 [전북대 정문 M1 로컬 현장 시험](m1_local_field_route_jbnu.md)을 기준으로 한다.

1. 현장에서 먼저 25m 구간을 눈으로 확인한다. 공사, 차량 진출입, 보행 혼잡 또는 미끄럼 위험이 있으면 시험하지 않는다.
2. 개발 PC에서 로컬 전용 backend를 실행한다.

```powershell
$localRouteDir = (Resolve-Path 'data\runtime\local-field-tests\jbnu-jeonju-main-gate').Path
$env:NAVI_GRAPH_PATH = Join-Path $localRouteDir 'route.geojson'
$env:NAVI_DB_PATH = Join-Path $localRouteDir 'navi-field-clean.db'
$env:NAVI_GRAPH_ENRICHMENT_PATH = ''
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8002
```

3. 다른 터미널에서 USB 연결과 reverse를 확인한다.

```powershell
$adbPath = 'C:\Users\User\AppData\Local\Android\Sdk\platform-tools\adb.exe'
& $adbPath devices -l
& $adbPath -s R3CWA0J3XRZ reverse tcp:8001 tcp:8002
Invoke-RestMethod http://127.0.0.1:8002/health
```

4. 앱 홈에서 `전북대학교 전주캠퍼스 정문`, `OSM 로컬 스냅샷`, `접근성 속성 미확인·미검증`, `공용 Graph에는 반영하지 않습니다`를 확인한다.
5. `접근 가능한 길 찾기`에서 일반/접근 가능 경로가 모두 `25m`, 약 `1분`인지 확인한다.
6. `이 경로로 안내 시작` → `카메라 안내 보기`로 진입한다.
7. 이동 중에는 휴대폰을 조작하지 않는다. 각 회차 시작·종료와 메모는 안전하게 멈춘 뒤 입력한다.
8. 같은 방향으로 3회 수행하며 GPS 횡오차, 리본 횡방향 오차, yaw 편차, tracking/fallback, Depth 상태를 기록한다.
9. 시험이 끝나면 backend를 `Ctrl+C`로 종료하고 기본 개발 backend를 쓸 때 reverse를 복구한다.

```powershell
& $adbPath -s R3CWA0J3XRZ reverse tcp:8001 tcp:8000
```

이 시나리오는 AR 정합만 평가한다. 3회가 성공해도 턱·폭·경사·표면 또는 휠체어 통행 가능성을 검증한 것이 아니며 공용 Graph 승인 근거가 아니다.
