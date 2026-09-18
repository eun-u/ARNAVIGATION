# Screen State Matrix

화면이 **어떤 시스템 상태에서 왜 나타나는가**를 정의한다.
각 상태는 제목·설명·상태색·CTA·다음 행동·복구 방법을 모두 갖는다. 빠진 칸이 있으면 구현에서 임의로 채워진다.

## 절대 규칙

1. 앱은 사용자의 Hard Constraint를 **임의로 완화하지 않는다.** 완화는 항상 사용자가 명시적으로 고른다.
2. "경로를 찾을 수 없습니다"라는 문장은 쓰지 않는다. **무엇이 막았는지**를 말한다.
3. 모든 실패 상태에는 최소 2개 이상의 다음 행동이 있어야 한다. 막다른 화면을 만들지 않는다.

## RouteResult — 8 states

| state | 제목 | 상태색 | Primary CTA | 다음 행동 | 복구 |
|---|---|---|---|---|---|
| `loading` | 접근 가능한 경로를 계산하고 있어요 | neutral | Loading (비활성) | 스켈레톤 | 8초 초과 시 `server_error` |
| `success_verified` | 목적지까지 갈 수 있어요 | pass | 안내 시작 | 지도 안내 | — |
| `success_partial_verified` | 대부분 확인됐고 일부는 확인이 필요해요 | warning | 안내 시작 | 지도 안내 + 미검증 고지 배너 | 추천 근거에서 구간별 확인 |
| `success_unverified` | 경로는 있지만 현장 확인이 안 된 정보예요 | warning | 안내 시작 | 지도 안내 + 상시 고지 | 제보로 갱신 요청 |
| `no_accessible_route` | 현재 조건을 모두 만족하는 경로가 없어요 | danger | 이동 조건 수정하기 | **U-1** · 조건 자동 완화 금지 | 출입구 변경 / 출발지 변경 / 미확인 구간 포함 / 지도 확인 |
| `location_uncertain` | 현재 위치가 정확하지 않아요 | warning | 지도에서 위치 지정 | **U-3** · 방향 안내 일시 중단 | 실외 이동 / 수동 핀 / 재시도 |
| `offline_cached` | 저장된 경로로 안내 중이에요 | unknown | 다시 연결 | **U-4** · 재탐색 비활성 | 연결 복구 시 자동 재검증 |
| `server_error` | 경로를 불러오지 못했어요 | danger | 다시 시도 | 연결 오류 · 데모 폴백 제안 | 재시도 2회 후 데모 데이터 전환 제안 |

## Navigation — 이동 중 상태

| state | 제목 | 상태색 | Primary CTA | 다음 행동 / 복구 |
|---|---|---|---|---|
| `guiding` | N m 앞 회전 | brand | — | 정상. 턴 배너가 주 정보 |
| `off_route` | 안내 경로에서 벗어났어요 | warning | 여기서 재탐색 | **U-6** · 자동 재탐색은 설정에 따름 |
| `obstacle_reported` | 다른 길을 찾았어요 | violet | 새 경로로 계속 | 재탐색 확인 · 현재 세션만 반영 |
| `reroute_failed` | 지금 위치에서 다른 길이 없어요 | danger | 되돌아가서 다시 찾기 | **U-2** · 완화는 사용자가 직접 선택 |
| `ar_tracking_lost` | 카메라가 주변을 인식하지 못해요 | warning | 지도 안내로 계속 | **U-5** · 음성·진동·거리 계산은 유지 |
| `arrived` | 목적지에 도착했어요 | pass | 홈으로 | 도착 · 경로 피드백 수집 |

## 상태 정의 템플릿

```yaml
state:        no_accessible_route
title:        현재 조건을 모두 만족하는 경로가 없어요
body:         조건을 대신 완화하지 않았어요
tone:         danger
blocking:     [curb_height, elevator_required]
primary:      이동 조건 수정하기
secondary:    지도에서 직접 확인
tertiary:     다른 출입구 찾기
recovery:     U-1
telemetry:    route.no_result
```

## 신규 예외 화면 — 모두 기존 화면의 상태다

새 목적지가 아니므로 IA는 늘어나지 않는다.

| 코드 | 화면 | 자리 |
|---|---|---|
| U-1 | 접근 가능한 경로 없음 | 길찾기 · 경로 결과의 한 상태 |
| U-2 | 재탐색 실패 | 안내 · 재탐색 확인의 실패 분기 |
| U-3 | 위치 부정확 | 안내 · 지도 안내 위 오버레이 |
| U-4 | 오프라인 · 캐시 경로 | 안내 · 전역 오프라인 모드 |
| U-5 | AR 추적 실패 | 안내 · AR의 폴백 |
| U-6 | 경로 이탈 | 안내 · 지도 안내의 한 상태 |

와이어프레임: `docs/wireframes/final/f-U1-No-Route.html` … `f-U6-Off-Route.html`

## 구현 메모

`NavigationViewModel` / `RouteViewModel`의 UI 상태를 위 표와 같은 이름의 sealed interface로 내리면
화면 분기와 문구가 한 곳에 모인다. 아직 코드로 옮기지 않았다.
