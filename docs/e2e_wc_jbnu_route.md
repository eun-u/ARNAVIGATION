# E2E-WC 전북대 휠체어 가정 재탐색 실증 경로

상태: **합성 Android 폐루프 완료, 현장 사전 점검 대기**

선정일: 2026-09-18

용도: `휠체어 프로필 경로 A → 장애 구간 확인 → 세션 차단 → 경로 B → 도착` 폐루프 검증

## M1-ALIGN과의 구분

기존 25m 코스는 AR 리본의 GPS·heading·공간 정합을 반복 측정하는 `M1-ALIGN` 기준선이다. Edge가 하나뿐이므로 차단하면 경로가 사라져 재탐색 실증에는 사용할 수 없다.

`E2E-WC`는 같은 전북대 현장에 별도 8-node/8-edge 로컬 Graph를 만들고, 한 구간을 막아도 다른 보행 경로가 남도록 구성한다. 두 시험은 목적과 성공 조건을 섞지 않는다.

| 구분 | M1-ALIGN | E2E-WC |
|---|---|---|
| 목적 | AR 리본 정합 3회 | 안내·장애물·재탐색·도착 폐루프 |
| Graph | 2 nodes / 1 edge | 8 nodes / 8 edges |
| 거리 | 25.0m | A 130.7m / B 153.5m |
| 차단 결과 | 경로 없음 | B로 22.8m 우회 |
| 현장 상태 | 정합 시험 대기 | 양 경로 접근성 사전 점검 대기 |

## 선정 경로

장소는 전북대학교 전주캠퍼스 **106 학생군사교육단 남동측 녹지 보행 루프**다. 기존 25m 정합 구간과 같은 현장이라 한 번의 현장 방문에서 정합 시험과 재탐색 시험을 순서대로 수행할 수 있다.

- 시작: OSM node `12288349033`, `127.13198610, 35.84635140`
- 공통 접근 종료·분기: OSM node `4655264754`, `127.13198320, 35.84589170`
- 통제 차단 후보: node `4655264754 → 4655264758`, OSM way `471373642`, 약 `10.3m`
- 재합류·도착: OSM node `12281807442`, `127.13128260, 35.84578700`
- 지도 중심: <https://www.openstreetmap.org/?mlat=35.84591&mlon=127.13157#map=19/35.84591/127.13157>

### 경로 A — 초기 안내

```text
12288349033
  → 4655264754
  → 4655264758
  → 9999717649
  → 12281807447
  → 12281807442
```

- 길이: `130.699m`
- 공통 접근: `51.171m`
- 지정 차단 Edge: `LOCAL_OSM_0c2997b56763`

### 경로 B — 세션 우회

```text
12288349033
  → 4655264754
  → 4655264749
  → 4668356700
  → 12281807442
```

- 길이: `153.542m`
- 증가 거리: `22.843m`, 약 `17.5%`
- A와 같은 51.171m 접근로를 지난 뒤 분기하고 같은 목적지에서 재합류한다.
- B에는 기존 `M1-ALIGN`이 사용하는 OSM way `471373639`가 포함된다.

경로 형상에 사용한 OSM way는 `471373639`, `471373642`, `1175116968`, `471373646`이다. 선택된 A·B Edge 자체에는 계단·횡단·실내·사유지·보행 금지 태그가 없다. 다만 A의 일부 노드에는 별도의 횡단 연결로가 접속하고 주변 차량 동선도 있으므로, 이는 현장 안전이나 휠체어 통행 가능성의 증거가 아니다.

## 선택 근거와 제외 후보

1. 지정 Edge를 제외해도 목적지까지 실제 두 번째 경로가 남는다.
2. 장애 지점 전 약 51m를 두 경로가 공유해 “AR 안내 중 장애물 발견” 순서를 재현할 수 있다.
3. 분기 직후의 짧은 Edge를 차단하므로 사용자는 막힌 구간에 진입하기 전에 정지하고 다른 가지로 전환할 수 있다.
4. 기존 25m 정합 코스와 같은 장소여서 추가 이동과 장비 재설정을 줄인다.
5. OSM 경로 drift는 예상 node path와 way ID가 하나라도 달라지면 생성 실패로 처리한다.

| 비교 후보 | 형상상 장점 | 제외 이유 |
|---|---|---|
| 공과대학 1호관 보행 루프 | A 약 91m, B 약 115m | 현재 정합 장소에서 이동해야 하고 목적지가 건물 경계에 닿아 출입구 접근성 확인 변수가 추가됨 |
| 건지광장·북문 방향 장거리 루프 | 120~170m로 시연성이 좋음 | 버스·서비스 도로와 가깝거나 대체 경로가 계단·횡단 연결점에 접하는 후보가 존재함 |
| 기존 25m 단일 Edge | 직선 정합 반복에 적합 | 차단 시 대체 경로가 없어 재탐색을 증명할 수 없음 |

## 생성과 재현

산출물은 Git 제외 경로에 둔다.

```text
data/runtime/local-field-tests/jbnu-jeonju-e2e-wheelchair/
├── manifest.json
├── osm-walk.graphml
└── route.geojson
```

재생성 명령:

```powershell
.\.venv\Scripts\python.exe .\scripts\prepare_local_reroute_route.py `
  --label "전북대학교 106 학생군사교육단 남동측 녹지 우회 루프" `
  --slug "jbnu-jeonju-e2e-wheelchair" `
  --center-lat 35.8459099 `
  --center-lon 127.1315685 `
  --radius-m 180 `
  --origin-node 12288349033 `
  --destination-node 12281807442 `
  --block-from-node 4655264754 `
  --block-to-node 4655264758 `
  --expected-primary-path "12288349033,4655264754,4655264758,9999717649,12281807447,12281807442" `
  --expected-alternate-path "12288349033,4655264754,4655264749,4668356700,12281807442" `
  --expected-way-id 471373639 `
  --expected-way-id 471373642 `
  --expected-way-id 1175116968 `
  --expected-way-id 471373646 `
  --source-graphml ".\data\runtime\local-field-tests\jbnu-jeonju-campus-poc\osm-walk.graphml"
```

현재 실제 산출물 계약:

- Graph: `8 nodes / 8 edges`
- pending observation: `0`
- 휠체어 프로필 초기 경로: `130.7m`
- 지정 Edge 세션 차단 후: `153.5m`
- `route_affected=true`, `route_changed=true`
- 세션 재탐색 후에도 원본 Edge `blocked=false`
- 모든 접근성 속성: `unknown`, `verified=false`
- 사용 범위: `field_test_only=true`, `shared_graph_mutation_allowed=false`

## 현장 실행 단계

### 0. 사람 사전 점검

A와 B를 먼저 보행 점검하고 폭·경사·턱·계단·표면·공사·차량 진출입·혼잡을 기록한다. 둘 중 하나라도 휠체어 통과가 불확실하면 실증 경로로 승인하지 않고 새 후보를 고른다. OSM 태그만으로 `wheelchair_accessible=true`를 만들지 않는다.

### 1. AI 없는 결정론적 폐루프

1. 휠체어 프로필로 경로 A를 생성한다.
2. AR 안내로 공통 접근로를 따라 분기점까지 이동한다.
3. 실제 통행을 방해하는 물체를 설치하지 않고, 지정 Edge를 통제 시나리오로 수동 제보한다.
4. 해당 Edge만 현재 세션에서 차단하고 경로 B를 계산한다.
5. AR 리본이 B로 바뀐 것을 확인하고 목적지까지 이동한다.
6. 목적지 반경 안에서 도착을 확인하고 세션 결과를 저장한다.

### 2. AI shadow 비교

같은 지정 Edge에서 AI가 장애물을 제안하는지 수동 기준과 비교한다. AI 결과는 경로를 바꾸지 않으며 `pending`, `verified=false`로만 저장한다.

### 3. 사용자 확인 후 재탐색

AI 제안과 위치 정합이 기준을 만족하면 사용자 확인을 거쳐 같은 session-local 차단 API를 호출한다. 공용 Graph 자동 변경은 계속 금지한다.

## Android 구현 상태와 남은 소프트웨어 차이

- 구현 완료: ARCore 3D 리본과 별도로 2D fallback도 정확도 `30m` 이하의 현재 위치에서 가장 가까운 forward segment 방위를 사용한다. 분기 꼭짓점에서는 다음 선분을 우선하며 경로 A/B 방향 변경을 단위 테스트했다.
- 구현 완료: 경로 끝점 `10m` 이내, 위치 정확도 `15m` 이하, 서로 다른 관측 `3회`와 최소 `2초`를 요구하는 도착 gate를 추가했다. 수동 `종료`로 도착 화면에 들어가는 연결은 제거했다.
- 구현 완료: 현재 활성 frontend 안내 화면도 실제 위치·방위·active route를 사용한다. 카메라 화면은 정적 corridor가 아니라 `CameraHud`의 ARCore 3D 리본과 2D fallback을 렌더링하고, 수동 종료는 도착 성공 대신 세션 중단으로 처리한다.
- 검증 완료: 실제 작업공간에서 guidance-contract `13 tests / 0 failures`, app `12 tests / 0 failures`, debug APK 빌드 성공.
- 2026-09-18 1차 공유 에뮬레이터 시도는 전용 backend `8 nodes / 8 edges`와 A `130.7m`까지만 확인해 실패·미완료로 남겼다.
- 2차 단독 에뮬레이터 완료 세션 `9393bae7-34bb-4058-9022-efcd0b70a735`에서 A `130.7m` → 지정 Edge session-local 차단 → B `153.5m` → 정확도 `30m` 도착 거부 → 정확도 `5m` 관측 3회·2초 → 자동 도착을 재현했다.
- 완료 세션의 Graph revision은 전후 `0`, 원본 Edge는 `blocked=false`, `verified=false`다. 후보 `MOB_3C690B2E8C7D`도 `pending`, `verified=false`로 유지됐다.
- ARCore/Play Store가 없는 에뮬레이터의 설치 화면 호출 crash를 availability 선확인과 2D 강등으로 수정했다. 재시험에서 `2D 대체 안내`가 보였고 fatal exception과 CameraX 재시도 로그가 없었다.
- 합성 증거는 Git 제외 경로 `data/runtime/local-field-tests/jbnu-jeonju-e2e-wheelchair/evidence/20260918-1822/`에 있다. `result.json`은 `verified=false`, `field_verified=false`로 고정했다.
- 현재 제보 화면은 Graph metadata의 고정 `block_edge`를 사용한다. 이 통제 코스에는 적합하지만 일반 현장에서는 M3 map matching으로 현재 앞 Edge를 선택해야 한다.
- 현재 frontend 결과·재탐색·도착 화면 일부의 안양/정적 데모 문구는 backend 세션 수치와 다르므로 화면 작업 완료 뒤 별도 시각 회귀가 필요하다.
- A·B의 실제 휠체어 통행 가능성, 안전 정지점, GPS/AR 정합은 아직 현장 검증되지 않았다.

## 성공 조건

- 사전 점검에서 A와 B 모두 휠체어 통행 가능으로 사람이 확인됨
- A 안내 중 지정 Edge 제보 전까지 AR 경로 진행이 유지됨
- 제보 후 공용 Graph 변경 없이 B로 전환됨
- 2D fallback과 3D 리본 모두 현재 진행 segment를 안내함
- 목적지 도착 gate가 성립하고 경로 A/B, 차단 Edge, 소요 시간, tracking/fallback 로그가 한 세션으로 남음
- 실패도 그대로 기록하며 추가 반복으로 결과를 덮어쓰지 않음

공식 랜드마크 대조에는 [전북대학교 캠퍼스 지도](https://www.jbnu.ac.kr/web/intro/campus/sub02.do)를 사용한다. OSM 형상은 [way 471373639](https://www.openstreetmap.org/way/471373639), [way 471373642](https://www.openstreetmap.org/way/471373642), [way 1175116968](https://www.openstreetmap.org/way/1175116968), [way 471373646](https://www.openstreetmap.org/way/471373646)을 사용한다.
