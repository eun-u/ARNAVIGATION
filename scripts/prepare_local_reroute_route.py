from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import networkx as nx
import osmnx as ox

if __package__:
    from scripts.prepare_local_ar_route import (
        DEFAULT_OUTPUT_ROOT,
        as_values,
        fetch_graph,
        highway_priority,
        oriented_geometry,
        sha256,
        write_json,
    )
else:  # Direct execution adds scripts/, not the repository root, to sys.path.
    from prepare_local_ar_route import (  # type: ignore[no-redef]
        DEFAULT_OUTPUT_ROOT,
        as_values,
        fetch_graph,
        highway_priority,
        oriented_geometry,
        sha256,
        write_json,
    )


def _node_lookup(graph: nx.MultiGraph, requested: str) -> Any:
    matches = [node for node in graph.nodes if str(node) == requested]
    if len(matches) != 1:
        raise RuntimeError(f"OSM node {requested} is missing or ambiguous")
    return matches[0]


def _edge_identity(from_node: Any, to_node: Any) -> frozenset[Any]:
    return frozenset((from_node, to_node))


def _path_edges(path: list[Any]) -> list[tuple[Any, Any]]:
    return list(zip(path, path[1:]))


def build_eligible_graph(graph: nx.MultiGraph) -> nx.Graph:
    eligible = nx.Graph()
    eligible.add_nodes_from(graph.nodes(data=True))
    for from_node, to_node, key, attributes in graph.edges(keys=True, data=True):
        if highway_priority(attributes) is None:
            continue
        length = float(attributes.get("length", 0.0))
        if length <= 0:
            continue
        selected = {
            "length": length,
            "source_key": key,
            "source_attributes": dict(attributes),
        }
        existing = eligible.get_edge_data(from_node, to_node)
        if existing is None or length < float(existing["length"]):
            eligible.add_edge(from_node, to_node, **selected)
    return eligible


def _path_length(graph: nx.Graph, path: list[Any]) -> float:
    return sum(float(graph[from_node][to_node]["length"]) for from_node, to_node in _path_edges(path))


def _shared_prefix_nodes(primary: list[Any], alternate: list[Any]) -> list[Any]:
    shared: list[Any] = []
    for primary_node, alternate_node in zip(primary, alternate):
        if primary_node != alternate_node:
            break
        shared.append(primary_node)
    return shared


def _shared_suffix_nodes(primary: list[Any], alternate: list[Any]) -> list[Any]:
    shared_reversed: list[Any] = []
    for primary_node, alternate_node in zip(reversed(primary), reversed(alternate)):
        if primary_node != alternate_node:
            break
        shared_reversed.append(primary_node)
    return list(reversed(shared_reversed))


def select_reroute_paths(
    graph: nx.MultiGraph,
    *,
    origin_node_id: str,
    destination_node_id: str,
    block_from_node_id: str,
    block_to_node_id: str,
) -> dict[str, Any]:
    eligible = build_eligible_graph(graph)
    origin = _node_lookup(eligible, origin_node_id)
    destination = _node_lookup(eligible, destination_node_id)
    block_from = _node_lookup(eligible, block_from_node_id)
    block_to = _node_lookup(eligible, block_to_node_id)

    if not eligible.has_edge(block_from, block_to):
        raise RuntimeError(
            f"Requested block edge {block_from_node_id}-{block_to_node_id} is unavailable"
        )

    try:
        primary = nx.shortest_path(eligible, origin, destination, weight="length")
    except (nx.NetworkXNoPath, nx.NodeNotFound) as exc:
        raise RuntimeError("The requested local origin and destination are not connected") from exc

    block_identity = _edge_identity(block_from, block_to)
    primary_identities = {
        _edge_identity(from_node, to_node)
        for from_node, to_node in _path_edges(primary)
    }
    if block_identity not in primary_identities:
        raise RuntimeError("Requested block edge is not on the primary route")

    blocked_attributes = dict(eligible[block_from][block_to])
    eligible.remove_edge(block_from, block_to)
    try:
        alternate = nx.shortest_path(eligible, origin, destination, weight="length")
    except (nx.NetworkXNoPath, nx.NodeNotFound) as exc:
        raise RuntimeError("Blocking the requested edge leaves no alternate walking route") from exc
    finally:
        eligible.add_edge(block_from, block_to, **blocked_attributes)

    primary_length = _path_length(eligible, primary)
    alternate_length = _path_length(eligible, alternate)
    if alternate == primary or alternate_length <= primary_length:
        raise RuntimeError("The selected block does not produce a longer, distinct detour")

    primary_edges = _path_edges(primary)
    alternate_edges = _path_edges(alternate)
    primary_edge_set = {_edge_identity(*edge) for edge in primary_edges}
    alternate_edge_set = {_edge_identity(*edge) for edge in alternate_edges}
    shared_edge_set = primary_edge_set.intersection(alternate_edge_set)
    shared_length = sum(
        float(eligible[from_node][to_node]["length"])
        for from_node, to_node in primary_edges
        if _edge_identity(from_node, to_node) in shared_edge_set
    )
    prefix = _shared_prefix_nodes(primary, alternate)
    suffix = _shared_suffix_nodes(primary, alternate)

    return {
        "eligible_graph": eligible,
        "origin": origin,
        "destination": destination,
        "block_from": block_from,
        "block_to": block_to,
        "primary_path": primary,
        "alternate_path": alternate,
        "primary_length_m": round(primary_length, 3),
        "alternate_length_m": round(alternate_length, 3),
        "detour_delta_m": round(alternate_length - primary_length, 3),
        "detour_ratio": round(alternate_length / primary_length, 6),
        "shared_length_m": round(shared_length, 3),
        "shared_ratio": round(shared_length / primary_length, 6),
        "branch_node": prefix[-1],
        "merge_node": suffix[0],
    }


def require_expected_path(
    actual_path: Iterable[Any],
    expected_node_ids: list[str] | None,
    label: str,
) -> None:
    if expected_node_ids is None:
        return
    actual = [str(node) for node in actual_path]
    if actual != expected_node_ids:
        raise RuntimeError(
            f"{label} path changed: expected {expected_node_ids}, got {actual}"
        )


def require_expected_way_ids(
    route: dict[str, Any],
    expected_way_ids: list[str],
) -> None:
    eligible: nx.Graph = route["eligible_graph"]
    actual: set[str] = set()
    for path_name in ("primary_path", "alternate_path"):
        for from_node, to_node in _path_edges(route[path_name]):
            attributes = eligible[from_node][to_node]["source_attributes"]
            actual.update(as_values(attributes.get("osmid")))
    missing = sorted(set(expected_way_ids).difference(actual))
    if missing:
        raise RuntimeError(
            f"Selected reroute paths are missing expected OSM ways {missing}; got {sorted(actual)}"
        )


def _edge_id(from_node: Any, to_node: Any, attributes: dict[str, Any]) -> str:
    node_pair = sorted((str(from_node), str(to_node)))
    osm_ids = sorted(as_values(attributes.get("osmid")))
    identity = f"{node_pair[0]}|{node_pair[1]}|{'-'.join(osm_ids)}"
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:12]
    return f"LOCAL_OSM_{digest}"


def _node_id(node: Any) -> str:
    return f"LOCAL_OSM_NODE_{node}"


def build_reroute_graph_payload(
    graph: nx.MultiGraph,
    *,
    label: str,
    route: dict[str, Any],
    fetched_at: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    eligible: nx.Graph = route["eligible_graph"]
    primary_edges = _path_edges(route["primary_path"])
    alternate_edges = _path_edges(route["alternate_path"])
    primary_set = {_edge_identity(*edge) for edge in primary_edges}
    alternate_set = {_edge_identity(*edge) for edge in alternate_edges}
    ordered_edges: list[tuple[Any, Any]] = []
    seen_edges: set[frozenset[Any]] = set()
    for edge in [*primary_edges, *alternate_edges]:
        identity = _edge_identity(*edge)
        if identity not in seen_edges:
            seen_edges.add(identity)
            ordered_edges.append(edge)

    ordered_nodes = list(dict.fromkeys([*route["primary_path"], *route["alternate_path"]]))
    block_identity = _edge_identity(route["block_from"], route["block_to"])
    edge_ids: dict[frozenset[Any], str] = {}
    edge_features: list[dict[str, Any]] = []

    for from_node, to_node in ordered_edges:
        selected = eligible[from_node][to_node]
        source_attributes = selected["source_attributes"]
        identity = _edge_identity(from_node, to_node)
        edge_id = _edge_id(from_node, to_node, source_attributes)
        edge_ids[identity] = edge_id
        geometry = oriented_geometry(graph, from_node, to_node, source_attributes)
        osm_way_ids = sorted(as_values(source_attributes.get("osmid")))
        role = (
            "shared"
            if identity in primary_set and identity in alternate_set
            else "primary"
            if identity in primary_set
            else "alternate"
        )
        if identity == block_identity:
            role = "primary_block_candidate"
        raw_tags = {
            key: source_attributes.get(key)
            for key in (
                "access",
                "foot",
                "footway",
                "highway",
                "incline",
                "indoor",
                "kerb",
                "name",
                "smoothness",
                "surface",
                "wheelchair",
                "width",
            )
            if source_attributes.get(key) is not None
        }
        edge_features.append(
            {
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [
                        [round(float(lon), 8), round(float(lat), 8)]
                        for lon, lat in geometry.coords
                    ],
                },
                "properties": {
                    "feature_type": "edge",
                    "edge_id": edge_id,
                    "from_node": _node_id(from_node),
                    "to_node": _node_id(to_node),
                    "name": f"{label} {role}",
                    "route_role": role,
                    "length": round(float(selected["length"]), 3),
                    "stairs": False,
                    "slope": None,
                    "width": None,
                    "curb_height": None,
                    "surface": source_attributes.get("surface"),
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
                    "highway": as_values(source_attributes.get("highway")),
                    "raw_osm_tags": raw_tags,
                    "osm_way_ids": osm_way_ids,
                    "osm_source_links": [
                        f"https://www.openstreetmap.org/way/{way_id}"
                        for way_id in osm_way_ids
                        if way_id.isdigit()
                    ],
                    "field_test_only": True,
                    "shared_graph_mutation_allowed": False,
                },
            }
        )

    origin = route["origin"]
    destination = route["destination"]
    branch = route["branch_node"]
    merge = route["merge_node"]
    node_features: list[dict[str, Any]] = []
    for node in ordered_nodes:
        roles = []
        if node == origin:
            roles.append("origin")
        if node == destination:
            roles.append("destination")
        if node == branch:
            roles.append("branch")
        if node == merge:
            roles.append("merge")
        node_features.append(
            {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [
                        round(float(graph.nodes[node]["x"]), 8),
                        round(float(graph.nodes[node]["y"]), 8),
                    ],
                },
                "properties": {
                    "feature_type": "node",
                    "node_id": _node_id(node),
                    "name": f"{label} {'/'.join(roles) if roles else '경로점'}",
                    "node_type": roles or ["route_vertex"],
                    "osm_node_id": str(node),
                    "source": "osm",
                    "confidence": None,
                    "verified": False,
                },
            }
        )

    primary_edge_ids = [edge_ids[_edge_identity(*edge)] for edge in primary_edges]
    alternate_edge_ids = [edge_ids[_edge_identity(*edge)] for edge in alternate_edges]
    block_edge_id = edge_ids[block_identity]
    route_contract = {
        "origin_osm_node": str(origin),
        "destination_osm_node": str(destination),
        "branch_osm_node": str(branch),
        "merge_osm_node": str(merge),
        "block_osm_nodes": [str(route["block_from"]), str(route["block_to"])],
        "primary_osm_nodes": [str(node) for node in route["primary_path"]],
        "alternate_osm_nodes": [str(node) for node in route["alternate_path"]],
        "primary_edge_ids": primary_edge_ids,
        "alternate_edge_ids": alternate_edge_ids,
        "block_edge_id": block_edge_id,
        "primary_length_m": route["primary_length_m"],
        "alternate_length_m": route["alternate_length_m"],
        "detour_delta_m": route["detour_delta_m"],
        "detour_ratio": route["detour_ratio"],
        "shared_length_m": route["shared_length_m"],
        "shared_ratio": route["shared_ratio"],
    }
    payload = {
        "type": "FeatureCollection",
        "metadata": {
            "name": f"NaVi local wheelchair reroute proof graph - {label}",
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
                "OSM 보행로 형상만 사용합니다. 휠체어 통행 가능성은 현장 사전 점검과 "
                "사람 확인 전까지 미확인·미검증이며 공용 Graph에는 반영하지 않습니다."
            ),
            "demo": {
                "origin_node": _node_id(origin),
                "destination_node": _node_id(destination),
                "block_edge": block_edge_id,
            },
            "reroute_proof": route_contract,
        },
        "features": [*node_features, *edge_features],
    }
    return payload, route_contract


def _parse_expected_path(value: str | None) -> list[str] | None:
    if value is None:
        return None
    nodes = [node.strip() for node in value.split(",") if node.strip()]
    if len(nodes) < 2:
        raise argparse.ArgumentTypeError("Expected path must contain at least two node IDs")
    return nodes


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Prepare a local-only OSM branch/detour/merge graph for wheelchair reroute proof testing."
    )
    parser.add_argument("--label", required=True)
    parser.add_argument("--slug", required=True)
    parser.add_argument("--center-lat", type=float, required=True)
    parser.add_argument("--center-lon", type=float, required=True)
    parser.add_argument("--radius-m", type=int, default=250)
    parser.add_argument("--origin-node", required=True)
    parser.add_argument("--destination-node", required=True)
    parser.add_argument("--block-from-node", required=True)
    parser.add_argument("--block-to-node", required=True)
    parser.add_argument("--expected-primary-path")
    parser.add_argument("--expected-alternate-path")
    parser.add_argument("--expected-way-id", action="append", default=[])
    parser.add_argument("--site-reference")
    parser.add_argument("--selection-note")
    parser.add_argument("--as-of")
    parser.add_argument("--source-graphml", type=Path)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    args = parser.parse_args()

    if not 50 <= args.radius_m <= 1_000:
        parser.error("--radius-m must be between 50 and 1000")

    created_at = datetime.now(timezone.utc).isoformat()
    graph = (
        ox.load_graphml(args.source_graphml.resolve())
        if args.source_graphml
        else fetch_graph(
            center_lat=args.center_lat,
            center_lon=args.center_lon,
            radius_m=args.radius_m,
            as_of=args.as_of,
        )
    )
    route = select_reroute_paths(
        graph,
        origin_node_id=args.origin_node,
        destination_node_id=args.destination_node,
        block_from_node_id=args.block_from_node,
        block_to_node_id=args.block_to_node,
    )
    require_expected_path(
        route["primary_path"],
        _parse_expected_path(args.expected_primary_path),
        "Primary",
    )
    require_expected_path(
        route["alternate_path"],
        _parse_expected_path(args.expected_alternate_path),
        "Alternate",
    )
    require_expected_way_ids(route, args.expected_way_id)
    graph_payload, route_contract = build_reroute_graph_payload(
        graph,
        label=args.label,
        route=route,
        fetched_at=created_at,
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
        "dataset_id": f"local-reroute-{args.slug}",
        "label": args.label,
        "created_at": created_at,
        "privacy_classification": "public_landmark",
        "center": {"lat": args.center_lat, "lon": args.center_lon},
        "radius_m": args.radius_m,
        "source": "OpenStreetMap local snapshot",
        "source_url": "https://www.openstreetmap.org/copyright",
        "license": "ODbL",
        "accessibility_status": "unknown",
        "verified": False,
        "field_verified": False,
        "field_test_only": True,
        "shared_graph_mutation_allowed": False,
        "allowed_use": "local_wheelchair_reroute_proof_only",
        "site_reference": args.site_reference,
        "selection_note": args.selection_note,
        "route_contract": route_contract,
        "raw_graph": {
            "path": raw_graph_path.name,
            "sha256": sha256(raw_graph_path),
            "nodes": graph.number_of_nodes(),
            "edges": graph.number_of_edges(),
        },
        "route_graph": {
            "path": route_graph_path.name,
            "sha256": sha256(route_graph_path),
            "nodes": sum(
                feature["properties"].get("feature_type") == "node"
                for feature in graph_payload["features"]
            ),
            "edges": sum(
                feature["properties"].get("feature_type") == "edge"
                for feature in graph_payload["features"]
            ),
        },
    }
    write_json(manifest_path, manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
