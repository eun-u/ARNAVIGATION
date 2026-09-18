package kr.co.navi.mobility.ui.screens

import kr.co.navi.mobility.data.model.CoordinateDto
import kr.co.navi.mobility.data.model.CoverageBounds
import kr.co.navi.mobility.data.model.NamedCoordinate
import kr.co.navi.mobility.data.model.NaviBootstrap
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class NaviScreensTrustTextTest {
    @Test
    fun `local osm graph displays unknown unverified boundary without synthetic claim`() {
        val bootstrap = NaviBootstrap(
            areaName = "전북대학교 106 학생군사교육단 남측 보행로",
            source = "OpenStreetMap local snapshot",
            accessibilityAttributes = "unknown_unverified",
            disclaimer = "공용 Graph에는 반영하지 않습니다.",
            origin = point("A"),
            destination = point("B"),
            blockEdgeId = "E1",
            blockEdgeGeometry = emptyList(),
            coverageBounds = CoverageBounds(35.0, 127.0, 36.0, 128.0),
        )

        val text = bootstrapTrustText(bootstrap)

        assertTrue(text.contains("OSM 로컬 스냅샷"))
        assertTrue(text.contains("접근성 속성 미확인·미검증"))
        assertTrue(text.contains("공용 Graph에는 반영하지 않습니다."))
        assertFalse(text.contains("synthetic"))
    }

    private fun point(id: String) = NamedCoordinate(
        id = id,
        name = id,
        coordinate = CoordinateDto(lat = 35.8422, lon = 127.1313),
    )
}
