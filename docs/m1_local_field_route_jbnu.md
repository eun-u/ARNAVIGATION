# M1 전북대학교 내부 로컬 AR 정합 시험

상태: 내부 경로 확정·산출물·backend 계약 검증 완료, SM-S911N 화면·현장 3회 대기

기준일: 2026-09-18

기준 기기: Samsung SM-S911N (`R3CWA0J3XRZ`)

이 절차는 `M1-ALIGN` 25m AR 정합 시험만 다룬다. 휠체어 프로필 안내 중 장애물 제보, 세션 재탐색과 도착까지의 실증은 [E2E-WC 전북대 재탐색 경로](e2e_wc_jbnu_route.md)를 따른다.

## 목적과 비목적

전북대학교 전주캠퍼스 내부 25m 보행로에서 ARCore 경로 리본의 공간 정합과 폴백을 같은 조건으로 3회 확인한다. 기존 안양 데모 Graph와 기존 정문 주변 경로는 사용하지 않는다.

이 시험은 턱·폭·경사·표면 또는 휠체어 통행 가능성을 검증하지 않는다. OSM 형상은 접근성 Ground Truth가 아니며 결과를 공용 Graph에 자동 반영하지 않는다.

## 활성 경로

| 항목 | 값 |
|---|---|
| 장소 | 전북대학교 106 학생군사교육단 남측 녹지 보행로 |
| 진행 | 서쪽 시작점 → 동쪽 종료점 |
| 시작 좌표 | `127.13143032, 35.84591590` |
| 종료 좌표 | `127.13170667, 35.84590380` |
| 원본 | OpenStreetMap via Overpass API |
| OSM way | `471373639` |
| OSM 분류 | `highway=footway` |
| 선택 길이 / 방위 | `25.0m` / `93.09°` |
| 원 보행선 / 양끝 여유 | `75.031m` / `25.015m`, `25.016m` |
| Edge ID | `LOCAL_OSM_427b2b6f53e0` |
| 접근성 상태 | `unknown`, `verified=false` |
| 사용 범위 | `field_test_only=true` |
| 공용 Graph 변경 | `shared_graph_mutation_allowed=false` |

선정 근거와 탈락 후보 비교는 [전북대 내부 PoC 경로 선정 기록](m1_jbnu_route_selection.md)에 고정했다. 정확한 원본 GraphML, route GeoJSON, hash와 생성 시각은 Git 제외 로컬 디렉터리에 있다.

```text
data/runtime/local-field-tests/jbnu-jeonju-campus-poc/
├── manifest.json
├── osm-walk.graphml
└── route.geojson
```

- 현장 중심 지도: <https://www.openstreetmap.org/?mlat=35.8459099&mlon=127.1315685#map=19/35.8459099/127.1315685>
- 전북대학교 공식 캠퍼스 지도: <https://www.jbnu.ac.kr/web/intro/campus/sub02.do>
- OSM 저작권·ODbL 고지: <https://www.openstreetmap.org/copyright>

## 생성과 회귀 검증

`--expected-osm-way-id`가 다른 way의 자동 선택을 막는다. 최신 OSM으로 재생성한 결과가 기존 좌표·방위·hash와 다르면 현장 문서를 먼저 재검토한다.

```powershell
.\.venv\Scripts\python.exe .\scripts\prepare_local_ar_route.py `
  --label '전북대학교 106 학생군사교육단 남측 보행로' `
  --slug 'jbnu-jeonju-campus-poc' `
  --center-lat 35.8459099 `
  --center-lon 127.1315685 `
  --radius-m 180 `
  --target-length-m 25 `
  --max-center-distance-m 10 `
  --expected-osm-way-id 471373639 `
  --site-reference '전북대학교 전주캠퍼스 106 학생군사교육단 남측 녹지 보행로' `
  --selection-note '캠퍼스 내부 전용 보행로, 직선 25m, 원 보행선 양끝 여유, 차량 교차 회피를 우선한 M1 PoC 구간'

.\.venv\Scripts\python.exe -m pytest backend\tests\test_prepare_local_ar_route.py
```

생성기는 계단, 횡단보도, 실내, 사유지·허가제·보행 금지 way를 제외한다. 그래도 현장 안전을 보장하지 않으므로 출발 전에 실제 보행로를 눈으로 확인한다.

## 현장 실행

### 1. backend

```powershell
$localRouteDir = (Resolve-Path 'data\runtime\local-field-tests\jbnu-jeonju-campus-poc').Path
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

1. 홈에 `전북대학교 106 학생군사교육단 남측 보행로`가 표시되어야 한다.
2. `OSM 로컬 스냅샷`, `접근성 속성 미확인·미검증`, 공용 Graph 미반영 문구가 보여야 한다.
3. 일반/접근 가능 경로가 모두 `25m`, 약 `1분`이어야 한다.
4. pending 후보는 0이어야 한다.
5. 현장 밖에서 `route_aligned=false`가 나오는 것은 정상이며 성공 결과로 세지 않는다.

### 4. 현장 안전 확인과 3회 측정

- 시작점은 106 학생군사교육단 남측 녹지 보행로의 서쪽 좌표다. 동쪽으로만 3회 진행한다.
- 공사, 차량 진출입, 혼잡, 단차, 미끄럼 또는 경로 단절이 있으면 시험을 시작하지 않는다.
- 이동 중 화면을 누르거나 수치를 적지 않는다. 회차 사이 안전한 정지 지점에서만 조작한다.
- 같은 시작점, 진행 방향, 휴대폰 높이와 자세를 유지한다.
- 초기 정합 시간, GPS 횡오차, 리본 횡방향 오차, yaw 편차, tracking/fallback, Depth와 사용자 가시 오류를 기록한다.

| 회차 | 초기 정합 시간 | GPS 횡오차 | 리본 횡오차 | yaw 편차 | tracking/fallback | Depth | 비고 |
|---|---:|---:|---:|---:|---|---|---|
| 1 | 대기 | 대기 | 대기 | 대기 | 대기 | 대기 | |
| 2 | 대기 | 대기 | 대기 | 대기 | 대기 | 대기 | |
| 3 | 대기 | 대기 | 대기 | 대기 | 대기 | 대기 | |

## 판정과 종료 조건

- 세 회차 모두 crash·process death·fatal exception이 없어야 한다.
- 정합 성공과 실패를 그대로 기록한다. 실패를 지우기 위한 추가 반복으로 표본을 바꾸지 않는다.
- GPS 또는 heading 조건 때문에 2D fallback이 발생하면 원인과 회복 시간을 함께 남긴다.
- ARCore native warning은 화면상 이상과 함께 관찰하되 warning만으로 실패를 확정하지 않는다.
- 측정이 끝나기 전까지 `field_verified=false`다.
- 결과는 AR 정합 판단에만 사용하며 접근성 승인이나 공용 Graph 변경으로 연결하지 않는다.

시험 종료 후 backend를 `Ctrl+C`로 중지하고 기본 개발 backend로 돌아갈 때 reverse를 복구한다.

```powershell
& $adbPath -s R3CWA0J3XRZ reverse tcp:8001 tcp:8000
```
