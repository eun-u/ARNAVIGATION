# Routing Constraint Model

UI의 `턱 2cm` · `경사 8%`가 그래프 탐색에서 정확히 무엇인지 1:1로 고정한다.
여기가 흐릿하면 구현하면서 해석이 갈린다.

## UI 컨트롤 ↔ 탐색 조건

| UI 컨트롤 | type | op | value | unit | priority | Edge 속성 / 없을 때 |
|---|---|---|---|---|---|---|
| 계단 구간 피하기 (토글) | `has_stairs` | `==` | `false` | bool | **hard** | `edge.stairs` · null이면 통과 가능으로 보지 않음 |
| 엘리베이터 필요 (토글) | `elevator_required` | `==` | `true` | bool | **hard** | `edge.elevator` · 수직 이동 edge에만 적용 |
| 넘을 수 있는 턱 (슬라이더) | `curb_height` | `<=` | `2` | cm | **hard** | `edge.curb_height` · null이면 unknown 처리 |
| 견딜 수 있는 경사 (슬라이더) | `slope` | `<=` | `8` | percent | **hard** | `edge.slope_pct` · DEM 파생값, `verified=false` |
| 필요한 통행 폭 (프로필) | `width` | `>=` | `90` | cm | **hard** | `edge.width` · 전동 휠체어는 100 |
| 공사·차단 (제보로 생성) | `blocked` | `==` | `false` | bool | **hard** | `edge.status` · **현재 세션에만** 적용 |
| 점자블록 (향후) | `tactile_paving` | `==` | `true` | bool | soft | AI 후보만 존재 · **라우팅에 연결하지 않음** |
| 미확인 구간 포함 (U-1에서만) | `allow_unknown` | `==` | `true` | bool | override | unknown edge를 통과 가능으로 **가정**. 결과에 상시 고지 |

## unknown 처리 — 가장 자주 논쟁이 되는 지점

| edge 속성 값 | 기본 동작 | `allow_unknown = true` |
|---|---|---|
| `null` (측정 안 됨) | **제외** | 포함 · unknown 배지 |
| `synthetic` (데모 속성) | **제외** | 포함 · 데모 데이터 고지 |
| `derived`, `verified=false` (DEM 등) | 포함 + 확인 필요 | 동일 |
| `institutional`, `verified=false` | 포함 + 확인 필요 | 동일 |
| field `verified=true` | 포함 | 동일 |

## 프로필 기본값

| 프로필 | 턱 | 경사 | 폭 |
|---|---|---|---|
| 수동 휠체어 | 2cm | 8% | 90cm |
| 전동 휠체어 | 3cm | 6% | 100cm |
| 유아차·보행보조 | 4cm | 10% | 80cm |
| 기본 도보 | 제약 없음 | | |

사용자가 값을 바꾸면 프로필은 `custom`으로 바뀌고, 프로필 전환 시 확인을 묻는다.

## 요청 스키마

```json
POST /route
{
  "origin": [126.95, 37.40],
  "destination": [126.96, 37.39],
  "constraints": [
    {"type": "has_stairs",  "op": "==", "value": false, "priority": "hard"},
    {"type": "curb_height", "op": "<=", "value": 2, "unit": "cm", "priority": "hard"},
    {"type": "slope",       "op": "<=", "value": 8, "unit": "percent", "priority": "hard"}
  ],
  "allow_unknown": false
}
```

현재 백엔드는 프로필 이름으로 조건을 받는다(`backend/app/profiles.py`, `backend/app/constraints.py`).
위 스키마로 옮길 때는 프로필을 constraint 목록으로 펼치는 계층을 두고, 기존 엔드포인트는 그대로 유지한다.

## 구현 시 확인할 것

- UI 슬라이더 눈금과 `value` 단위가 같은가
- hard가 하나라도 위반되면 edge를 **완전히 제외**하는가 (가중치 증가가 아니라)
- 제보로 만든 `blocked`가 공용 Graph에 새지 않는가
- `allow_unknown`이 세션 종료와 함께 초기화되는가
