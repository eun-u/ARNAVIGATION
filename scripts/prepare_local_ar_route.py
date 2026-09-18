from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import networkx as nx
import osmnx as ox
from pyproj import Transformer
from shapely.geometry import LineString, Point
from shapely.ops import substring, transform


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "data" / "runtime" / "local-field-tests"
PREFERRED_HIGHWAYS = {
    "footway": 0,
    "pedestrian": 1,
    "path": 2,
    "living_street": 3,
    "residential": 4,
}
REJECTED_ACCESS = {"customers", "no", "permit", "private"}


def as_values(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return [str(item) for item in value]
    return [str(value)]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def utm_epsg(lat: float, lon: float) -> int:
    zone = int((lon + 180.0) / 6.0) + 1
    return (32600 if lat >= 0 else 32700) + zone


def oriented_geometry(
    graph: nx.MultiGraph,
    from_node: Any,
    to_node: Any,
    attributes: dict[str, Any],
) -> LineString:
    geometry = attributes.get("geometry")
    if not isinstance(geometry, LineString):
        geometry = LineString(
            [
                (float(graph.nodes[from_node]["x"]), float(graph.nodes[from_node]["y"])),
                (float(graph.nodes[to_node]["x"]), float(graph.nodes[to_node]["y"])),
            ]
        )
    origin = Point(
        float(graph.nodes[from_node]["x"]),
        float(graph.nodes[from_node]["y"]),
    )
    coordinates = list(geometry.coords)
    if origin.distance(Point(coordinates[-1])) < origin.distance(Point(coordinates[0])):
        coordinates.reverse()
    return LineString(coordinates)


def highway_priority(attributes: dict[str, Any]) -> int | None:
    highway_values = as_values(attributes.get("highway"))
    if "steps" in highway_values:
        return None
    if REJECTED_ACCESS.intersection(as_values(attributes.get("access"))):
        return None
    if "no" in as_values(attributes.get("foot")):
        return None
    if "crossing" in as_values(attributes.get("footway")):
        return None
    if attributes.get("indoor") in {"yes", True}:
        return None
    priorities = [PREFERRED_HIGHWAYS[item] for item in highway_values if item in PREFERRED_HIGHWAYS]
    return min(priorities) if priorities else None


def select_route_segment(
    graph: nx.MultiGraph,
    *,
    center_lat: float,
    center_lon: float,
    target_length_m: float,
    max_center_distance_m: float,
) -> dict[str, Any]:
    epsg = utm_epsg(center_lat, center_lon)
    to_local = Transformer.from_crs("EPSG:4326", f"EPSG:{epsg}", always_xy=True)
    to_wgs84 = Transformer.from_crs(f"EPSG:{epsg}", "EPSG:4326", always_xy=True)
    center = Point(*to_local.transform(center_lon, center_lat))
    candidates: list[tuple[tuple[Any, ...], dict[str, Any]]] = []

    for from_node, to_node, key, attributes in graph.edges(keys=True, data=True):
        priority = highway_priority(attributes)
        if priority is None:
            continue
        wgs84_line = oriented_geometry(graph, from_node, to_node, attributes)
        local_line = transform(to_local.transform, wgs84_line)
        if local_line.length < target_length_m:
            continue
        center_distance = center.distance(local_line)
        if center_distance > max_center_distance_m:
            continue

        nearest_offset = local_line.project(center)
        start_offset = max(
            0.0,
            min(nearest_offset - target_length_m / 2.0, local_line.length - target_length_m),
        )
        segment_local = substring(
            local_line,
            start_offset,
            start_offset + target_length_m,
        )
        if not isinstance(segment_local, LineString) or len(segment_local.coords) < 2:
            continue
        segment_wgs84 = transform(to_wgs84.transform, segment_local)
        osm_ids = sorted(as_values(attributes.get("osmid")))
        identity = f"{from_node}|{to_node}|{key}|{'-'.join(osm_ids)}"
        candidate = {
            "from_node": str(from_node),
            "to_node": str(to_node),
            "key": str(key),
            "osm_way_ids": osm_ids,
            "attributes": dict(attributes),
            "center_distance_m": round(center_distance, 3),
            "length_m": round(float(segment_local.length), 3),
            "coordinates": [
                [round(float(lon), 8), round(float(lat), 8)]
                for lon, lat in segment_wgs84.coords
            ],
            "identity": identity,
            "projection_epsg": epsg,
        }
        score = (
            priority,
            round(center_distance, 3),
            -round(float(local_line.length), 3),
            identity,
        )
        candidates.append((score, candidate))

    if not candidates:
        raise RuntimeError(
            "No non-crossing public walking edge can provide the requested test segment"
        )
    return min(candidates, key=lambda item: item[0])[1]


def bearing_degrees(coordinates: list[list[float]]) -> float:
    start_lon, start_lat = coordinates[0]
    end_lon, end_lat = coordinates[-1]
    start_lat_radians = math.radians(start_lat)
    end_lat_radians = math.radians(end_lat)
    longitude_delta = math.radians(end_lon - start_lon)
    y = math.sin(longitude_delta) * math.cos(end_lat_radians)
    x = (
        math.cos(start_lat_radians) * math.sin(end_lat_radians)
        - math.sin(start_lat_radians)
        * math.cos(end_lat_radians)
        * math.cos(longitude_delta)
    )
    return round((math.degrees(math.atan2(y, x)) + 360.0) % 360.0, 2)


def build_graph_payload(
    *,
    label: str,
    segment: dict[str, Any],
    fetched_at: str,
) -> tuple[dict[str, Any], str]:
    coordinates = segment["coordinates"]
    edge_hash = hashlib.sha256(segment["identity"].encode("utf-8")).hexdigest()[:12]
    edge_id = f"LOCAL_OSM_{edge_hash}"
    osm_way_ids = segment["osm_way_ids"]
    attributes = segment["attributes"]
    source_links = [
        f"https://www.openstreetmap.org/way/{way_id}"
        for way_id in osm_way_ids
        if way_id.isdigit()
    ]
    common_node_properties = {
        "feature_type": "node",
        "node_type": "field_test_endpoint",
        "source": "osm",
        "confidence": None,
        "verified": False,
    }
    edge_properties = {
        "feature_type": "edge",
        "edge_id": edge_id,
        "from_node": "LOCAL_ORIGIN",
        "to_node": "LOCAL_DESTINATION",
        "name": f"{label} 25m AR 정합 시험 구간",
        "length": segment["length_m"],
        "stairs": False,
        "slope": None,
        "width": None,
        "curb_height": None,
        "surface": None,
        "elevator_required": False,
        "elevator_status": None,
        "blocked": False,
        "block_reason": None,
        "wheelchair_accessible": None,
        "accessibility_status": "unknown",
        "source": "osm",
        "accessibility_source": "unverified_osm_geometry_only",
        "confidence": None,
        "verified": False,
        "updated_at": None,
        "highway": as_values(attributes.get("highway")),
        "raw_osm_tags": {
            key: attributes.get(key)
            for key in (
                "access",
                "foot",
                "footway",
                "highway",
                "name",
                "surface",
                "wheelchair",
                "width",
            )
            if attributes.get(key) is not None
        },
        "osm_way_ids": osm_way_ids,
        "osm_source_links": source_links,
        "field_test_only": True,
        "shared_graph_mutation_allowed": False,
    }
    payload = {
        "type": "FeatureCollection",
        "metadata": {
            "name": f"NaVi local AR alignment graph - {label}",
            "area": label,
            "crs": "EPSG:4326",
            "source": "OpenStreetMap local snapshot",
            "source_url": "https://www.openstreetmap.org/copyright",
            "license": "ODbL",
            "accessibility_attributes": "unknown_unverified",
            "verified": False,
            "field_test_only": True,
            "shared_graph_mutation_allowed": False,
            "fetched_at": fetched_at,
            "disclaimer": (
                "OSM 형상만 사용하며 접근성 속성은 미확인·미검증입니다. "
                "로컬 AR 정합 시험에만 사용하고 공용 Graph에는 반영하지 않습니다."
            ),
            "demo": {
                "origin_node": "LOCAL_ORIGIN",
                "destination_node": "LOCAL_DESTINATION",
                "block_edge": edge_id,
            },
        },
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": coordinates[0]},
                "properties": {
                    **common_node_properties,
                    "node_id": "LOCAL_ORIGIN",
                    "name": f"{label} 시험 시작",
                },
            },
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": coordinates[-1]},
                "properties": {
                    **common_node_properties,
                    "node_id": "LOCAL_DESTINATION",
                    "name": f"{label} 시험 종료",
                },
            },
            {
                "type": "Feature",
                "geometry": {"type": "LineString", "coordinates": coordinates},
                "properties": edge_properties,
            },
        ],
    }
    return payload, edge_id


def fetch_graph(
    *,
    center_lat: float,
    center_lon: float,
    radius_m: int,
    as_of: str | None,
) -> nx.MultiDiGraph:
    ox.settings.use_cache = True
    ox.settings.cache_folder = PROJECT_ROOT / "data" / "raw" / "osmnx_cache"
    ox.settings.requests_timeout = 180
    if as_of:
        ox.settings.overpass_settings = (
            f'[out:json][timeout:{{timeout}}]{{maxsize}}[date:"{as_of}"]'
        )
    ox.settings.useful_tags_way = list(
        dict.fromkeys(
            [
                *ox.settings.useful_tags_way,
                "access",
                "foot",
                "footway",
                "highway",
                "incline",
                "indoor",
                "kerb",
                "sidewalk",
                "smoothness",
                "surface",
                "wheelchair",
                "width",
            ]
        )
    )
    return ox.graph.graph_from_point(
        (center_lat, center_lon),
        dist=radius_m,
        network_type="walk",
        simplify=True,
        retain_all=True,
    )


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Prepare a local-only 20-30m OSM route for AR alignment testing."
    )
    parser.add_argument("--label", required=True)
    parser.add_argument("--slug", required=True)
    parser.add_argument("--center-lat", type=float, required=True)
    parser.add_argument("--center-lon", type=float, required=True)
    parser.add_argument("--radius-m", type=int, default=180)
    parser.add_argument("--target-length-m", type=float, default=25.0)
    parser.add_argument("--max-center-distance-m", type=float, default=100.0)
    parser.add_argument("--as-of")
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    args = parser.parse_args()

    if not 20.0 <= args.target_length_m <= 30.0:
        parser.error("--target-length-m must be between 20 and 30")
    if not 50 <= args.radius_m <= 1_000:
        parser.error("--radius-m must be between 50 and 1000")

    fetched_at = datetime.now(timezone.utc).isoformat()
    graph = fetch_graph(
        center_lat=args.center_lat,
        center_lon=args.center_lon,
        radius_m=args.radius_m,
        as_of=args.as_of,
    )
    segment = select_route_segment(
        graph,
        center_lat=args.center_lat,
        center_lon=args.center_lon,
        target_length_m=args.target_length_m,
        max_center_distance_m=args.max_center_distance_m,
    )
    graph_payload, edge_id = build_graph_payload(
        label=args.label,
        segment=segment,
        fetched_at=fetched_at,
    )

    output_directory = args.output_root.resolve() / args.slug
    output_directory.mkdir(parents=True, exist_ok=True)
    raw_graph_path = output_directory / "osm-walk.graphml"
    route_graph_path = output_directory / "route.geojson"
    manifest_path = output_directory / "manifest.json"
    ox.io.save_graphml(graph, raw_graph_path)
    write_json(route_graph_path, graph_payload)

    manifest = {
        "schema_version": 1,
        "dataset_id": f"local-ar-{args.slug}",
        "label": args.label,
        "created_at": fetched_at,
        "privacy_classification": "public_landmark",
        "center": {"lat": args.center_lat, "lon": args.center_lon},
        "radius_m": args.radius_m,
        "requested_length_m": args.target_length_m,
        "selected_length_m": segment["length_m"],
        "selected_center_distance_m": segment["center_distance_m"],
        "bearing_degrees": bearing_degrees(segment["coordinates"]),
        "projection_epsg": segment["projection_epsg"],
        "osm_way_ids": segment["osm_way_ids"],
        "edge_id": edge_id,
        "origin": segment["coordinates"][0],
        "destination": segment["coordinates"][-1],
        "source": "OpenStreetMap via Overpass API",
        "source_url": "https://www.openstreetmap.org/copyright",
        "license": "ODbL",
        "accessibility_status": "unknown",
        "verified": False,
        "field_verified": False,
        "shared_graph_mutation_allowed": False,
        "allowed_use": "local_ar_alignment_test_only",
        "raw_graph": {
            "path": raw_graph_path.name,
            "sha256": sha256(raw_graph_path),
            "nodes": graph.number_of_nodes(),
            "edges": graph.number_of_edges(),
        },
        "route_graph": {
            "path": route_graph_path.name,
            "sha256": sha256(route_graph_path),
        },
    }
    write_json(manifest_path, manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
