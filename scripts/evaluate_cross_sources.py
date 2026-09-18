"""Cross-check the HD map, public crosswalk points, and baseline graph.

HD-map objects remain geometry/evidence candidates.  In particular, a curb
line is never interpreted as curb height or wheelchair passability, and no
candidate produced here can mutate the shared graph.
"""

from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Callable

from shapely import STRtree, force_2d, make_valid
from shapely.geometry import Point, box, shape
from shapely.ops import unary_union

try:
    from scripts.spatial_evaluation_common import (
        EdgeMatcher,
        PROVENANCE_FLAGS,
        feature_collection,
        geometry_feature,
        load_graph_edges,
        load_json,
        now_iso,
        transformed,
        write_json,
    )
except ModuleNotFoundError:  # Direct execution from scripts/
    from spatial_evaluation_common import (  # type: ignore[no-redef]
        EdgeMatcher,
        PROVENANCE_FLAGS,
        feature_collection,
        geometry_feature,
        load_graph_edges,
        load_json,
        now_iso,
        transformed,
        write_json,
    )


HD_DIR = Path("data/raw/ngii/precision_road_map/2023/gyeonggi_anyang_pilot")
CROSSWALK_DIR = Path("data/raw/anyang/crosswalks/2026")
DEFAULT_OUTPUT_DIR = Path("data/processed/evaluation/cross_sources")
HD_LAYERS = (
    {
        "filename": "v_hdm2023_a4_subsidiarysection.geojson",
        "role": "sidewalk_polygon",
        "predicate": lambda properties: _decode_legacy_name(properties.get("name")) == "보도",
        "official_filter": "A4 name decoded as 보도",
    },
    {
        "filename": "v_hdm2023_b3_surfacemark.geojson",
        "role": "crosswalk_polygon",
        "predicate": lambda properties: str(properties.get("kind")) == "5321",
        "official_filter": "B3 kind=5321",
    },
    {
        "filename": "v_hdm2023_c3_vehicleprotectionsafety.geojson",
        "role": "concrete_curb_line",
        "predicate": lambda properties: str(properties.get("type")) == "4",
        "official_filter": "C3 type=4",
    },
)


def _decode_legacy_name(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    try:
        return value.encode("latin1").decode("cp949")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return value


def _read_crosswalks(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {
            "관리번호",
            "위도",
            "경도",
            "횡단보도폭",
            "횡단보도길이",
            "보도턱낮춤여부",
            "점자블록유무",
        }
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"crosswalk CSV columns are missing: {sorted(missing)}")
        for raw in reader:
            try:
                point = Point(float(raw["경도"]), float(raw["위도"]))
            except (TypeError, ValueError):
                continue
            rows.append(
                {
                    "id": str(raw["관리번호"]).strip(),
                    "point_wgs84": point,
                    "width_source_m": _float_or_none(raw.get("횡단보도폭")),
                    "length_source_m": _float_or_none(raw.get("횡단보도길이")),
                    "curb_lowering_source_value": (raw.get("보도턱낮춤여부") or "").strip() or None,
                    "tactile_block_source_value": (raw.get("점자블록유무") or "").strip() or None,
                }
            )
    return rows


def _float_or_none(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _load_hd_layer(
    path: Path,
    predicate: Callable[[dict[str, Any]], bool],
    context_100m: Any,
) -> tuple[list[dict[str, Any]], int]:
    data = load_json(path)
    selected: list[dict[str, Any]] = []
    source_count = 0
    for raw in data.get("features") or []:
        properties = dict(raw.get("properties") or {})
        if not predicate(properties):
            continue
        source_count += 1
        geometry_wgs84 = force_2d(shape(raw.get("geometry")))
        if not geometry_wgs84.is_valid:
            geometry_wgs84 = make_valid(geometry_wgs84)
        if geometry_wgs84.is_empty:
            continue
        geometry_5179 = transformed(geometry_wgs84, "EPSG:4326", "EPSG:5179")
        if not geometry_5179.intersects(context_100m):
            continue
        selected.append(
            {
                "properties": properties,
                "geometry_wgs84": geometry_wgs84,
                "geometry_5179": geometry_5179,
            }
        )
    return selected, source_count


def _nearest_hd_crosswalk(
    point_5179: Any,
    geometries: list[Any],
    ids: list[str],
    tree: STRtree | None,
    *,
    max_distance_m: float = 50.0,
) -> dict[str, Any]:
    if tree is None:
        return {"status": "unmatched", "id": None, "distance_m": None}
    candidates: list[tuple[float, str]] = []
    for raw_index in tree.query(point_5179.buffer(max_distance_m)):
        index = int(raw_index)
        distance = float(point_5179.distance(geometries[index]))
        if distance <= max_distance_m:
            candidates.append((distance, ids[index]))
    candidates.sort(key=lambda item: (round(item[0], 9), item[1]))
    if not candidates:
        return {"status": "unmatched", "id": None, "distance_m": None}
    distance, identifier = candidates[0]
    return {
        "status": "matched_near" if distance <= 20.0 else "nearby_review",
        "id": identifier,
        "distance_m": round(distance, 3),
    }


def run_cross_source_evaluation(
    project_root: Path,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    *,
    created_at: str | None = None,
) -> dict[str, Any]:
    project_root = project_root.resolve()
    output_dir = output_dir if output_dir.is_absolute() else project_root / output_dir
    timestamp = created_at or now_iso()
    edges, graph = load_graph_edges(project_root)
    matcher = EdgeMatcher(edges)
    context_100m = unary_union([edge.geometry_5179 for edge in edges]).buffer(100.0)
    hd_manifest = load_json(project_root / HD_DIR / "source_manifest.json")
    source_bbox = box(*(hd_manifest.get("source_bbox_epsg5179") or []))
    if source_bbox.is_empty:
        raise ValueError("HD-map source footprint is missing")

    hd_features: list[dict[str, Any]] = []
    selected_by_role: dict[str, list[dict[str, Any]]] = {}
    source_counts: dict[str, int] = {}
    mapping_counts: dict[str, Counter[str]] = {}
    for layer in HD_LAYERS:
        role = str(layer["role"])
        selected, source_count = _load_hd_layer(
            project_root / HD_DIR / str(layer["filename"]),
            layer["predicate"],
            context_100m,
        )
        selected_by_role[role] = selected
        source_counts[role] = source_count
        counts: Counter[str] = Counter()
        for item in selected:
            properties = item["properties"]
            source_id = str(properties.get("id") or properties.get("gid") or "")
            edge_match = matcher.match(item["geometry_5179"])
            counts[edge_match["mapping_status"]] += 1
            hd_features.append(
                geometry_feature(
                    transformed(item["geometry_5179"], "EPSG:5179", "EPSG:4326"),
                    {
                        "review_id": f"hd-{role}-{source_id}",
                        "candidate_type": f"hdmap_{role}",
                        "evaluation_role": role,
                        "source_feature_id": source_id,
                        "source_layer": layer["filename"],
                        "source_filter": layer["official_filter"],
                        "source_year": hd_manifest.get("source_year"),
                        "graph_mapping_status": edge_match["mapping_status"],
                        "graph_edge_id": edge_match["edge_id"],
                        "candidate_graph_edge_ids": edge_match["candidate_edge_ids"],
                        "graph_distance_m": edge_match["distance_m"],
                        "overlap_ratio": edge_match["overlap_ratio"],
                        "human_review_status": "pending",
                        "passability_claimed": False,
                        "curb_height_claimed": False,
                    },
                )
            )
        mapping_counts[role] = counts

    hd_crosswalks = selected_by_role.get("crosswalk_polygon", [])
    hd_crosswalk_geometries = [item["geometry_5179"] for item in hd_crosswalks]
    hd_crosswalk_ids = [
        str(item["properties"].get("id") or item["properties"].get("gid") or "")
        for item in hd_crosswalks
    ]
    crosswalk_tree = STRtree(hd_crosswalk_geometries) if hd_crosswalk_geometries else None
    crosswalk_files = sorted((project_root / CROSSWALK_DIR).glob("*.csv"))
    if len(crosswalk_files) != 1:
        raise RuntimeError("exactly one Anyang crosswalk CSV is required")
    correspondence_features: list[dict[str, Any]] = []
    correspondence_counts: Counter[str] = Counter()
    unknown_accessibility_count = 0
    for public in _read_crosswalks(crosswalk_files[0]):
        point_5179 = transformed(public["point_wgs84"], "EPSG:4326", "EPSG:5179")
        if not context_100m.covers(point_5179):
            continue
        edge_match = matcher.match(point_5179)
        if not source_bbox.covers(point_5179):
            correspondence = {"status": "outside_hd_coverage", "id": None, "distance_m": None}
        else:
            correspondence = _nearest_hd_crosswalk(
                point_5179,
                hd_crosswalk_geometries,
                hd_crosswalk_ids,
                crosswalk_tree,
            )
        correspondence_counts[correspondence["status"]] += 1
        if public["curb_lowering_source_value"] is None or public["tactile_block_source_value"] is None:
            unknown_accessibility_count += 1
        correspondence_features.append(
            geometry_feature(
                public["point_wgs84"],
                {
                    "review_id": f"public-crosswalk-{public['id']}",
                    "candidate_type": "public_to_hd_crosswalk_correspondence",
                    "public_crosswalk_id": public["id"],
                    "hd_coverage_status": "inside" if source_bbox.covers(point_5179) else "outside",
                    "hd_match_status": correspondence["status"],
                    "hd_crosswalk_id": correspondence["id"],
                    "hd_distance_m": correspondence["distance_m"],
                    "graph_mapping_status": edge_match["mapping_status"],
                    "graph_edge_id": edge_match["edge_id"],
                    "candidate_graph_edge_ids": edge_match["candidate_edge_ids"],
                    "graph_distance_m": edge_match["distance_m"],
                    "crosswalk_width_source_m": public["width_source_m"],
                    "crosswalk_length_source_m": public["length_source_m"],
                    "curb_lowering_source_value": public["curb_lowering_source_value"],
                    "tactile_block_source_value": public["tactile_block_source_value"],
                    "human_review_status": "pending",
                    "passability_claimed": False,
                },
            )
        )

    checks = [
        {
            "code": "cross_source_eval.hd_semantics",
            "status": "pass",
            "message": "Only explicit HD-map layer codes are selected: A4 sidewalk, B3 kind 5321 crosswalk, and C3 type 4 concrete curb.",
        },
        {
            "code": "cross_source_eval.partial_coverage",
            "status": "warning",
            "message": "The 2023 pilot HD map covers only part of the representative corridor; outside-coverage points are not treated as missing objects.",
            "evidence": dict(sorted(correspondence_counts.items())),
        },
        {
            "code": "cross_source_eval.accessibility_unknowns",
            "status": "warning" if unknown_accessibility_count else "pass",
            "message": "Blank curb-lowering or tactile-block fields remain unknown and are not converted to false.",
            "evidence": {"rows_with_unknown_accessibility": unknown_accessibility_count},
        },
        {
            "code": "cross_source_eval.graph_safety_boundary",
            "status": "pass",
            "message": "All correspondences require human review and are ineligible for automatic graph mutation.",
        },
    ]
    metrics = {
        "schema_version": "1.0",
        "created_at": timestamp,
        "status": "warning",
        "dataset_ids": [
            hd_manifest.get("dataset_id"),
            load_json(project_root / CROSSWALK_DIR / "source_manifest.json").get("dataset_id"),
        ],
        "graph": graph,
        "metrics": {
            "hd_source_feature_counts": source_counts,
            "hd_context_feature_counts": {
                role: len(values) for role, values in selected_by_role.items()
            },
            "hd_graph_mapping_counts": {
                role: dict(sorted(counts.items())) for role, counts in mapping_counts.items()
            },
            "public_crosswalk_context_count": len(correspondence_features),
            "public_to_hd_correspondence_counts": dict(sorted(correspondence_counts.items())),
            "rows_with_unknown_accessibility_count": unknown_accessibility_count,
        },
        "decision": {
            "hd_sidewalk_and_crosswalk_geometry": "partial_accept_for_qa",
            "hd_curb": "context_only_no_height_or_passability",
            "public_crosswalk_points": "partial_accept_for_location_qa",
            "automatic_graph_update": "reject",
        },
        "checks": checks,
        "policy": {**PROVENANCE_FLAGS, "routing_graph_mutated": False},
    }
    write_json(
        output_dir / "hdmap_graph_candidates.geojson",
        feature_collection(
            hd_features,
            created_at=timestamp,
            source_graph_sha256=graph["graph_sha256"],
            metadata={"purpose": "hdmap_to_graph_human_review_candidates"},
        ),
    )
    write_json(
        output_dir / "crosswalk_correspondence.geojson",
        feature_collection(
            correspondence_features,
            created_at=timestamp,
            source_graph_sha256=graph["graph_sha256"],
            metadata={"purpose": "public_crosswalk_to_hdmap_human_review"},
        ),
    )
    write_json(output_dir / "metrics.json", metrics)
    return metrics


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Cross-check HD-map and crosswalk sources.")
    parser.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--created-at")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = run_cross_source_evaluation(
            args.project_root, args.output_dir, created_at=args.created_at
        )
    except Exception as exc:  # noqa: BLE001
        print(f"Cross-source evaluation failed: {exc}", file=sys.stderr)
        return 2
    metrics = result["metrics"]
    print(
        "Cross-source evaluation: "
        f"status={result['status']} hd_candidates="
        f"{sum(metrics['hd_context_feature_counts'].values())} "
        f"public_crosswalks={metrics['public_crosswalk_context_count']}"
    )
    return 1 if result["status"] == "fail" else 0


if __name__ == "__main__":
    raise SystemExit(main())
