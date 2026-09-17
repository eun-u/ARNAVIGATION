package kr.co.navi.mobility.data.model

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.doubleOrNull
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonPrimitive

@Serializable
data class CoordinateDto(
    val lat: Double,
    val lon: Double,
)

@Serializable
data class RouteRequestDto(
    val origin: CoordinateDto,
    val destination: CoordinateDto,
    val profile: String = "wheelchair",
    @SerialName("session_id") val sessionId: String? = null,
)

@Serializable
data class ExcludedEdgeDto(
    @SerialName("edge_id") val edgeId: String,
    val name: String,
    val reasons: List<String> = emptyList(),
)

@Serializable
data class ProvenanceSummaryDto(
    val sources: List<String> = emptyList(),
    @SerialName("accessibility_sources") val accessibilitySources: List<String> = emptyList(),
    @SerialName("contains_synthetic") val containsSynthetic: Boolean = false,
    @SerialName("verified_edges") val verifiedEdges: Int = 0,
    @SerialName("unverified_edges") val unverifiedEdges: Int = 0,
)

@Serializable
data class RouteResultDto(
    val status: String = "ok",
    @SerialName("distance_m") val distanceM: Double,
    @SerialName("estimated_minutes") val estimatedMinutes: Int,
    @SerialName("route_type") val routeType: String,
    val profile: String,
    @SerialName("origin_node") val originNode: String,
    @SerialName("destination_node") val destinationNode: String,
    @SerialName("node_ids") val nodeIds: List<String> = emptyList(),
    @SerialName("edge_ids") val edgeIds: List<String> = emptyList(),
    val geometry: List<List<Double>> = emptyList(),
    @SerialName("excluded_edges") val excludedEdges: List<ExcludedEdgeDto> = emptyList(),
    val reasons: List<String> = emptyList(),
    val warnings: List<String> = emptyList(),
    val provenance: ProvenanceSummaryDto,
    @SerialName("session_id") val sessionId: String? = null,
    @SerialName("graph_revision") val graphRevision: Int? = null,
    @SerialName("expires_at") val expiresAt: String? = null,
)

@Serializable
data class RouteComparisonDto(
    val status: String = "ok",
    val standard: RouteResultDto,
    val accessible: RouteResultDto,
    @SerialName("difference_m") val differenceM: Double,
    @SerialName("difference_pct") val differencePct: Double,
    val reasons: List<String> = emptyList(),
    val warnings: List<String> = emptyList(),
    @SerialName("session_id") val sessionId: String? = null,
    @SerialName("graph_revision") val graphRevision: Int? = null,
    @SerialName("expires_at") val expiresAt: String? = null,
)

@Serializable
data class SessionRerouteRequestDto(
    @SerialName("temporary_blocked_edge_ids") val temporaryBlockedEdgeIds: List<String>,
    val reason: String,
)

@Serializable
data class SessionRerouteResponseDto(
    val status: String,
    @SerialName("session_id") val sessionId: String,
    @SerialName("temporary_blocked_edge_ids") val temporaryBlockedEdgeIds: List<String> = emptyList(),
    @SerialName("graph_revision") val graphRevision: Int,
    @SerialName("route_affected") val routeAffected: Boolean,
    @SerialName("route_changed") val routeChanged: Boolean,
    @SerialName("previous_route") val previousRoute: RouteResultDto? = null,
    @SerialName("recalculated_route") val recalculatedRoute: RouteResultDto? = null,
    val comparison: RouteComparisonDto? = null,
    val warnings: List<String> = emptyList(),
)

@Serializable
data class ObservationCandidateCreateDto(
    @SerialName("edge_id") val edgeId: String,
    val type: String = "blocked_path",
    val source: String = "manual_camera",
    @SerialName("session_id") val sessionId: String? = null,
    @SerialName("observed_at") val observedAt: String? = null,
    val note: String? = null,
    val lat: Double? = null,
    val lon: Double? = null,
)

@Serializable
data class ObservationCandidateDto(
    @SerialName("candidate_id") val candidateId: String,
    @SerialName("edge_id") val edgeId: String,
    val type: String,
    val source: String,
    val confidence: Double? = null,
    val status: String,
    val verified: Boolean = false,
    @SerialName("session_id") val sessionId: String? = null,
    @SerialName("observed_at") val observedAt: String? = null,
    @SerialName("ai_note") val note: String? = null,
    val lat: Double? = null,
    val lon: Double? = null,
)

@Serializable
data class GraphResponseDto(
    val type: String,
    val metadata: GraphMetadataDto,
    val features: List<GraphFeatureDto> = emptyList(),
)

@Serializable
data class GraphMetadataDto(
    val name: String = "NaVi Accessibility Graph",
    val area: String = "테스트 구역",
    val source: String = "unknown",
    @SerialName("accessibility_attributes") val accessibilityAttributes: String = "unknown",
    val verified: Boolean = false,
    val disclaimer: String = "현장 검증이 필요한 실험 데이터입니다.",
    val demo: DemoMetadataDto? = null,
)

@Serializable
data class DemoMetadataDto(
    @SerialName("origin_node") val originNode: String,
    @SerialName("destination_node") val destinationNode: String,
    @SerialName("block_edge") val blockEdge: String,
)

@Serializable
data class GraphFeatureDto(
    val geometry: GraphGeometryDto,
    val properties: JsonObject,
)

@Serializable
data class GraphGeometryDto(
    val type: String,
    val coordinates: JsonElement,
)

data class NamedCoordinate(
    val id: String,
    val name: String,
    val coordinate: CoordinateDto,
)

data class NaviBootstrap(
    val areaName: String,
    val source: String,
    val accessibilityAttributes: String,
    val disclaimer: String,
    val origin: NamedCoordinate,
    val destination: NamedCoordinate,
    val blockEdgeId: String,
    val blockEdgeGeometry: List<List<Double>>,
    val coverageBounds: CoverageBounds,
)

data class CoverageBounds(
    val minLat: Double,
    val minLon: Double,
    val maxLat: Double,
    val maxLon: Double,
) {
    fun contains(coordinate: CoordinateDto, marginDegrees: Double = 0.003): Boolean =
        coordinate.lat in (minLat - marginDegrees)..(maxLat + marginDegrees) &&
            coordinate.lon in (minLon - marginDegrees)..(maxLon + marginDegrees)
}

fun GraphResponseDto.toBootstrap(): NaviBootstrap {
    val demoConfig = requireNotNull(metadata.demo) { "Graph metadata.demo is required for the PoC" }
    val nodes = features
        .filter { it.properties.string("feature_type") == "node" }
        .associateBy { requireNotNull(it.properties.string("node_id")) }
    val edges = features
        .filter { it.properties.string("feature_type") == "edge" }
        .associateBy { requireNotNull(it.properties.string("edge_id")) }
    val nodeCoordinates = nodes.values.map { feature ->
        val values = feature.geometry.coordinates.jsonArray
        CoordinateDto(
            lon = requireNotNull(values.getOrNull(0)?.jsonPrimitive?.doubleOrNull),
            lat = requireNotNull(values.getOrNull(1)?.jsonPrimitive?.doubleOrNull),
        )
    }
    require(nodeCoordinates.isNotEmpty()) { "Graph must contain at least one node" }

    fun namedNode(nodeId: String): NamedCoordinate {
        val feature = requireNotNull(nodes[nodeId]) { "Graph node $nodeId is missing" }
        val values = feature.geometry.coordinates.jsonArray
        return NamedCoordinate(
            id = nodeId,
            name = feature.properties.string("name") ?: nodeId,
            coordinate = CoordinateDto(
                lon = requireNotNull(values.getOrNull(0)?.jsonPrimitive?.doubleOrNull),
                lat = requireNotNull(values.getOrNull(1)?.jsonPrimitive?.doubleOrNull),
            ),
        )
    }

    val blockFeature = requireNotNull(edges[demoConfig.blockEdge]) {
        "Graph edge ${demoConfig.blockEdge} is missing"
    }
    val blockGeometry = blockFeature.geometry.coordinates.jsonArray.map { point ->
        point.jsonArray.map { requireNotNull(it.jsonPrimitive.doubleOrNull) }
    }

    return NaviBootstrap(
        areaName = metadata.area,
        source = metadata.source,
        accessibilityAttributes = metadata.accessibilityAttributes,
        disclaimer = metadata.disclaimer,
        origin = namedNode(demoConfig.originNode),
        destination = namedNode(demoConfig.destinationNode),
        blockEdgeId = demoConfig.blockEdge,
        blockEdgeGeometry = blockGeometry,
        coverageBounds = CoverageBounds(
            minLat = nodeCoordinates.minOf { it.lat },
            minLon = nodeCoordinates.minOf { it.lon },
            maxLat = nodeCoordinates.maxOf { it.lat },
            maxLon = nodeCoordinates.maxOf { it.lon },
        ),
    )
}

private fun JsonObject.string(key: String): String? = get(key)?.jsonPrimitive?.contentOrNull
