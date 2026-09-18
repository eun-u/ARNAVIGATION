# Design — NaVi

NaVi의 모든 화면이 공유하는 잠금 디자인 시스템이다.
개별 화면에서 새 테마를 만들지 않고, 이 문서와 `frontend/tokens.css`의 토큰을 확장해 사용한다.

수치와 토큰 이름은 [디자인 토큰 명세](docs/design_tokens.md)가 정본이다.
화면 단위 판단 근거는 [최종 와이어프레임](docs/wireframes/final/README.md)에 있다.

## Visual philosophy — Liquid Glass × Stained Glass

NaVi의 인터페이스는 단순한 반투명 UI가 아니라, 빛이 통과하고 굴절되고 색이 겹쳐지며
사용자의 조작에 반응하는 광학적 인터페이스를 지향한다.

- **Optical Depth** — 여러 투명 레이어가 겹쳐진 공간감
- **Materiality** — 실제 유리와 같은 재질감. 핵심은 "흐림"이 아니라 "재질"이다
- **Chromatic Refraction** — 블루·바이올렛이 빛에 의해 분산되는 표현
- **Fluid Interaction** — 컨트롤이 유연하게 반응하는 움직임

유리는 장식이 아니라 **인터랙션을 나타내는 재질**이고,
스테인드글라스는 장식이 아니라 **브랜드와 의미를 나타내는 빛의 언어**다.

> Clear when functional. Chromatic when meaningful. Glass when interactive.

## 3계층 구조

| 층 | 내용 | 비중 |
|---|---|---|
| L0 Content | 지도 · 카메라 · 경로 · 데이터 — 가장 선명하게, 유리를 씌우지 않는다 | 70% |
| Liquid Glass UI | 네비게이션 · 버튼 · 툴바 · 플로팅 패널 · 시트 | 20% |
| Stained Glass Accent | 나비 심볼 · 경로 하이라이트 · 온보딩 · 선택 상태 · AR 인디케이터 | 10% |

스테인드글라스는 희소하게 등장해야 더 강하다.
모든 것을 스테인드글라스로 만들면 정보 위계가 무너지고 저가형 glassmorphism이 된다.

## Glass Hierarchy

유리는 한 종류만 쓰지 않는다. 조작에 가까워질수록 엣지와 광택이 또렷해진다.

- **L1 Soft Glass** — 카드, 정보 패널, 상태 표시
- **L2 Interactive Glass** — 버튼, 세그먼트, 툴바, FAB, 바텀시트
- **L3 Focus Glass** — 활성 버튼, 선택된 경로, 선택된 탭, AR 주요 안내

수치(blur · opacity · edge · specular · shadow)는 [design_tokens.md](docs/design_tokens.md) 2절에 고정되어 있다.
**한 화면에 L2 이상은 최대 3개.**

## Theme

- Canvas: `#F4F6FA` — 앱 화면의 기본 바탕
- Ink: `#10131A` / Body `#3D4453` / Muted `#737D8C`
- Brand: cobalt `#2A5FE8` → violet `#5A3FD6`. Indigo·Cyan은 스테인드글라스 면에서만
- Semantic glass: pass `#0E8F72`, warning `#A9660B`, danger `#C4283C`, unknown `#6B7480`

**누를 수 있는 것은 brand 하나뿐이다.** 의미색은 상태를 설명만 하고 버튼이 되지 않는다.

## Typography

- 본문·UI: Pretendard → 시스템 한글 글꼴 폴백. 네트워크 폰트 교체를 방지한다
- 표제 26 / 700 / `-0.035em`, 본문 15 / 400 / 1.6, 보조 13 / 400
- 유리 효과가 강할수록 타이포는 단순해야 한다. 재질이 개성을, 타이포는 정보 전달을 담당한다
- 숫자는 **일반 텍스트와 분리된 4단계**를 쓴다 — Primary Metric / Secondary Metric / Delta / Uncertainty.
  `22분`과 `+221m`이 같은 체계에 있으면 안 된다. 모두 tabular numeral

## Spacing

8pt 기본, 4pt 보조. 화면 좌우 여백 20px 고정, 목록 항목 최소 높이 60px,
최소 터치 타깃 48×48dp, 안내 중 단일 행동은 56dp 이상.

## Shapes

버튼 18 · 컨트롤 16 · 카드 20 · 시트 26 · 필터 칩만 pill.
담는 것과 누르는 것의 문법을 섞지 않는다.

## Motion

- press 140 · chip 180 · screen 220 · sheet 280 · route 380 (ms), easing `cubic-bezier(.2,.8,.3,1)`
- 눌림은 `scale(0.985)`
- 재탐색은 4단계로 나눈다: 기존 경로 fade → 차단 위치 강조 → 새 경로 draw → 거리 변화
- `prefers-reduced-motion`에서는 opacity만 120ms 이하

## CTA voice

Primary / Secondary / Tertiary / Destructive / Disabled / Loading 6종.
**한 화면에 Primary는 하나뿐이다.** Primary와 Destructive를 나란히 두지 않는다.
Disabled는 이유를 옆에 적는다 — 비활성만 두고 침묵하지 않는다.

## Per-page allowances

스테인드글라스 강도는 화면별로 고정한다.

- **High** — 스플래시, 온보딩, 도착. 사용자가 판단하지 않는 순간
- **Medium** — 홈, 이동 조건, 권한, 빈 상태
- **Low / None** — 지도, 검색, 경로 결과, 추천 근거, AR, 제보, 설정. **사용자가 판단하는 화면**

감성 화면에서는 브랜드를, 판단 화면에서는 정보를 보여준다.

## What pages MUST share

- NaVi 나비 심볼과 워드마크
- 단일 brand 행동색과 의미색 4종
- Glass hierarchy와 3계층 비중
- 하단 목적지 4개(홈 · 길찾기 · 제보 · 내 정보)와 컨트롤 상태
- 최소 48dp 터치 타깃
- 명시적인 데이터 검증 고지 — "안전한 경로"가 아니라 "설정한 조건에서 통과 가능한 경로"

## 폴백

흐림과 투명도가 사라져도 **구조와 위계는 그대로 유지되어야 한다.**
직사광선·고대비·저전력·`backdrop-filter` 미지원에서 불투명 대체값으로 내려간다.
`frontend/tokens.css`와 `NaviGlass.*Fallback`에 값이 있다.

## Exports

- `frontend/tokens.css` — 웹 정본
- `android/app/src/main/java/kr/co/navi/mobility/ui/theme/` — Color / Dimens / Type
- `docs/design_tokens.md` — Figma Variable ↔ CSS ↔ Compose 매핑
