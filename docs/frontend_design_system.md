# NaVi 프론트 디자인 시스템

> 이 문서는 개요다. 수치와 토큰 이름의 정본은 [design_tokens.md](design_tokens.md),
> 잠금 원칙은 저장소 루트의 [design.md](../design.md)다.

## 시각 철학: Liquid Glass × Stained Glass

NaVi의 스테인드글라스는 장식용 유리 효과가 아니라, 조각난 도시 정보를 하나의 이동 방향으로
모으는 방식이다. 나비 날개, 지도 핀, 방향 화살표가 동일한 기하를 공유한다.

화면의 70%는 콘텐츠(L0)가 지배한다. 지도와 카메라 위에 Liquid Glass UI가 얹히고,
브랜드 색은 나비 심볼·주요 CTA·선택 상태·경로 하이라이트에만 나타난다.

정상 이동은 이어지는 투명 조각, 확인 필요는 Amber, 통행 제한은 Red로 표현하되
**색 단독으로 구분하지 않는다.** 아이콘과 상태명을 항상 함께 쓴다.

텍스트는 짧고 행동 중심으로 쓴다. 가장 큰 글자는 브랜드 문장이 아니라
지금 해야 할 행동과 예상 이동 시간이다. 지도와 카메라가 항상 가장 큰 작업 표면이다.

## 토큰 요약

| 역할 | 값 |
|---|---|
| Canvas | `#F4F6FA` |
| Surface | `#FFFFFF` |
| Ink / Body / Muted | `#10131A` / `#3D4453` / `#737D8C` |
| Brand primary → violet | `#2A5FE8` → `#5A3FD6` |
| Pass / Warning / Block / Unknown | `#0E8F72` / `#A9660B` / `#C4283C` / `#6B7480` |

- 본문은 시스템 한글 글꼴을 사용해 네트워크 폰트 교체를 방지한다
- 데이터 숫자는 tabular numeral을 쓰고, 일반 텍스트와 분리된 4단계 체계를 따른다
- 기본 간격은 4px 단위, 화면 좌우 여백은 20px
- 조작 대상은 최소 48×48dp
- 카드 안쪽 요소의 radius는 부모보다 작게 유지한다

## 컴포넌트

| 이름 | 설명 | Variant 축 |
|---|---|---|
| `BrandMark` | 나비 날개 + Map Pin + 방향 축 | — |
| `Button` | 주 행동 | Type(4) × State(5) × Material(2) |
| `Card` | 정보 묶음 | Type(4) × State(3) × Material(2) |
| `Chip` | 필터·조건 | Type(3) × State(3) |
| `Banner` | 고지·오류 | Type(4) × State(2) |
| `BottomSheet` | 지도 화면의 주 작업면 | Type(4) × Stage(3) |
| `RouteBadge` | 통행 상태 | Type(4) × State(2) |
| `TurnBanner` | 안내 배너 | Type(2) × State(4) |
| `MetricBlock` | 수치 표기 | Type(4) × State(2) |
| `TabBar` | 하단 목적지 4개 | State(3) |

상세 축과 코드 매핑은 [design_tokens.md](design_tokens.md)와
`docs/wireframes/final/f-D1-Design-System.html`에 있다.

## 모션과 접근성

- 화면 계층 진입은 220ms 이내의 opacity/translate 전환만 사용한다
- 재탐색은 4단계 시퀀스를 따른다 — [interaction_spec.md](interaction_spec.md)
- `prefers-reduced-motion`에서는 모든 반복 애니메이션을 중지한다
- 포커스는 2px Blue outline으로 표시한다
- 상태는 색상 외에 아이콘과 텍스트를 반드시 포함한다
- 흐림과 투명도가 사라져도 구조가 유지되어야 한다 — [accessibility_validation.md](accessibility_validation.md)
