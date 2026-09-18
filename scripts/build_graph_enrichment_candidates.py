"""Build a non-routing graph-enrichment candidate bundle.

This stage promotes deterministic spatial matches into *proposals*, not facts.
The baseline graph is never edited.  A preview copy only attaches a
``candidate_enrichments`` list to matched edges; existing routing fields stay
byte-for-byte equivalent after those annotations are stripped.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
from collections import Counter, defaultdict
from copy import deepcopy
from pathlib import Path
from typing import Any

from affine import Affine
from pyproj import Transformer
from rasterio.transform import rowcol
from shapely.geometry import shape

try:
    from scripts.spatial_evaluation_common import (
        GRAPH_PATH,
        PROVENANCE_FLAGS,
        file_sha256,
        load_json,
        now_iso,
        write_csv,
        write_json,
    )
except ModuleNotFoundError:  # Direct execution from scripts/
    from spatial_evaluation_common import (  # type: ignore[no-redef]
        GRAPH_PATH,
        PROVENANCE_FLAGS,
        file_sha256,
        load_json,
        now_iso,
        write_csv,
        write_json,
    )


EVALUATION_ROOT = Path("data/processed/evaluation")
DEFAULT_OUTPUT_DIR = EVALUATION_ROOT / "graph_enrichment"
REPORT_PATH = Path("docs/graph_enrichment_candidate_report.md")
DEM_CANDIDATE_PATH = EVALUATION_ROOT / "dem" / "edge_slope_candidates.csv"
ORTHOPHOTO_DIR = EVALUATION_ROOT / "orthophoto"
ORTHOPHOTO_MANIFEST_PATH = ORTHOPHOTO_DIR / "qa_evidence_manifest.json"
EXPERIMENTAL_WHEELCHAIR_MAX_SLOPE_PCT = 8.0
ROUTING_FIELDS = (
    "stairs",
    "slope",
    "width",
    "curb_height",
    "surface",
    "elevator_required",
    "elevator_status",
    "blocked",
    "block_reason",
    "wheelchair_accessible",
    "accessibility_status",
    "accessibility_source",
    "verified",
)
CANDIDATE_CSV_FIELDS = (
    "candidate_id",
    "edge_id",
    "type",
    "priority",
    "routing_impact",
    "mapping_quality",
    "candidate_class",
    "simulation_allowed",
    "approval_eligible",
    "evidence_count",
    "visual_evidence_reference_count",
    "source_types",
    "proposed_changes_json",
    "current_values_json",
    "status",
    "verified",
    "graph_update_allowed",
)


def _candidate_id(edge_id: str, candidate_type: str) -> str:
    digest = hashlib.sha256(f"{edge_id}|{candidate_type}".encode("utf-8")).hexdigest()
    return f"GEC-{digest[:16].upper()}"


def _edge_features(graph: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(feature["properties"]["edge_id"]): feature
        for feature in graph.get("features") or []
        if (feature.get("properties") or {}).get("feature_type") == "edge"
    }


def _add_evidence(
    groups: dict[tuple[str, str], dict[str, Any]],
    *,
    edge_id: str,
    candidate_type: str,
    priority: str,
    routing_impact: str,
    proposed_changes: dict[str, Any],
    evidence: dict[str, Any],
) -> None:
    key = (edge_id, candidate_type)
    group = groups.setdefault(
        key,
        {
            "edge_id": edge_id,
            "type": candidate_type,
            "priority": priority,
            "routing_impact": routing_impact,
            "proposed_changes": proposed_changes,
            "evidence": [],
        },
    )
    if group["proposed_changes"] != proposed_changes:
        raise ValueError(f"conflicting proposed changes for {key}")
    group["evidence"].append(evidence)


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _as_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def derive_candidates(
    graph: dict[str, Any],
    topographic: dict[str, Any],
    hdmap: dict[str, Any],
    public_crosswalks: dict[str, Any],
    dem_rows: list[dict[str, Any]] | None = None,
    *,
    created_at: str,
    dataset_ids: dict[str, str],
    experimental_max_slope_pct: float = EXPERIMENTAL_WHEELCHAIR_MAX_SLOPE_PCT,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Derive candidates using only deterministic, pre-declared gates."""

    edges = _edge_features(graph)
    groups: dict[tuple[str, str], dict[str, Any]] = {}
    skipped: Counter[str] = Counter()
    topographic_roles = {
        "pedestrian_area": (
            "pedestrian_area_evidence",
            "low",
            "none_before_review",
            {},
        ),
        "crossing_candidate": (
            "crosswalk_geometry_evidence",
            "medium",
            "none_before_review",
            {},
        ),
        "grade_separated_crossing_candidate": (
            "grade_separated_crossing_evidence",
            "medium",
            "none_before_review",
            {},
        ),
    }
    for feature in topographic.get("features") or []:
        properties = feature.get("properties") or {}
        if properties.get("match_status") != "unique":
            skipped["topographic_not_unique"] += 1
            continue
        edge_id = str(properties.get("best_edge_id") or "")
        if edge_id not in edges:
            skipped["topographic_edge_missing"] += 1
            continue
        role = str(properties.get("evaluation_role") or "")
        if role == "stairs_candidate":
            if bool(edges[edge_id]["properties"].get("stairs")):
                skipped["stairs_already_present"] += 1
                continue
            candidate_type, priority, routing_impact, proposed = (
                "stairs_attribute_candidate",
                "high",
                "wheelchair_edge_exclusion_after_approval",
                {"stairs": True},
            )
        elif role in topographic_roles:
            candidate_type, priority, routing_impact, proposed = topographic_roles[role]
        else:
            skipped["topographic_role_not_promoted"] += 1
            continue
        _add_evidence(
            groups,
            edge_id=edge_id,
            candidate_type=candidate_type,
            priority=priority,
            routing_impact=routing_impact,
            proposed_changes=proposed,
            evidence={
                "source_type": "ngii_topographic_map",
                "source_dataset_id": dataset_ids["topographic"],
                "source_feature_id": properties.get("source_feature_id"),
                "source_feature_code": properties.get("source_feature_code"),
                "evaluation_role": role,
                "mapping_status": "unique",
                "mapping_distance_m": properties.get("best_distance_m"),
                "mapping_score": properties.get("best_score"),
                "source_sheet_id": properties.get("source_sheet_id"),
                "source_year": properties.get("source_year"),
            },
        )

    hd_roles = {
        "sidewalk_polygon": (
            "pedestrian_area_evidence",
            "low",
        ),
        "crosswalk_polygon": (
            "crosswalk_geometry_evidence",
            "medium",
        ),
        "concrete_curb_line": (
            "curb_presence_evidence",
            "low",
        ),
    }
    for feature in hdmap.get("features") or []:
        properties = feature.get("properties") or {}
        if properties.get("graph_mapping_status") != "unique":
            skipped["hdmap_not_unique"] += 1
            continue
        edge_id = str(properties.get("graph_edge_id") or "")
        role = str(properties.get("evaluation_role") or "")
        if edge_id not in edges or role not in hd_roles:
            skipped["hdmap_not_promoted"] += 1
            continue
        candidate_type, priority = hd_roles[role]
        _add_evidence(
            groups,
            edge_id=edge_id,
            candidate_type=candidate_type,
            priority=priority,
            routing_impact="none_before_review",
            proposed_changes={},
            evidence={
                "source_type": "ngii_hdmap",
                "source_dataset_id": dataset_ids["hdmap"],
                "source_feature_id": properties.get("source_feature_id"),
                "source_layer": properties.get("source_layer"),
                "evaluation_role": role,
                "mapping_status": "unique",
                "mapping_distance_m": properties.get("graph_distance_m"),
                "overlap_ratio": properties.get("overlap_ratio"),
                "source_year": properties.get("source_year"),
            },
        )

    for feature in public_crosswalks.get("features") or []:
        properties = feature.get("properties") or {}
        if not (
            properties.get("graph_mapping_status") == "unique"
            and properties.get("hd_match_status") == "matched_near"
        ):
            skipped["public_crosswalk_without_hd_consensus"] += 1
            continue
        edge_id = str(properties.get("graph_edge_id") or "")
        if edge_id not in edges:
            skipped["public_crosswalk_edge_missing"] += 1
            continue
        _add_evidence(
            groups,
            edge_id=edge_id,
            candidate_type="crosswalk_geometry_evidence",
            priority="medium",
            routing_impact="none_before_review",
            proposed_changes={},
            evidence={
                "source_type": "anyang_public_crosswalk_hd_consensus",
                "source_dataset_id": dataset_ids["crosswalk"],
                "source_feature_id": properties.get("public_crosswalk_id"),
                "hd_crosswalk_id": properties.get("hd_crosswalk_id"),
                "hd_distance_m": properties.get("hd_distance_m"),
                "mapping_status": "unique",
                "mapping_distance_m": properties.get("graph_distance_m"),
                "accessibility_values_used": False,
            },
        )

    for row in dem_rows or []:
        edge_id = str(row.get("edge_id") or "")
        if edge_id not in edges:
            skipped["dem_edge_missing"] += 1
            continue
        if str(row.get("quality_flag") or "") != "coarse_context_only":
            skipped["dem_insufficient_resolution"] += 1
            continue
        slope_pct = _as_float(row.get("slope_pct_abs_candidate"))
        if slope_pct is None:
            skipped["dem_slope_missing"] += 1
            continue
        if slope_pct <= experimental_max_slope_pct:
            skipped["dem_below_experimental_threshold"] += 1
            continue
        if edges[edge_id]["properties"].get("slope") is not None:
            skipped["dem_existing_slope_preserved"] += 1
            continue
        _add_evidence(
            groups,
            edge_id=edge_id,
            candidate_type="dem_slope_diagnostic_candidate",
            priority="medium",
            routing_impact="diagnostic_wheelchair_sensitivity_only",
            proposed_changes={"slope": round(slope_pct, 6)},
            evidence={
                "source_type": "ngii_dem",
                "source_dataset_id": dataset_ids["dem"],
                "evaluation_role": "coarse_slope_sensitivity",
                "mapping_status": "edge_sampled",
                "mapping_distance_m": 0.0,
                "slope_pct_abs_candidate": round(slope_pct, 6),
                "slope_pct_signed_candidate": _as_float(
                    row.get("slope_pct_signed_candidate")
                ),
                "dem_resolution_m": _as_float(row.get("dem_resolution_m")),
                "distinct_cell_count": int(row.get("distinct_cell_count") or 0),
                "nearest_bilinear_endpoint_max_diff_m": _as_float(
                    row.get("nearest_bilinear_endpoint_max_diff_m")
                ),
                "quality_flag": "coarse_context_only",
                "hard_constraint_eligible": False,
                "derived": True,
                "verified": False,
                "allowed_use": "route_impact_sensitivity_test_only",
            },
        )

    candidates: list[dict[str, Any]] = []
    for (edge_id, candidate_type), group in sorted(groups.items()):
        edge_feature = edges[edge_id]
        edge_properties = edge_feature["properties"]
        evidence = sorted(
            group["evidence"],
            key=lambda item: (
                str(item.get("source_type")),
                str(item.get("source_feature_id")),
            ),
        )
        source_types = sorted({str(item["source_type"]) for item in evidence})
        centroid = shape(edge_feature["geometry"]).centroid
        proposed = dict(group["proposed_changes"])
        diagnostic_only = candidate_type == "dem_slope_diagnostic_candidate"
        candidate_class = (
            "diagnostic_sensitivity"
            if diagnostic_only
            else "routing_attribute"
            if proposed
            else "evidence_only"
        )
        mapping_quality = (
            "coarse_dem_context"
            if diagnostic_only
            else (
                "cross_source_consensus"
                if len(source_types) >= 2
                else "single_source_unique_match"
            )
        )
        candidates.append(
            {
                "candidate_id": _candidate_id(edge_id, candidate_type),
                "edge_id": edge_id,
                "type": candidate_type,
                "source": "spatial_evaluation_candidate",
                "confidence": None,
                "status": "pending",
                "verified": False,
                "graph_update_allowed": False,
                "requires_human_review": True,
                "priority": group["priority"],
                "routing_impact": group["routing_impact"],
                "mapping_status": "edge_sampled" if diagnostic_only else "unique",
                "mapping_quality": mapping_quality,
                "candidate_class": candidate_class,
                "simulation_allowed": bool(proposed),
                "approval_eligible": not diagnostic_only,
                "quality_flags": (
                    ["coarse_90m_dem", "not_hard_constraint_eligible"]
                    if diagnostic_only
                    else []
                ),
                "proposed_changes": proposed,
                "current_values": {
                    key: edge_properties.get(key) for key in proposed
                },
                "evidence_count": len(evidence),
                "source_types": source_types,
                "evidence": evidence,
                "visual_evidence_refs": [],
                "lat": round(float(centroid.y), 8),
                "lon": round(float(centroid.x), 8),
                "created_at": created_at,
            }
        )
    return candidates, dict(sorted(skipped.items()))


def _build_orthophoto_qa_manifest(
    project_root: Path,
    evaluation_root: Path,
    candidates: list[dict[str, Any]],
    *,
    created_at: str,
    baseline_sha256: str,
) -> dict[str, Any]:
    """Attach provisional image locators without claiming geometry validation."""

    orthophoto_dir = evaluation_root / "orthophoto"
    metrics = load_json(orthophoto_dir / "metrics.json")
    sidecars = [
        load_json(path)
        for path in sorted((orthophoto_dir / "georeferencing").glob("*.json"))
    ]
    if not sidecars:
        raise RuntimeError("orthophoto georeferencing sidecars are required")

    to_5179 = Transformer.from_crs("EPSG:4326", "EPSG:5179", always_xy=True)
    candidate_references: dict[str, list[dict[str, Any]]] = {}
    unreferenced_candidate_ids: list[str] = []
    reference_count = 0
    for candidate in candidates:
        x, y = to_5179.transform(float(candidate["lon"]), float(candidate["lat"]))
        refs: list[dict[str, Any]] = []
        for sidecar in sidecars:
            min_x, min_y, max_x, max_y = [float(value) for value in sidecar["bounds"]]
            if not (min_x <= x <= max_x and min_y <= y <= max_y):
                continue
            affine = Affine.from_gdal(*sidecar["affine_gdal_order"])
            pixel_row, pixel_col = rowcol(affine, x, y)
            sheet_id = str(sidecar["sheet_id"])
            ref = {
                "reference_id": f"ORTHO-{candidate['candidate_id']}-{sheet_id}",
                "source_type": "ngii_orthophoto",
                "source_dataset_id": metrics.get("dataset_id"),
                "sheet_id": sheet_id,
                "raster": sidecar.get("raster"),
                "raster_sha256": sidecar.get("raster_sha256"),
                "georeferencing_sidecar": (
                    orthophoto_dir
                    / "georeferencing"
                    / f"{sheet_id}.json"
                ).relative_to(project_root).as_posix(),
                "pixel_row": int(pixel_row),
                "pixel_col": int(pixel_col),
                "pixel_size_m": sidecar.get("pixel_size_m"),
                "reference_status": "visual_qa_only_provisional_georeferencing",
                "allowed_use": "human_visual_spatial_qa",
                "control_point_count": sidecar.get("control_point_count", 0),
                "control_point_rmse_m": sidecar.get("control_point_rmse_m"),
                "geometry_correction_allowed": False,
                "graph_update_allowed": False,
                "verified": False,
            }
            refs.append(ref)
        refs.sort(key=lambda item: str(item["sheet_id"]))
        candidate["visual_evidence_refs"] = refs
        if refs:
            candidate_references[candidate["candidate_id"]] = refs
            reference_count += len(refs)
        else:
            unreferenced_candidate_ids.append(candidate["candidate_id"])

    graph_coverage = metrics.get("metrics", {}).get("graph_coverage") or {}
    return {
        "schema_version": "1.1",
        "created_at": created_at,
        "status": "visual_qa_only",
        "dataset_id": metrics.get("dataset_id"),
        "baseline_graph_sha256": baseline_sha256,
        "source_manifest": "data/raw/ngii/orthophoto/2025/source_manifest.json",
        "quality_gate": {
            "pixel_size_m_min": metrics.get("metrics", {}).get("pixel_size_m_min"),
            "pixel_size_m_max": metrics.get("metrics", {}).get("pixel_size_m_max"),
            "control_point_count": metrics.get("metrics", {}).get("control_point_count", 0),
            "control_point_rmse_m": metrics.get("metrics", {}).get("control_point_rmse_m"),
            "graph_covered_edge_pct": graph_coverage.get("intersected_edge_pct"),
            "automatic_geometry_correction": "hold",
            "reason": "independent control-point RMSE has not been measured",
        },
        "metrics": {
            "candidate_count": len(candidates),
            "referenced_candidate_count": len(candidate_references),
            "unreferenced_candidate_count": len(unreferenced_candidate_ids),
            "reference_count": reference_count,
            "tile_count": len(sidecars),
        },
        "candidate_references": candidate_references,
        "unreferenced_candidate_ids": unreferenced_candidate_ids,
        "policy": {
            "derived": True,
            "verified": False,
            "graph_update_allowed": False,
            "routing_graph_mutated": False,
            "raw_tiff_mutated": False,
            "allowed_use": "human_visual_spatial_qa_only",
        },
    }


def _preview_graph(
    graph: dict[str, Any],
    candidates: list[dict[str, Any]],
    *,
    created_at: str,
    baseline_sha256: str,
) -> dict[str, Any]:
    preview = deepcopy(graph)
    by_edge: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for candidate in candidates:
        by_edge[candidate["edge_id"]].append(
            {
                "candidate_id": candidate["candidate_id"],
                "type": candidate["type"],
                "priority": candidate["priority"],
                "routing_impact": candidate["routing_impact"],
                "proposed_changes": candidate["proposed_changes"],
                "evidence_count": candidate["evidence_count"],
                "status": "pending",
                "verified": False,
                "graph_update_allowed": False,
            }
        )
    for feature in preview.get("features") or []:
        properties = feature.get("properties") or {}
        edge_id = str(properties.get("edge_id") or "")
        if edge_id in by_edge:
            properties["candidate_enrichments"] = sorted(
                by_edge[edge_id], key=lambda item: item["candidate_id"]
            )
    preview.setdefault("metadata", {})["candidate_overlay"] = {
        "created_at": created_at,
        "baseline_graph_sha256": baseline_sha256,
        "candidate_count": len(candidates),
        "candidate_edge_count": len(by_edge),
        "routing_fields_applied": False,
        "runtime_default_graph": False,
        **PROVENANCE_FLAGS,
    }
    return preview


def _simulation_graph(
    graph: dict[str, Any],
    candidates: list[dict[str, Any]],
    *,
    created_at: str,
    baseline_sha256: str,
) -> dict[str, Any]:
    """Apply proposed fields to an isolated graph used only for impact tests."""

    simulation = deepcopy(graph)
    proposals: dict[str, dict[str, Any]] = {}
    proposal_ids: dict[str, list[str]] = defaultdict(list)
    for item in candidates:
        if not item.get("proposed_changes"):
            continue
        edge_id = str(item["edge_id"])
        edge_changes = proposals.setdefault(edge_id, {})
        for field, value in item["proposed_changes"].items():
            if field in edge_changes and edge_changes[field] != value:
                raise ValueError(f"conflicting {field} proposals for edge {edge_id}")
            edge_changes[field] = deepcopy(value)
        proposal_ids[edge_id].append(str(item["candidate_id"]))
    for feature in simulation.get("features") or []:
        properties = feature.get("properties") or {}
        edge_id = str(properties.get("edge_id") or "")
        changes = proposals.get(edge_id)
        if changes is None:
            continue
        properties.update(deepcopy(changes))
        properties["candidate_simulation_ids"] = sorted(proposal_ids[edge_id])
        properties["candidate_simulation_only"] = True
    simulation.setdefault("metadata", {})["candidate_simulation"] = {
        "created_at": created_at,
        "baseline_graph_sha256": baseline_sha256,
        "applied_candidate_count": sum(len(ids) for ids in proposal_ids.values()),
        "applied_edge_count": len(proposals),
        "runtime_use_allowed": False,
        "shared_graph_updated": False,
        **PROVENANCE_FLAGS,
    }
    return simulation


def _routing_projection(graph: dict[str, Any]) -> dict[str, dict[str, Any]]:
    projection: dict[str, dict[str, Any]] = {}
    for edge_id, feature in _edge_features(graph).items():
        properties = feature["properties"]
        projection[edge_id] = {
            "from_node": properties.get("from_node"),
            "to_node": properties.get("to_node"),
            "length": properties.get("length"),
            "geometry": feature.get("geometry"),
            **{field: properties.get(field) for field in ROUTING_FIELDS},
        }
    return projection


def _route_regression(baseline_path: Path, preview_path: Path) -> dict[str, Any]:
    from app.graph_store import GraphStore
    from app.profiles import ProfileRegistry
    from app.routing import RouteEngine
    from app.schemas import Coordinate, RouteRequest

    baseline_store = GraphStore(baseline_path)
    preview_store = GraphStore(preview_path)
    demo = baseline_store.metadata.get("demo") or {}
    origin_id = str(demo.get("origin_node") or "")
    destination_id = str(demo.get("destination_node") or "")
    origin = baseline_store.get_node(origin_id)
    destination = baseline_store.get_node(destination_id)
    profiles = ProfileRegistry()
    snapshots: dict[str, Any] = {}
    identical = True
    for profile in ("default", "wheelchair"):
        request = RouteRequest(
            origin=Coordinate(lat=origin["lat"], lon=origin["lon"]),
            destination=Coordinate(lat=destination["lat"], lon=destination["lon"]),
            profile=profile,
        )
        before_engine = RouteEngine(baseline_store, profiles)
        after_engine = RouteEngine(preview_store, profiles)
        if profile == "default":
            before = before_engine.find_shortest_route(request)
            after = after_engine.find_shortest_route(request)
        else:
            before = before_engine.find_accessible_route(request)
            after = after_engine.find_accessible_route(request)
        same = before.edge_ids == after.edge_ids and before.distance_m == after.distance_m
        identical = identical and same
        snapshots[profile] = {
            "identical": same,
            "distance_m": before.distance_m,
            "edge_ids": before.edge_ids,
        }
    return {"identical": identical, "profiles": snapshots}


def _route_impact_simulation(
    baseline_path: Path,
    simulation_path: Path,
    route_affecting: list[dict[str, Any]],
) -> dict[str, Any]:
    from app.graph_store import GraphStore
    from app.profiles import ProfileRegistry
    from app.routing import RouteEngine, RouteNotFoundError
    from app.schemas import Coordinate, RouteRequest

    baseline_store = GraphStore(baseline_path)
    simulation_store = GraphStore(simulation_path)
    profiles = ProfileRegistry()

    def calculate(
        before_engine: RouteEngine,
        after_engine: RouteEngine,
        request: RouteRequest,
        *,
        accessible: bool,
        after_overlays: dict[str, dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        def one(
            engine: RouteEngine,
            overlays: dict[str, dict[str, Any]] | None = None,
        ) -> dict[str, Any]:
            try:
                route = (
                    engine.find_accessible_route(
                        request,
                        edge_attribute_overlays=overlays,
                    )
                    if accessible
                    else engine.find_shortest_route(request)
                )
                return {
                    "status": "ok",
                    "distance_m": route.distance_m,
                    "edge_ids": route.edge_ids,
                }
            except RouteNotFoundError as exc:
                return {"status": exc.status, "distance_m": None, "edge_ids": []}

        before = one(before_engine)
        after = one(after_engine, after_overlays)
        return {
            "before": before,
            "after": after,
            "route_changed": before != after,
            "difference_m": (
                round(float(after["distance_m"]) - float(before["distance_m"]), 1)
                if before["distance_m"] is not None and after["distance_m"] is not None
                else None
            ),
        }

    before_engine = RouteEngine(baseline_store, profiles)
    after_engine = RouteEngine(simulation_store, profiles)
    demo = baseline_store.metadata.get("demo") or {}
    demo_origin = baseline_store.get_node(str(demo.get("origin_node") or ""))
    demo_destination = baseline_store.get_node(str(demo.get("destination_node") or ""))
    demo_results: dict[str, Any] = {}
    for profile, accessible in (("default", False), ("wheelchair", True)):
        request = RouteRequest(
            origin=Coordinate(lat=demo_origin["lat"], lon=demo_origin["lon"]),
            destination=Coordinate(
                lat=demo_destination["lat"], lon=demo_destination["lon"]
            ),
            profile=profile,
        )
        demo_results[profile] = calculate(
            before_engine, after_engine, request, accessible=accessible
        )

    edge_results: list[dict[str, Any]] = []
    for candidate in route_affecting:
        edge = baseline_store.get_edge(candidate["edge_id"])
        origin = baseline_store.get_node(str(edge["from_node"]))
        destination = baseline_store.get_node(str(edge["to_node"]))
        request = RouteRequest(
            origin=Coordinate(lat=origin["lat"], lon=origin["lon"]),
            destination=Coordinate(lat=destination["lat"], lon=destination["lon"]),
            profile="wheelchair",
        )
        impact = calculate(
            before_engine,
            before_engine,
            request,
            accessible=True,
            after_overlays={candidate["edge_id"]: candidate["proposed_changes"]},
        )
        impact.update(
            {
                "candidate_id": candidate["candidate_id"],
                "edge_id": candidate["edge_id"],
                "proposed_changes": candidate["proposed_changes"],
                "baseline_route_uses_candidate_edge": candidate["edge_id"]
                in impact["before"]["edge_ids"],
            }
        )
        edge_results.append(impact)
    return {
        "demo": demo_results,
        "candidate_edges": edge_results,
        "candidate_edge_route_changed_count": sum(
            bool(item["route_changed"]) for item in edge_results
        ),
        "candidate_edge_no_route_count": sum(
            item["after"]["status"] == "no_accessible_route" for item in edge_results
        ),
    }


def _report(metrics: dict[str, Any]) -> str:
    counts = metrics["metrics"]["candidate_counts_by_type"]
    impact_rows = "\n".join(
        "| {candidate} | {kind} | {edge} | {before} | {after} | {difference} |".format(
            candidate=item["candidate_id"],
            kind=(
                "DEM 경사 진단"
                if "slope" in item["proposed_changes"]
                else "계단 제안"
            ),
            edge=item["edge_id"],
            before=(
                f"{item['before']['distance_m']}m"
                if item["before"]["distance_m"] is not None
                else item["before"]["status"]
            ),
            after=(
                f"{item['after']['distance_m']}m"
                if item["after"]["distance_m"] is not None
                else item["after"]["status"]
            ),
            difference=(
                f"+{item['difference_m']}m"
                if item["difference_m"] is not None
                else "경로 없음"
            ),
        )
        for item in metrics["simulation"]["candidate_edges"]
    )
    return f"""# NaVi Graph 반영 후보 결과

생성 시각: `{metrics['created_at']}`

## 결론

현재 자동평가만으로 공유 Graph에 확정 반영한 값은 없습니다. 대신 기존 routing 필드를 유지한 candidate Graph 사본과 Edge별 반영 제안을 생성했습니다.

- 전체 후보: {metrics['metrics']['candidate_count']}개 / {metrics['metrics']['candidate_edge_count']}개 Edge
- 경로 영향 시뮬레이션 후보: {metrics['metrics']['route_affecting_candidate_count']}개
- 이 중 90m DEM 경사 민감도 진단: {metrics['metrics']['diagnostic_candidate_count']}개 (`approval_eligible=false`)
- 근거 전용 후보: {metrics['metrics']['evidence_only_candidate_count']}개
- 정사영상 QA 참조가 연결된 후보: {metrics['metrics']['orthophoto_referenced_candidate_count']}개
- 후보 유형: `{json.dumps(counts, ensure_ascii=False, sort_keys=True)}`
- 기준 Graph 변경: `{str(not metrics['safety']['baseline_graph_unchanged']).lower()}`
- candidate Graph 경로 회귀 동일: `{str(metrics['safety']['route_regression_identical']).lower()}`
- 국소 Edge OD에서 경로가 달라진 시뮬레이션: {metrics['simulation']['candidate_edge_route_changed_count']}개

## 후보 유형과 사용 경계

- 수치지형도 계단 객체 5건은 `stairs=true` 제안이며 사람 검토 전에는 반영되지 않습니다.
- DEM 12건은 `slope` 값을 가정해 경로 민감도만 계산합니다. 90m 격자이므로 현장 보도 종단경사로 승인하거나 Hard Constraint에 자동 반영할 수 없습니다.
- 보행공간·횡단시설·연석 230건은 위치/존재 근거이며 Routing 속성을 만들지 않습니다.
- 모든 후보는 `pending`, `verified=false`, `graph_update_allowed=false`입니다.

### 후보 적용 시뮬레이션

각 후보 Edge의 양 끝점을 출발·도착으로 두고 후보 하나만 요청 한정 overlay로 적용했습니다. 아래 결과는 후보가 사실이라는 판정이 아니라 영향 크기를 보는 진단입니다.

| 후보 ID | 유형 | Edge | 적용 전 휠체어 경로 | 후보 적용 후 | 변화 |
|---|---|---|---:|---:|---:|
{impact_rows}

`no_accessible_route` 결과가 다수이므로, 특히 자동 반영하면 접근 가능한 구역을 잘못 단절할 위험이 큽니다. DEM 행은 승인 대상조차 아니며 더 정밀한 고도자료 또는 현장 측정의 우선순위를 정하는 데만 사용합니다.

## 근거로만 유지한 객체

- 보도/보행공간: geometry 의미 근거만 기록
- 횡단보도: 위치/교차 근거만 기록
- 정밀도로지도 연석: 연석 존재 근거만 기록하고 높이는 생성하지 않음
- 육교/입체횡단: 구조물 근거만 기록하고 계단 또는 통과 불가로 단정하지 않음

## 정사영상 QA 참조

25cm 정사영상의 임시 도엽 affine을 이용해 후보별 `sheet_id`, `pixel_row`, `pixel_col` 참조를 만들었습니다. 전 후보가 적어도 한 도엽에 연결됐지만 독립 기준점 RMSE는 `null`입니다. 따라서 이미지는 사람의 시각 QA 위치 찾기에만 쓰고 geometry 자동 보정이나 Graph 반영에는 쓰지 않습니다.

## 산출물

- `data/processed/evaluation/graph_enrichment/candidate_bundle.json`
- `data/processed/evaluation/graph_enrichment/candidates.csv`
- `data/processed/evaluation/graph_enrichment/route_affecting_candidates.json`
- `data/processed/evaluation/graph_enrichment/anyang_accessibility_graph.candidate.geojson`
- `data/processed/evaluation/graph_enrichment/anyang_accessibility_graph.candidate_simulation.geojson`
- `data/processed/evaluation/graph_enrichment/route_impact_simulation.json`
- `data/processed/evaluation/graph_enrichment/metrics.json`
- `data/processed/evaluation/orthophoto/qa_evidence_manifest.json`

candidate Graph는 기본 실행 Graph가 아니며 `candidate_enrichments` 주석만 추가합니다. 승인 절차가 생기기 전에는 이 파일을 `NAVI_GRAPH_PATH`로 사용하지 않습니다.

`anyang_accessibility_graph.candidate_simulation.geojson`은 계단 5건과 DEM 진단 12건을 별도 사본에 적용한 영향 시험 전용 파일입니다. 이 파일 역시 실행 Graph나 검증 데이터가 아닙니다.
"""


def run_graph_enrichment_candidates(
    project_root: Path,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    *,
    created_at: str | None = None,
) -> dict[str, Any]:
    project_root = project_root.resolve()
    output_dir = output_dir if output_dir.is_absolute() else project_root / output_dir
    timestamp = created_at or now_iso()
    baseline_path = project_root / GRAPH_PATH
    baseline_sha = file_sha256(baseline_path)
    graph = load_json(baseline_path)
    evaluation_root = project_root / EVALUATION_ROOT
    evaluation_summary = load_json(evaluation_root / "evaluation_summary.json")
    expected_sha = str(evaluation_summary.get("graph", {}).get("after_sha256") or "")
    if expected_sha != baseline_sha:
        raise RuntimeError("evaluation results do not match the current baseline graph SHA-256")

    topographic = load_json(evaluation_root / "topographic_map" / "matches.geojson")
    hdmap = load_json(evaluation_root / "cross_sources" / "hdmap_graph_candidates.geojson")
    public_crosswalks = load_json(
        evaluation_root / "cross_sources" / "crosswalk_correspondence.geojson"
    )
    dem_rows = _read_csv_rows(project_root / DEM_CANDIDATE_PATH)
    datasets = {
        "topographic": str(
            evaluation_summary["results"]["topographic_map"].get("dataset_id")
        ),
        "hdmap": str(
            evaluation_summary["results"]["cross_sources"]["dataset_ids"][0]
        ),
        "crosswalk": str(
            evaluation_summary["results"]["cross_sources"]["dataset_ids"][1]
        ),
        "dem": str(evaluation_summary["results"]["dem"].get("dataset_id")),
    }
    candidates, skipped = derive_candidates(
        graph,
        topographic,
        hdmap,
        public_crosswalks,
        dem_rows,
        created_at=timestamp,
        dataset_ids=datasets,
    )
    orthophoto_manifest = _build_orthophoto_qa_manifest(
        project_root,
        evaluation_root,
        candidates,
        created_at=timestamp,
        baseline_sha256=baseline_sha,
    )
    write_json(project_root / ORTHOPHOTO_MANIFEST_PATH, orthophoto_manifest)
    preview = _preview_graph(
        graph,
        candidates,
        created_at=timestamp,
        baseline_sha256=baseline_sha,
    )
    if _routing_projection(graph) != _routing_projection(preview):
        raise RuntimeError("candidate preview changed one or more routing fields")

    route_affecting = [item for item in candidates if item["proposed_changes"]]
    diagnostics = [
        item for item in candidates if item["candidate_class"] == "diagnostic_sensitivity"
    ]
    approval_eligible = [item for item in candidates if item["approval_eligible"]]
    simulation = _simulation_graph(
        graph,
        route_affecting,
        created_at=timestamp,
        baseline_sha256=baseline_sha,
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    preview_path = output_dir / "anyang_accessibility_graph.candidate.geojson"
    simulation_path = (
        output_dir / "anyang_accessibility_graph.candidate_simulation.geojson"
    )
    write_json(preview_path, preview)
    write_json(simulation_path, simulation)
    route_regression = _route_regression(baseline_path, preview_path)
    if not route_regression["identical"]:
        raise RuntimeError("candidate annotations changed the demo route")
    if file_sha256(baseline_path) != baseline_sha:
        raise RuntimeError("baseline graph changed while building candidates")

    route_simulation = _route_impact_simulation(
        baseline_path, simulation_path, route_affecting
    )
    type_counts = Counter(str(item["type"]) for item in candidates)
    priority_counts = Counter(str(item["priority"]) for item in candidates)
    source_consensus_count = sum(
        item["mapping_quality"] == "cross_source_consensus" for item in candidates
    )
    metrics = {
        "schema_version": "1.1",
        "created_at": timestamp,
        "status": "candidate_bundle_ready",
        "baseline_graph": {
            "path": GRAPH_PATH.as_posix(),
            "sha256": baseline_sha,
            "edge_count": len(_edge_features(graph)),
        },
        "metrics": {
            "candidate_count": len(candidates),
            "candidate_edge_count": len({item["edge_id"] for item in candidates}),
            "route_affecting_candidate_count": len(route_affecting),
            "evidence_only_candidate_count": len(candidates) - len(route_affecting),
            "diagnostic_candidate_count": len(diagnostics),
            "approval_eligible_candidate_count": len(approval_eligible),
            "orthophoto_referenced_candidate_count": orthophoto_manifest["metrics"][
                "referenced_candidate_count"
            ],
            "cross_source_consensus_candidate_count": source_consensus_count,
            "candidate_counts_by_type": dict(sorted(type_counts.items())),
            "candidate_counts_by_priority": dict(sorted(priority_counts.items())),
            "skipped_counts": skipped,
        },
        "excluded_sources": {
            "dem_slope_graph_update": "rejected_90m_resolution_diagnostic_simulation_only",
            "orthophoto_geometry_correction": "hold_missing_control_point_rmse_visual_reference_only",
            "public_crosswalk_accessibility_nulls": "preserved_unknown",
            "ambiguous_or_unmatched_geometry": "not_promoted",
        },
        "safety": {
            "baseline_graph_unchanged": file_sha256(baseline_path) == baseline_sha,
            "routing_field_projection_identical": True,
            "route_regression_identical": route_regression["identical"],
            "route_regression": route_regression,
            "candidate_preview_sha256": file_sha256(preview_path),
            "candidate_simulation_sha256": file_sha256(simulation_path),
        },
        "simulation": route_simulation,
        "decision": {
            "shared_graph_updated": False,
            "candidate_preview_is_runtime_default": False,
            "human_review_required_before_apply": True,
            "dem_diagnostic_candidates_approval_eligible": False,
            "orthophoto_geometry_correction_allowed": False,
        },
        "policy": {**PROVENANCE_FLAGS, "routing_graph_mutated": False},
    }
    bundle = {
        "schema_version": "1.1",
        "created_at": timestamp,
        "baseline_graph_sha256": baseline_sha,
        "status": "pending",
        "evidence_manifests": {
            "orthophoto_qa": ORTHOPHOTO_MANIFEST_PATH.as_posix(),
        },
        **PROVENANCE_FLAGS,
        "candidates": candidates,
    }
    write_json(output_dir / "candidate_bundle.json", bundle)
    write_json(output_dir / "route_affecting_candidates.json", route_affecting)
    write_json(output_dir / "route_impact_simulation.json", route_simulation)
    rows = [
        {
            "candidate_id": item["candidate_id"],
            "edge_id": item["edge_id"],
            "type": item["type"],
            "priority": item["priority"],
            "routing_impact": item["routing_impact"],
            "mapping_quality": item["mapping_quality"],
            "candidate_class": item["candidate_class"],
            "simulation_allowed": item["simulation_allowed"],
            "approval_eligible": item["approval_eligible"],
            "evidence_count": item["evidence_count"],
            "visual_evidence_reference_count": len(item["visual_evidence_refs"]),
            "source_types": "|".join(item["source_types"]),
            "proposed_changes_json": json.dumps(
                item["proposed_changes"], ensure_ascii=False, sort_keys=True
            ),
            "current_values_json": json.dumps(
                item["current_values"], ensure_ascii=False, sort_keys=True
            ),
            "status": item["status"],
            "verified": item["verified"],
            "graph_update_allowed": item["graph_update_allowed"],
        }
        for item in candidates
    ]
    write_csv(output_dir / "candidates.csv", rows, CANDIDATE_CSV_FIELDS)
    write_json(output_dir / "metrics.json", metrics)
    report_path = project_root / REPORT_PATH
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(_report(metrics), encoding="utf-8")
    return metrics


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build candidate-only Graph enrichments without mutating routing fields."
    )
    parser.add_argument(
        "--project-root", type=Path, default=Path(__file__).resolve().parents[1]
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--created-at")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = run_graph_enrichment_candidates(
            args.project_root, args.output_dir, created_at=args.created_at
        )
    except Exception as exc:  # noqa: BLE001
        print(f"Graph enrichment candidate build failed: {exc}", file=sys.stderr)
        return 2
    values = result["metrics"]
    print(
        "Graph enrichment candidates: "
        f"status={result['status']} candidates={values['candidate_count']} "
        f"route_affecting={values['route_affecting_candidate_count']} "
        f"graph_unchanged={result['safety']['baseline_graph_unchanged']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
