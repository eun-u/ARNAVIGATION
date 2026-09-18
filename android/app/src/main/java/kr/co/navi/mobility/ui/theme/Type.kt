package kr.co.navi.mobility.ui.theme

import androidx.compose.material3.Typography
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.sp

/**
 * 유리 효과가 강할수록 타이포는 단순해야 한다.
 * 재질이 시각적 개성을, 타이포는 정보 전달을 담당한다.
 *
 * 네트워크 폰트 교체를 막기 위해 시스템 한글 글꼴을 쓴다.
 * Pretendard를 번들하게 되면 이 상수만 교체하면 된다.
 */
private val NaviSans = FontFamily.SansSerif

val NaviTypography = Typography(
    // 큰 수치 전용 — 남은 시간처럼 화면을 지배하는 값
    displaySmall = TextStyle(
        fontFamily = NaviSans,
        fontWeight = FontWeight.Bold,
        fontSize = 34.sp,
        lineHeight = 38.sp,
        letterSpacing = (-1.2).sp,
    ),
    headlineLarge = TextStyle(
        fontFamily = NaviSans,
        fontWeight = FontWeight.Bold,
        fontSize = 30.sp,
        lineHeight = 40.sp,
        letterSpacing = (-1.0).sp,
    ),
    // text.display — 화면 표제
    headlineMedium = TextStyle(
        fontFamily = NaviSans,
        fontWeight = FontWeight.Bold,
        fontSize = 26.sp,
        lineHeight = 37.sp,
        letterSpacing = (-0.91).sp,
    ),
    headlineSmall = TextStyle(
        fontFamily = NaviSans,
        fontWeight = FontWeight.Bold,
        fontSize = 22.sp,
        lineHeight = 31.sp,
        letterSpacing = (-0.7).sp,
    ),
    // text.title — 앱바와 섹션 제목
    titleLarge = TextStyle(
        fontFamily = NaviSans,
        fontWeight = FontWeight.Bold,
        fontSize = 18.sp,
        lineHeight = 26.sp,
        letterSpacing = (-0.54).sp,
    ),
    titleMedium = TextStyle(
        fontFamily = NaviSans,
        fontWeight = FontWeight.SemiBold,
        fontSize = 16.sp,
        lineHeight = 23.sp,
        letterSpacing = (-0.4).sp,
    ),
    // text.body — 목록 본문과 설명
    bodyLarge = TextStyle(
        fontFamily = NaviSans,
        fontWeight = FontWeight.Normal,
        fontSize = 15.sp,
        lineHeight = 24.sp,
        letterSpacing = (-0.3).sp,
    ),
    bodyMedium = TextStyle(
        fontFamily = NaviSans,
        fontWeight = FontWeight.Normal,
        fontSize = 14.sp,
        lineHeight = 22.sp,
        letterSpacing = (-0.28).sp,
    ),
    // text.caption — 보조 설명, 출처, 라벨
    bodySmall = TextStyle(
        fontFamily = NaviSans,
        fontWeight = FontWeight.Normal,
        fontSize = 13.sp,
        lineHeight = 20.sp,
        letterSpacing = (-0.26).sp,
    ),
    // 버튼 라벨
    labelLarge = TextStyle(
        fontFamily = NaviSans,
        fontWeight = FontWeight.Bold,
        fontSize = 17.sp,
        lineHeight = 22.sp,
        letterSpacing = (-0.51).sp,
    ),
    labelMedium = TextStyle(
        fontFamily = NaviSans,
        fontWeight = FontWeight.SemiBold,
        fontSize = 12.sp,
        lineHeight = 17.sp,
        letterSpacing = (-0.24).sp,
    ),
)

/**
 * 숫자 체계 — 일반 텍스트와 분리된 4단계.
 *
 * NaVi에는 22분 · 1,303m · +221m · ±8m · 8% · 2cm가 반복된다.
 * 22분과 +221m이 같은 체계에 있으면 안 된다.
 * 네 스타일 모두 tabular numeral을 강제해 자릿수가 바뀌어도 레이아웃이 흔들리지 않는다.
 */

/** metric.primary — 화면당 하나. 사용자가 가장 먼저 알아야 할 값 */
val NaviMetricPrimary = TextStyle(
    fontFamily = NaviSans,
    fontWeight = FontWeight.Bold,
    fontSize = 40.sp,
    lineHeight = 40.sp,
    letterSpacing = (-1.8).sp,
    fontFeatureSettings = "tnum",
)

/** metric.secondary — 거리·도착 예정·개수 */
val NaviMetricSecondary = TextStyle(
    fontFamily = NaviSans,
    fontWeight = FontWeight.Bold,
    fontSize = 18.sp,
    lineHeight = 24.sp,
    letterSpacing = (-0.54).sp,
    fontFeatureSettings = "tnum",
)

/** metric.delta — 비교값. 부호를 항상 붙이고 색은 caution(증가) / pass(감소) */
val NaviMetricDelta = TextStyle(
    fontFamily = NaviSans,
    fontWeight = FontWeight.Bold,
    fontSize = 14.sp,
    lineHeight = 20.sp,
    letterSpacing = (-0.28).sp,
    fontFeatureSettings = "tnum",
)

/** metric.uncertainty — 오차·임계값·조건. 항상 가장 작고 가장 약하다 */
val NaviMetricUncertainty = TextStyle(
    fontFamily = NaviSans,
    fontWeight = FontWeight.SemiBold,
    fontSize = 12.sp,
    lineHeight = 17.sp,
    letterSpacing = 0.sp,
    fontFeatureSettings = "tnum",
)

/**
 * 기존 호출부 호환용 별칭. 새 코드는 [NaviMetricSecondary]를 직접 쓴다.
 *
 * 과거에는 monospace였으나, 안내 중 글랜스 가독성이 떨어져
 * 본문 글꼴 + tabular numeral로 바꿨다(docs/design_tokens.md 참고).
 */
val NaviMetricTextStyle = NaviMetricSecondary
