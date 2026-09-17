package kr.co.navi.mobility.ui.components

import android.graphics.Color as AndroidColor
import android.graphics.PointF
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.Alignment
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.LocalLifecycleOwner
import kr.co.navi.mobility.data.model.RouteResultDto
import kr.co.navi.mobility.ui.theme.NaviBlue
import kr.co.navi.mobility.ui.theme.NaviCanvas
import kr.co.navi.mobility.ui.theme.NaviInkMuted
import kr.co.navi.mobility.ui.theme.NaviViolet
import org.maplibre.android.camera.CameraPosition
import org.maplibre.android.camera.CameraUpdateFactory
import org.maplibre.android.geometry.LatLng
import org.maplibre.android.geometry.LatLngBounds
import org.maplibre.android.maps.MapLibreMap
import org.maplibre.android.maps.MapView
import org.maplibre.android.maps.Style
import org.maplibre.android.style.layers.LineLayer
import org.maplibre.android.style.layers.PropertyFactory.lineCap
import org.maplibre.android.style.layers.PropertyFactory.lineColor
import org.maplibre.android.style.layers.PropertyFactory.lineDasharray
import org.maplibre.android.style.layers.PropertyFactory.lineJoin
import org.maplibre.android.style.layers.PropertyFactory.lineOpacity
import org.maplibre.android.style.layers.PropertyFactory.lineWidth
import org.maplibre.android.style.layers.Property.LINE_CAP_ROUND
import org.maplibre.android.style.layers.Property.LINE_JOIN_ROUND
import org.maplibre.android.style.sources.GeoJsonSource
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonArray
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put

@Composable
fun RouteMap(
    standard: RouteResultDto,
    accessible: RouteResultDto,
    blockGeometry: List<List<Double>>,
    rerouted: Boolean,
    modifier: Modifier = Modifier,
) {
    val mapView = rememberMapViewWithLifecycle()
    var mapReady by remember { mutableStateOf(false) }
    var mapFailed by remember { mutableStateOf(false) }
    var startScreenPoint by remember { mutableStateOf<PointF?>(null) }
    var endScreenPoint by remember { mutableStateOf<PointF?>(null) }
    val markerRadiusPx = with(LocalDensity.current) { 18.dp.roundToPx() }
    val standardJson = remember(standard.geometry) { lineGeoJson(standard.geometry) }
    val accessibleJson = remember(accessible.geometry) { lineGeoJson(accessible.geometry) }
    val blockJson = remember(blockGeometry) { lineGeoJson(blockGeometry) }

    LaunchedEffect(mapView, standardJson, accessibleJson, blockJson, rerouted) {
        runCatching {
            mapView.getMapAsync { map ->
                val existingStyle = map.style
                if (existingStyle == null || !existingStyle.isFullyLoaded) {
                    map.setStyle(Style.Builder().fromJson(BASE_STYLE_JSON)) { style ->
                        installOrUpdateRoutes(
                            style,
                            standardJson,
                            accessibleJson,
                            blockJson,
                            rerouted,
                        )
                        fitRoute(mapView, standard.geometry + accessible.geometry)
                        positionEndpointBadges(mapView, map, accessible.geometry) { start, end ->
                            startScreenPoint = start
                            endScreenPoint = end
                        }
                        mapReady = true
                    }
                } else {
                    installOrUpdateRoutes(
                        existingStyle,
                        standardJson,
                        accessibleJson,
                        blockJson,
                        rerouted,
                    )
                    fitRoute(mapView, standard.geometry + accessible.geometry)
                    positionEndpointBadges(mapView, map, accessible.geometry) { start, end ->
                        startScreenPoint = start
                        endScreenPoint = end
                    }
                    mapReady = true
                }
            }
        }.onFailure { mapFailed = true }
    }

    Box(modifier.background(NaviCanvas)) {
        RouteCanvas(
            standard = standard.geometry,
            accessible = accessible.geometry,
            blockGeometry = blockGeometry,
            rerouted = rerouted,
            modifier = Modifier.fillMaxSize(),
        )
        if (!mapFailed) {
            AndroidView(
                factory = { mapView },
                modifier = Modifier.fillMaxSize(),
            )
        }
        if (!mapReady || mapFailed) {
            Text(
                text = if (mapFailed) "오프라인 경로 보기" else "지도를 준비하고 있습니다",
                modifier = Modifier.padding(12.dp),
                style = MaterialTheme.typography.labelMedium,
                color = NaviInkMuted,
            )
        }
        MapLegend(
            rerouted = rerouted,
            modifier = Modifier
                .align(Alignment.TopEnd)
                .padding(12.dp),
        )
        startScreenPoint?.let { point ->
            EndpointBadge(
                label = "A",
                description = "출발 A",
                color = NaviBlue,
                modifier = Modifier.offset {
                    IntOffset(point.x.toInt() - markerRadiusPx, point.y.toInt() - markerRadiusPx)
                },
            )
        }
        endScreenPoint?.let { point ->
            EndpointBadge(
                label = "B",
                description = "도착 B",
                color = NaviViolet,
                modifier = Modifier.offset {
                    IntOffset(point.x.toInt() - markerRadiusPx, point.y.toInt() - markerRadiusPx)
                },
            )
        }
    }
}

@Composable
private fun EndpointBadge(
    label: String,
    description: String,
    color: Color,
    modifier: Modifier = Modifier,
) {
    Box(
        modifier = modifier
            .size(36.dp)
            .background(Color.White, CircleShape)
            .padding(3.dp)
            .background(color, CircleShape)
            .semantics { contentDescription = description },
        contentAlignment = Alignment.Center,
    ) {
        Text(label, color = Color.White, fontWeight = FontWeight.ExtraBold)
    }
}

@Composable
private fun MapLegend(
    rerouted: Boolean,
    modifier: Modifier = Modifier,
) {
    Surface(
        modifier = modifier,
        color = MaterialTheme.colorScheme.surface.copy(alpha = 0.94f),
        shape = MaterialTheme.shapes.small,
        shadowElevation = 2.dp,
    ) {
        Column(
            modifier = Modifier.padding(horizontal = 10.dp, vertical = 8.dp),
            verticalArrangement = Arrangement.spacedBy(5.dp),
        ) {
            LegendItem("일반 최단", Color(0xFF64748B))
            LegendItem(if (rerouted) "재탐색 경로" else "접근 가능", if (rerouted) NaviViolet else NaviBlue)
            if (rerouted) LegendItem("제보 차단", Color(0xFFC8202F))
        }
    }
}

@Composable
private fun LegendItem(label: String, color: Color) {
    Row(
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(7.dp),
    ) {
        Box(Modifier.size(width = 22.dp, height = 5.dp).background(color, CircleShape))
        Text(
            text = label,
            style = MaterialTheme.typography.labelSmall,
            color = NaviInkMuted,
            fontWeight = FontWeight.SemiBold,
        )
    }
}

@Composable
private fun rememberMapViewWithLifecycle(): MapView {
    val context = LocalContext.current
    val lifecycle = LocalLifecycleOwner.current.lifecycle
    val mapView = remember { MapView(context).apply { onCreate(null) } }

    DisposableEffect(lifecycle, mapView) {
        val observer = LifecycleEventObserver { _, event ->
            when (event) {
                Lifecycle.Event.ON_START -> mapView.onStart()
                Lifecycle.Event.ON_RESUME -> mapView.onResume()
                Lifecycle.Event.ON_PAUSE -> mapView.onPause()
                Lifecycle.Event.ON_STOP -> mapView.onStop()
                Lifecycle.Event.ON_DESTROY -> mapView.onDestroy()
                else -> Unit
            }
        }
        lifecycle.addObserver(observer)
        if (lifecycle.currentState.isAtLeast(Lifecycle.State.STARTED)) mapView.onStart()
        if (lifecycle.currentState.isAtLeast(Lifecycle.State.RESUMED)) mapView.onResume()
        onDispose {
            lifecycle.removeObserver(observer)
            if (lifecycle.currentState.isAtLeast(Lifecycle.State.RESUMED)) mapView.onPause()
            if (lifecycle.currentState.isAtLeast(Lifecycle.State.STARTED)) mapView.onStop()
            mapView.onDestroy()
        }
    }
    return mapView
}

private fun installOrUpdateRoutes(
    style: Style,
    standardJson: String,
    accessibleJson: String,
    blockJson: String,
    rerouted: Boolean,
) {
    addOrUpdateSource(style, STANDARD_SOURCE, standardJson)
    addOrUpdateSource(style, ACCESSIBLE_SOURCE, accessibleJson)
    addOrUpdateSource(style, BLOCK_SOURCE, blockJson)

    if (style.getLayer(STANDARD_LAYER) == null) {
        style.addLayer(
            LineLayer(STANDARD_LAYER, STANDARD_SOURCE).withProperties(
                lineColor(AndroidColor.parseColor("#64748B")),
                lineWidth(4f),
                lineOpacity(0.72f),
                lineCap(LINE_CAP_ROUND),
                lineJoin(LINE_JOIN_ROUND),
            ),
        )
    }
    val accessibleColor = if (rerouted) "#7C3AED" else "#2563EB"
    val accessibleLayer = style.getLayerAs<LineLayer>(ACCESSIBLE_LAYER)
    if (accessibleLayer == null) {
        style.addLayer(
            LineLayer(ACCESSIBLE_LAYER, ACCESSIBLE_SOURCE).withProperties(
                lineColor(AndroidColor.parseColor(accessibleColor)),
                lineWidth(7f),
                lineOpacity(0.94f),
                lineCap(LINE_CAP_ROUND),
                lineJoin(LINE_JOIN_ROUND),
            ),
        )
    } else {
        accessibleLayer.setProperties(lineColor(AndroidColor.parseColor(accessibleColor)))
    }
    if (style.getLayer(BLOCK_LAYER) == null) {
        style.addLayer(
            LineLayer(BLOCK_CASING_LAYER, BLOCK_SOURCE).withProperties(
                lineColor(AndroidColor.WHITE),
                lineWidth(12f),
                lineOpacity(0.9f),
                lineCap(LINE_CAP_ROUND),
            ),
        )
        style.addLayer(
            LineLayer(BLOCK_LAYER, BLOCK_SOURCE).withProperties(
                lineColor(AndroidColor.parseColor("#C8202F")),
                lineWidth(8f),
                lineOpacity(0.96f),
                lineDasharray(arrayOf(1.2f, 1.2f)),
                lineCap(LINE_CAP_ROUND),
            ),
        )
    }
}

private fun addOrUpdateSource(style: Style, id: String, geoJson: String) {
    val source = style.getSourceAs<GeoJsonSource>(id)
    if (source == null) style.addSource(GeoJsonSource(id, geoJson)) else source.setGeoJson(geoJson)
}

private fun fitRoute(mapView: MapView, geometry: List<List<Double>>) {
    val points = geometry.mapNotNull { point ->
        if (point.size >= 2) LatLng(point[1], point[0]) else null
    }
    if (points.size < 2) return
    mapView.getMapAsync { map ->
        val bounds = LatLngBounds.Builder().includes(points).build()
        val padding = (72 * mapView.resources.displayMetrics.density).toInt()
        runCatching { map.moveCamera(CameraUpdateFactory.newLatLngBounds(bounds, padding)) }
            .onFailure {
                map.cameraPosition = CameraPosition.Builder().target(points.first()).zoom(15.0).build()
            }
    }
}

private fun positionEndpointBadges(
    mapView: MapView,
    map: MapLibreMap,
    geometry: List<List<Double>>,
    onPositioned: (PointF, PointF) -> Unit,
) {
    val start = geometry.firstOrNull()?.takeIf { it.size >= 2 } ?: return
    val end = geometry.lastOrNull()?.takeIf { it.size >= 2 } ?: return
    map.uiSettings.setAllGesturesEnabled(false)
    mapView.post {
        onPositioned(
            map.projection.toScreenLocation(LatLng(start[1], start[0])),
            map.projection.toScreenLocation(LatLng(end[1], end[0])),
        )
    }
}

private fun lineGeoJson(geometry: List<List<Double>>): String = buildJsonObject {
    put("type", "FeatureCollection")
    put("features", buildJsonArray {
        if (geometry.size >= 2) {
            add(buildJsonObject {
                put("type", "Feature")
                put("properties", buildJsonObject {})
                put("geometry", buildJsonObject {
                    put("type", "LineString")
                    put("coordinates", JsonArray(geometry.map { point ->
                        JsonArray(point.take(2).map(::JsonPrimitive))
                    }))
                })
            })
        }
    })
}.toString()

@Composable
private fun RouteCanvas(
    standard: List<List<Double>>,
    accessible: List<List<Double>>,
    blockGeometry: List<List<Double>>,
    rerouted: Boolean,
    modifier: Modifier = Modifier,
) {
    Canvas(modifier.background(Color(0xFFF1F5F9))) {
        val all = standard + accessible + blockGeometry
        if (all.isEmpty()) return@Canvas
        val minLon = all.minOf { it[0] }
        val maxLon = all.maxOf { it[0] }
        val minLat = all.minOf { it[1] }
        val maxLat = all.maxOf { it[1] }
        val lonSpan = (maxLon - minLon).takeIf { it > 0 } ?: 1.0
        val latSpan = (maxLat - minLat).takeIf { it > 0 } ?: 1.0

        fun path(points: List<List<Double>>): Path = Path().apply {
            points.forEachIndexed { index, point ->
                val x = ((point[0] - minLon) / lonSpan).toFloat() * size.width * 0.86f + size.width * 0.07f
                val y = size.height - (((point[1] - minLat) / latSpan).toFloat() * size.height * 0.82f + size.height * 0.09f)
                if (index == 0) moveTo(x, y) else lineTo(x, y)
            }
        }
        drawPath(path(standard), Color(0xFF64748B), style = Stroke(4.dp.toPx(), cap = StrokeCap.Round))
        drawPath(
            path(accessible),
            if (rerouted) NaviViolet else NaviBlue,
            style = Stroke(7.dp.toPx(), cap = StrokeCap.Round),
        )
        drawPath(path(blockGeometry), Color.White, style = Stroke(12.dp.toPx(), cap = StrokeCap.Round))
        drawPath(path(blockGeometry), Color(0xFFC8202F), style = Stroke(8.dp.toPx(), cap = StrokeCap.Round))
    }
}

private const val STANDARD_SOURCE = "navi-standard-source"
private const val ACCESSIBLE_SOURCE = "navi-accessible-source"
private const val BLOCK_SOURCE = "navi-block-source"
private const val STANDARD_LAYER = "navi-standard-layer"
private const val ACCESSIBLE_LAYER = "navi-accessible-layer"
private const val BLOCK_CASING_LAYER = "navi-block-casing-layer"
private const val BLOCK_LAYER = "navi-block-layer"

private val BASE_STYLE_JSON = """
{
  "version": 8,
  "name": "NaVi Light",
  "sources": {
    "osm": {
      "type": "raster",
      "tiles": ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
      "tileSize": 256,
      "attribution": "© OpenStreetMap contributors"
    }
  },
  "layers": [
    {"id": "osm", "type": "raster", "source": "osm", "paint": {"raster-opacity": 0.82}}
  ]
}
""".trimIndent()
