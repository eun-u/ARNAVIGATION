# NaVi 디자인 토큰

정본은 세 곳이며 이름과 값이 서로 1:1로 대응한다.

| 대상 | 파일 |
|---|---|
| 웹 | `frontend/tokens.css` |
| Android 색 | `android/app/src/main/java/kr/co/navi/mobility/ui/theme/Color.kt` |
| Android 간격·모션 | `.../ui/theme/Dimens.kt` |
| Android 타입 | `.../ui/theme/Type.kt` |

Figma Variable 이름 = CSS 변수 이름 = Kotlin 심볼 이름으로 맞춘다. 이름이 갈라지면 핸드오프에서 해석 차이가 생긴다.

## 1. 색

### brand — 누를 수 있는 것과 브랜드 순간에만

| 토큰 | 값 | CSS | Kotlin |
|---|---|---|---|
| `color.brand.primary` | `#2A5FE8` | `--color-brand-primary` | `NaviBlue` |
| `color.brand.primary.pressed` | `#1E49BE` | `--color-brand-primary-pressed` | `NaviBlueDeep` |
| `color.brand.primary.soft` | `#E9EFFD` | `--color-brand-primary-soft` | `NaviBlueSoft` |
| `color.brand.violet` | `#5A3FD6` | `--color-brand-violet` | `NaviViolet` |
| `color.brand.indigo` | `#4A47E0` | `--color-brand-indigo` | `NaviIndigo` |
| `color.brand.cyan` | `#3FC8E4` | `--color-brand-cyan` | `NaviCyan` |

Indigo와 Cyan은 스테인드글라스 면에서만 등장한다. 한 화면에 브랜드 색은 최대 2개까지만 동시에 쓴다.

### semantic — 상태 표기 전용

| 토큰 | 값 | 의미 |
|---|---|---|
| `semantic.pass` | `#0E8F72` | 통과 확인 |
| `semantic.warning` | `#A9660B` | 확인 필요 |
| `semantic.danger` | `#C4283C` | 통행 제한 |
| `semantic.unknown` | `#6B7480` | 정보 없음 |

**의미색은 누를 수 있는 요소가 되지 않는다.** 상태를 설명만 한다.
상태는 색 + 아이콘 + 글자 셋을 항상 함께 쓴다. 색만으로 구분하지 않는다.

### text — 4단계

| 토큰 | 값 | 흰 바탕 대비 | 용도 |
|---|---|---|---|
| `text.strong` | `#10131A` | 17.9 : 1 | 표제·강조 본문 |
| `text.body` | `#3D4453` | 10.2 : 1 | 본문·목록 |
| `text.muted` | `#737D8C` | 4.6 : 1 | 보조 설명·라벨. **13sp 이상에서만** |
| `text.disabled` | `#A8AFBC` | 2.6 : 1 | 비활성. 정보 전달에 쓰지 않음 |

새 회색이 필요하면 만들지 말고 위 넷 또는 유리 불투명도로 해결한다.

## 2. Glass — 수치 고정

컴포넌트는 반드시 아래 세 레벨 중 하나를 그대로 쓴다. 감으로 조정하지 않는다.

| 속성 | L1 Soft | L2 Interactive | L3 Focus |
|---|---|---|---|
| backdrop blur | 16px | 20px | 22px |
| backdrop saturate | 170% | 180% | 190% |
| surface opacity | 72% → 52% | 82% → 64% | 92% → 74% (blue tint) |
| optical edge | `.5px rgba(16,19,26,.06)` | `.5px rgba(16,19,26,.07)` | `.5px rgba(47,107,255,.32)` |
| specular (inset top) | `1px rgba(255,255,255,.95)` | `1px rgba(255,255,255,1)` | `1px rgba(255,255,255,1)` |
| edge darkening | `1px rgba(16,19,26,.05)` | `1px rgba(16,19,26,.06)` | 없음 — 브랜드 엣지가 대신 |
| diffused shadow | `0 6px 18px / .07` | `0 8px 22px / .09` | `0 8px 24px / .15 (blue)` |
| 용도 | 카드·정보 패널·상태 표시 | 버튼·세그먼트·툴바·시트 | 활성 버튼·선택된 경로·선택된 탭·AR 주요 안내 |

가장자리 색 분산(chromatic edge)은 세 레벨 공통으로 1px 링을 쓴다.
`linear-gradient(145deg, brand.primary .38 → brand.violet .20 38% → transparent 66%)`

### 유리를 쓰지 않는 곳

지도·카메라·경로선·일러스트(L0), 목록 행 배경, 아이콘 자체, 입력 필드 내부, 전체화면 오류 화면.
**한 화면에 L2 이상은 최대 3개.** 모든 카드에 Glass를 쓰면 위계가 사라진다.

### 폴백

`backdrop-filter` 미지원, 저전력, 고대비 설정일 때 불투명 대체값으로 내려간다.
흐림이 사라져도 **구조와 위계는 그대로 유지되어야 한다.**

| 레벨 | 폴백 |
|---|---|
| L1 | `#FFFFFF 92%` |
| L2 | `#FFFFFF 96%` |
| L3 | `#ECF1FF` + `1px #2A5FE8` |

`frontend/tokens.css`는 `@supports not (backdrop-filter)` 와 `@media (prefers-contrast: more)` 에서 자동 전환한다.

## 3. CTA — 6종

| 타입 | 재질 | 높이 | 용도 |
|---|---|---|---|
| Primary | Brand Glass (`#2A5FE8 → #5A3FD6`), 흰 글자 | 56dp | 화면의 주 행동. **한 화면 1개** |
| Secondary | Interactive Glass, ink 글자 | 56dp | 동등한 대안. Primary와 나란히 |
| Tertiary | 면 없음, brand ink | 48dp | 보조 진입 |
| Destructive | danger tint + danger ink | 56dp | 되돌리기 어려운 행동. 빨강으로 채우지 않는다 |
| Disabled | 평면 회색. 유리도 그림자도 없음 | 56dp | 비활성 — **이유를 옆에 적는다** |
| Loading | Primary의 채도만 낮춤. 레이아웃 불변 | 56dp | 최소 400ms 유지해 깜빡임 방지 |

Primary와 Destructive를 나란히 두지 않는다. Destructive는 앱바나 시트 하단 우측으로 분리한다.

| 상태 | 처리 |
|---|---|
| Hover | 색 불변. 하이라이트와 엣지만 증가 |
| Pressed | `scale(0.985)` · 140ms |
| Focus | `2px #2A5FE8` outline · offset 2 |

## 4. 타이포그래피

| 토큰 | 값 | Kotlin |
|---|---|---|
| `text.display` | 26 / 700 / -0.035em / 1.42 | `headlineMedium` |
| `text.title` | 18 / 700 / -0.03em | `titleLarge` |
| `text.body` | 15 / 400 / 1.6 | `bodyLarge` |
| `text.caption` | 13 / 400 / muted | `bodySmall` |
| button label | 17 / 700 | `labelLarge` |

유리 효과가 강할수록 타이포는 단순해야 한다. 재질이 시각적 개성을, 타이포는 정보 전달을 담당한다.
장식(그림자·아웃라인·그라데이션 텍스트)을 쓰지 않는다.

### 숫자 체계 — 일반 텍스트와 분리된 4단계

`22분`과 `+221m`이 같은 체계에 있으면 안 된다. 넷 모두 tabular numeral을 강제한다.

| 토큰 | 값 | Kotlin | 용도 |
|---|---|---|---|
| `metric.primary` | 40 / 700 / -0.045em | `NaviMetricPrimary` | 화면당 하나. 소요·남은 시간 |
| `metric.secondary` | 18 / 700 / -0.03em | `NaviMetricSecondary` | 거리·도착 예정·개수 |
| `metric.delta` | 14 / 700 | `NaviMetricDelta` | 비교값. 부호 필수. 증가=warning, 감소=pass |
| `metric.uncertainty` | 12 / 600 / muted | `NaviMetricUncertainty` | 오차·임계값·조건 |

단위(분·m·%·cm)는 값보다 한 단계 작게, 같은 색으로 붙인다.

> 과거 `NaviMetricTextStyle`은 monospace였다. 안내 중 글랜스 가독성이 떨어져 본문 글꼴 + tabular numeral로 바꿨고, 기존 호출부 호환을 위해 이름은 `NaviMetricSecondary`의 별칭으로 남겼다.

## 5. 간격 · 반경 · 터치

8pt 기본, 4pt 보조. 화면마다 여백을 새로 정하지 않는다.

| 토큰 | 값 |
|---|---|
| `space.1 … space.8` | 4 · 8 · 12 · 16 · 20 · 24 · 32 |
| 화면 좌우 여백 | 20px 고정 |
| 카드 안쪽 여백 | 16px |
| 목록 항목 최소 높이 | 60px |
| 최소 터치 타깃 | 48 × 48dp |
| 타깃 사이 간격 | 8px 이상 |
| 안내 중 단일 행동 | 56dp 이상 |

| 반경 | 값 | 용도 |
|---|---|---|
| `radius.sm` | 10 | 작은 칩·내부 이미지 |
| `radius.control` | 16 | 컨트롤 |
| `radius.action` | 18 | 버튼 |
| `radius.card` | 20 | 카드 |
| `radius.sheet` | 26 | 바텀시트 |
| `radius.pill` | 999 | 필터 칩 |

## 6. 아이콘

24 × 24 캔버스 / live area 20 × 20 / stroke 2px / round cap·join / fill은 selected에서만 / `currentColor`.
탭 크기는 48 × 48. 16px는 stroke 1.75, 32px는 2.25로 보정한다. **같은 굵기로 스케일하지 않는다.**
아이콘 자체에 glass·blur·그림자를 넣지 않는다. selected일 때만 뒤에 유리 컨테이너가 붙는다.

## 7. 스테인드글라스 사용 강도

감성 화면에서는 브랜드를, 판단 화면에서는 정보를 보여준다.

| 강도 | 면 불투명도 | 화면 |
|---|---|---|
| High | 15–22% | 01 스플래시 · 02 온보딩 · 13 도착 |
| Medium | 7–11% | 03 권한 · 04 이동 조건 · 05 홈 · 15 저장/기록 · 빈 상태 |
| Low | 0–4.5% | 06 검색 · 07 경로 설정 · 16 내 정보 |
| None | 0% | 08 경로 결과 · 09 추천 근거 · 10 지도 안내 · 11 AR · 12 재탐색 · 14 제보 · U-1…U-6 |

### 피해야 하는 4가지

- 모든 카드에 Glass
- 모든 버튼에 Gradient
- 모든 배경에 Stained Glass
- 모든 경로에 Chromatic effect

넷 중 하나라도 어기면 정보 위계가 무너지고 저가형 glassmorphism이 된다.

### 검사 방법

화면을 회색조로 변환했을 때 정보 위계가 그대로 읽히면 통과. 색면이 사라져 구조가 무너지면 강도를 한 단계 내린다.
두 번째 검사: blur를 0으로 놓아도 각 층이 구분되면 통과.

## 8. 정보 위계 5단계

모든 경로 관련 화면에 같은 순서를 적용한다. 화면마다 순서를 바꾸지 않는다.

| 레벨 | 내용 |
|---|---|
| L1 | 갈 수 있는가? — 통행 상태 배지 하나 |
| L2 | 얼마나 걸리는가? — Primary Metric + 거리 + 우회량 |
| L3 | 어느 부분이 위험하거나 제외됐는가? |
| L4 | 왜 이 경로인가 · 근거와 데이터 신뢰 — 별도 화면으로 분리 |
| L5 | 원시 데이터 — 출처 · 최종 검증일 · edge 개수 |

한 화면에 L1·L2는 각각 하나씩만. L4 이하가 L2보다 시각적으로 커지면 위계가 깨진 것이다.
