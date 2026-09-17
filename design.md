# Design — NaVi

NaVi의 모든 화면이 공유하는 잠금 디자인 시스템이다. 개별 화면에서 새 테마를
만들지 않고, 이 문서와 `frontend/tokens.css`의 토큰을 확장해 사용한다.

## Visual philosophy — 빛의 회랑

NaVi는 도시를 평면 지도가 아니라 서로 다른 몸과 상황이 통과하는 빛의 회랑으로
본다. 화면의 검은 구조선은 스테인드글라스의 납선이면서 동시에 경로, 구획,
판단 근거를 나타낸다. 장식은 기능을 설명할 때만 존재한다.

색은 성당 유리처럼 면 안에서 깊이를 갖지만 한 화면의 강한 색은 제한한다.
코발트는 진행, 바이올렛은 브랜드 기억, 청록은 확인, 호박은 주의, 루비는 차단을
의미한다. 배경은 빛을 받는 석재와 종이 사이의 따뜻한 백색이다.

기하학은 완전한 대칭보다 교차로와 우회 경로의 비대칭을 따른다. 큰 다각형 한 개와
작은 구조선 몇 개로 초점을 만들고, 정보가 많은 앱 화면에서는 장식을 줄여 기능이
주인공이 되게 한다. 장미창의 방사형 리듬은 직접 묘사하지 않고 경로 노드와 진행
상태의 배열에만 은근히 남긴다.

## Genre

Atmospheric utility. 감성적 진입과 명확한 작업 화면을 분리한다.

## Macrostructure family

- Marketing / landing: asymmetric stained-glass threshold
- App pages: mobile workbench with persistent bottom navigation
- Evidence pages: quiet long-document with pinned primary action
- Navigation: camera-first full-bleed stage

## Theme

- Paper: warm mineral white
- Ink: leaded navy
- Accent: cathedral cobalt with restrained violet
- Semantic glass: peacock teal, amber, ruby
- Surface: translucent paper, never dark frosted-glass cards

## Typography

- Display: `MaruBuri`, `Noto Serif KR`, Georgia, serif; weight 700; roman only
- Body: `Pretendard`, `SUIT`, system sans; weight 400–800
- Data: system monospace only for distances, times, and counts
- Display tracking: `-0.045em`
- Display scale anchor: `clamp(2.35rem, 11vw, 4.75rem)`

## Spacing

4-point named scale in `frontend/tokens.css`. Pages use named tokens rather than
inventing local spacing values.

## Motion

- One threshold reveal on landing; peer-screen changes use opacity only
- Interaction motion: transform and opacity, 180–420ms
- Reduced motion: opacity-only, at most 120ms

## Microinteractions stance

- Silent persistence for settings
- Visible pressed/focus/disabled states on every control
- Status feedback is concise and does not move persistent chrome

## CTA voice

- Primary: cobalt field with a clipped lower-right facet; never pill-shaped
- Secondary: paper surface with a leaded 1px boundary
- Text action: underlined or arrow-linked, no decorative container

## Per-page allowances

- Landing may use the supplied concept board and large geometric glass.
- App pages use geometry only as orientation or state communication.
- Settings and evidence pages are typography- and rule-led.

## What pages MUST share

- NaVi butterfly/pin mark and wordmark
- Leaded navy structural lines
- Cobalt primary action and semantic status colors
- Bottom navigation geometry and control states
- Minimum 44px touch targets and explicit data-verification language

## Exports

The canonical implementation is `frontend/tokens.css`, which exposes both the
portable Hallmark token names and compatibility aliases used by the existing app.

