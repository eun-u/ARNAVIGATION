# M1 전북대학교 전주캠퍼스 정문 로컬 AR 정합 시험

상태: 경로 준비·backend 계약·SM-S911N UI 연결 완료, 현장 3회 측정 대기
기준일: 2026-09-18
기준 기기: Samsung SM-S911N (`R3CWA0J3XRZ`)

## 목적과 비목적

이 시험은 사용자가 제시한 공개 랜드마크인 전북대학교 전주캠퍼스 정문 주변에서 ARCore 경로 리본의 공간 정합과 폴백 동작을 확인한다. 기존 안양 데모 Graph를 사용하지 않으며 안양 현장 방문도 요구하지 않는다.

이 시험만으로 보도의 턱·폭·경사·표면 또는 휠체어 통행 가능성을 검증하지 않는다. OSM 형상은 접근성 Ground Truth가 아니며 결과를 공용 Graph에 자동 반영하지 않는다.

## 준비된 경로

| 항목 | 값 |
|---|---|
| 장소 | 전북대학교 전주캠퍼스 정문 |
| 원본 | OpenStreetMap via Overpass API |
| OSM way | `1072205323` |
| OSM 분류 | `highway=footway`, `footway=sidewalk` |
| 선택 길이 | `25.0m` |
| 진행 방위 | `343.3°` |
| Edge ID | `LOCAL_OSM_726e93a77a1b` |
| 접근성 상태 | `unknown`, `verified=false` |
| 사용 범위 | `field_test_only=true` |
| 공용 Graph 변경 | `shared_graph_mutation_allowed=false` |

정확한 좌표, 원본 GraphML, route GeoJSON, hash와 생성 시각은 아래 로컬 전용 디렉터리에 있다. `data/runtime/`은 Git에서 제외된다.

```text
data/runtime/local-field-tests/jbnu-jeonju-main-gate/
├── manifest.json
├── osm-walk.graphml
└── route.geojson
```

전북대학교 공식 주소 확인: <https://www.jbnu.ac.kr/web/intro/campus/sub04.do>
OSM 저작권·ODbL 고지: <https://www.openstreetmap.org/copyright>

## 생성과 회귀 검증

필요할 때만 최신 OSM으로 다시 생성한다. 재생성하면 way, 좌표, 방위와 hash가 달라질 수 있으므로 이 문서와 manifest를 함께 비교한다.

```powershell
.\.venv\Scripts\python.exe .\scripts\prepare_local_ar_route.py `
  --label '전북대학교 전주캠퍼스 정문' `
  --slug 'jbnu-jeonju-main-gate' `
  --center-lat 35.84219415 `
  --center-lon 127.13136210 `
  --radius-m 180 `
  --target-length-m 25

.\.venv\Scripts\python.exe -m pytest backend\tests\test_prepare_local_ar_route.py
```

생성기는 계단, 횡단보도, 실내, 사유지·허가제·보행 금지 way를 제외한다. 그래도 현장 안전을 보장하지 않으므로 출발 전에 실제 보행로를 눈으로 확인한다.

## 현장 실행

### 1. backend

```powershell
$localRouteDir = (Resolve-Path 'data\runtime\local-field-tests\jbnu-jeonju-main-gate').Path
$env:NAVI_GRAPH_PATH = Join-Path $localRouteDir 'route.geojson'
$env:NAVI_DB_PATH = Join-Path $localRouteDir 'navi-field-clean.db'
$env:NAVI_GRAPH_ENRICHMENT_PATH = ''
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8002
```

정상 health 기준은 `nodes=2`, `edges=1`, `pending=0`, `source=OpenStreetMap local snapshot`, `accessibility_attributes=unknown_unverified`다.

### 2. SM-S911N 연결

앱 debug 주소는 `127.0.0.1:8001`이다. USB reverse로 로컬 backend `8002`에 연결한다.

```powershell
$adbPath = 'C:\Users\User\AppData\Local\Android\Sdk\platform-tools\adb.exe'
& $adbPath devices -l
& $adbPath -s R3CWA0J3XRZ reverse tcp:8001 tcp:8002
& $adbPath -s R3CWA0J3XRZ reverse --list
```

### 3. 앱 사전 확인

1. 홈 고지에 장소, `OSM 로컬 스냅샷`, `접근성 속성 미확인·미검증`, 공용 Graph 미반영 문구가 모두 보여야 한다.
2. 경로 비교에서 일반/접근 가능 경로가 모두 `25m`, 약 `1분`이어야 한다.
3. pending 후보는 0이어야 한다.
4. 현장 밖에서 `route_aligned=false`가 나오는 것은 정상이며 성공 결과로 세지 않는다.

### 4. 3회 측정

- 시험 전 구간의 공사, 차량 진출입, 혼잡, 노면 위험을 육안으로 확인한다.
- 이동 중 화면을 누르거나 수치를 적지 않는다. 회차 사이 안전한 정지 지점에서만 조작한다.
- 가능한 한 같은 시작점, 같은 진행 방향, 비슷한 휴대폰 높이와 자세를 유지한다.
- 각 회차에서 초기 정합 시간, GPS 횡오차, 리본 횡방향 오차, yaw 편차, tracking/fallback, Depth 상태와 사용자 가시 오류를 기록한다.

| 회차 | 초기 정합 시간 | GPS 횡오차 | 리본 횡오차 | yaw 편차 | tracking/fallback | Depth | 비고 |
|---|---:|---:|---:|---:|---|---|---|
| 1 | 대기 | 대기 | 대기 | 대기 | 대기 | 대기 | |
| 2 | 대기 | 대기 | 대기 | 대기 | 대기 | 대기 | |
| 3 | 대기 | 대기 | 대기 | 대기 | 대기 | 대기 | |

## 판정과 종료 조건

- 세 회차 모두 crash·process death·fatal exception이 없어야 한다.
- 정합 성공/실패를 각각 그대로 기록한다. 실패를 없애기 위한 추가 반복으로 표본을 바꾸지 않는다.
- GPS 또는 heading 조건 때문에 2D fallback이 발생하면 원인과 회복 시간을 함께 남긴다.
- ARCore native warning은 화면상 이상과 함께 관찰하되 warning만으로 실패를 확정하지 않는다.
- 측정이 끝나기 전까지 `field_verified=false`다.
- 3회 결과는 AR 정합 판단에만 사용하며 접근성 속성 승인이나 공용 Graph 변경으로 연결하지 않는다.

시험 종료 후 backend를 `Ctrl+C`로 중지하고 기본 개발 backend로 돌아갈 때 reverse를 복구한다.

```powershell
& $adbPath -s R3CWA0J3XRZ reverse tcp:8001 tcp:8000
```
