package kr.co.navi.mobility.navigation

import kotlin.math.PI
import kotlin.math.atan2
import kotlin.math.cos
import kotlin.math.sin

fun bearingDegrees(from: List<Double>, to: List<Double>): Float {
    require(from.size >= 2 && to.size >= 2)
    val lon1 = from[0] * PI / 180.0
    val lat1 = from[1] * PI / 180.0
    val lon2 = to[0] * PI / 180.0
    val lat2 = to[1] * PI / 180.0
    val y = sin(lon2 - lon1) * cos(lat2)
    val x = cos(lat1) * sin(lat2) - sin(lat1) * cos(lat2) * cos(lon2 - lon1)
    return ((Math.toDegrees(atan2(y, x)) + 360.0) % 360.0).toFloat()
}

fun normalizeHeadingDelta(routeBearing: Float, deviceHeading: Float): Float =
    ((routeBearing - deviceHeading + 540f) % 360f) - 180f

fun routeBearing(geometry: List<List<Double>>): Float? =
    geometry.zipWithNext()
        .firstOrNull { (from, to) -> from != to }
        ?.let { (from, to) -> bearingDegrees(from, to) }

fun reasonLabel(reason: String): String = when (reason) {
    "stairs" -> "계단 구간 제외"
    "high_curb" -> "높은 턱 구간 제외"
    "blocked" -> "통행 제한 구간 제외"
    "construction" -> "공사 구간 제외"
    "temporary_closure" -> "임시 통행 불가 구간 제외"
    "session_blocked" -> "방금 확인한 장애 구간 제외"
    "unknown_accessibility" -> "접근성 정보 미확인 구간 제외"
    else -> reason.replace('_', ' ')
}
