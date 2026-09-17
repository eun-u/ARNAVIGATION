# NaVi 프론트 디자인 시스템

## 시각 철학: Prismatic Wayfinding

NaVi의 스테인드글라스는 장식용 유리 효과가 아니라 경로 판단이 조각난 도시 정보를 하나의 이동 방향으로 모으는 방식이다. 나비 날개, 지도 핀, 방향 화살표가 동일한 사선과 곡률을 공유한다.

화면 대부분은 White와 Deep Navy로 조용하게 유지한다. Blue와 Violet의 빛은 브랜드 진입 화면, 추천 경로, AR 방향처럼 중요한 순간에만 사용한다. 이 절제가 프리즘 효과를 신뢰할 수 있는 신호로 만든다.

정상 이동은 이어지는 투명 조각, 확인 필요는 Amber 테두리, 통행 제한은 Red 파편으로 표현한다. 상태의 형태가 달라지므로 색을 구분하기 어려운 사용자도 의미를 읽을 수 있다.

텍스트는 짧고 행동 중심으로 작성한다. 가장 큰 글자는 브랜드 문장이 아니라 지금 해야 할 행동과 예상 이동 시간에 사용한다. 지도와 카메라가 항상 가장 큰 작업 표면이다.

## 토큰

| 역할 | 값 |
|---|---|
| Ink | `#172554` |
| Ink soft | `#475569` |
| Canvas | `#F5F8FC` |
| Surface | `#FFFFFF` |
| Primary | `#2563EB` |
| Violet | `#7C3AED` |
| Pass | `#00866A` |
| Warning | `#B45309` |
| Block | `#DC2626` |
| Unknown | `#64748B` |

- 본문은 시스템 한글 글꼴을 사용해 네트워크 폰트 교체를 방지한다.
- 데이터 숫자는 tabular numeral을 사용한다.
- 기본 간격은 4px 단위, 주요 화면 여백은 20px이다.
- 조작 대상은 최소 44×44px이다.
- 카드 안쪽 요소의 radius는 부모보다 작게 유지한다.

## 컴포넌트

- `BrandMark`: 나비 날개 + Map Pin + 방향 축
- `ModePill`: API 연결 / 데모 데이터
- `LocationField`: 출발지·목적지 선택
- `ProfilePreset`: 휠체어 / 기본 이동
- `ConditionChip`: 적용 중인 Hard Constraint 설명
- `RouteSummary`: 시간·거리·추가 거리·검증 상태
- `EvidenceItem`: 이유·출처·검증 여부
- `GuidanceBanner`: 다음 행동과 거리
- `PrismRoute`: 직진·회전·재탐색의 AR 경로
- `StatusBadge`: 통과 확인 / 통행 제한 / 확인 필요 / 정보 없음 / 재확인
- `FeedbackToast`: 로딩·성공·오류 피드백, 고정 높이

## 모션과 접근성

- 화면 계층 진입은 220ms 이내의 opacity/translate 전환만 사용한다.
- AR 경로의 호흡 애니메이션은 하나의 대표 모션으로 제한한다.
- `prefers-reduced-motion`에서는 모든 반복 애니메이션을 중지한다.
- 포커스는 3px Blue outline으로 표시한다.
- 상태는 색상 외에 아이콘과 텍스트를 반드시 포함한다.
