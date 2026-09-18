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
import sys
from collections import Counter, defaultdict
from copy import deepcopy
from pathlib import Path
from typing import Any

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
    "evidence_count",
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


def derive_candidates(
    graph: dict[str, Any],
    topographic: dict[str, Any],
    hdmap: dict[str, Any],
    public_crosswalks: dict[str, Any],
    *,
    created_at: str,
    dataset_ids: dict[str, str],
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
                "mapping_status": "unique",
                "mapping_quality": (
                    "cross_source_consensus"
                    if len(source_types) >= 2
                    else "single_source_unique_match"
                ),
                "proposed_changes": proposed,
                "current_values": {
                    key: edge_properties.get(key) for key in proposed
                },
                "evidence_count": len(evidence),
                "source_types": source_types,
                "evidence": evidence,
                "lat": round(float(centroid.y), 8),
                "lon": round(float(centroid.x), 8),
                "created_at": created_at,
            }
        )
    return candidates, dict(sorted(skipped.items()))


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
    proposals = {
        item["edge_id"]: item
        for item in candidates
        if item.get("proposed_changes")
    }
    for feature in simulation.get("features") or []:
        properties = feature.get("properties") or {}
        edge_id = str(properties.get("edge_id") or "")
        candidate = proposals.get(edge_id)
        if candidate is None:
            continue
        properties.update(deepcopy(candidate["proposed_changes"]))
        properties["candidate_simulation_ids"] = [candidate["candidate_id"]]
        properties["candidate_simulation_only"] = True
    simulation.setdefault("metadata", {})["candidate_simulation"] = {
        "created_at": created_at,
        "baseline_graph_sha256": baseline_sha256,
        "applied_candidate_count": len(proposals),
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
    ) -> dict[str, Any]:
        def one(engine: RouteEngine) -> dict[str, Any]:
            try:
                route = (
                    engine.find_accessible_route(request)
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
        after = one(after_engine)
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
        impact = calculate(before_engine, after_engine, request, accessible=True)
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
        "| {edge} | {before} | {after} | {difference} |".format(
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
- 경로 조건 변경 가능 후보: {metrics['metrics']['route_affecting_candidate_count']}개
- 근거 전용 후보: {metrics['metrics']['evidence_only_candidate_count']}개
- 후보 유형: `{json.dumps(counts, ensure_ascii=False, sort_keys=True)}`
- 기준 Graph 변경: `{str(not metrics['safety']['baseline_graph_unchanged']).lower()}`
- candidate Graph 경로 회귀 동일: `{str(metrics['safety']['route_regression_identical']).lower()}`
- 5개 계단 제안 시뮬레이션에서 영향을 받은 후보 Edge OD: {metrics['simulation']['candidate_edge_route_changed_count']}개

## 자동 제안 가능한 필드

수치지형도 계단 객체가 unique 매칭되고 기존 OSM Edge에 `stairs=true`가 없는 5개 Edge에만 `stairs=true`를 제안했습니다. 이 값은 아직 적용되지 않았으며 승인 전에는 wheelchair 경로에서 제외되지 않습니다.

### 후보 적용 시뮬레이션

대표 데모 OD의 일반 경로 1081.9m와 휠체어 경로 1302.5m는 다섯 후보를 적용해도 변하지 않았습니다. 후보 Edge 양 끝점을 각각 시험하면 다음과 같습니다.

| Edge | 적용 전 휠체어 경로 | 후보 적용 후 | 변화 |
|---|---:|---:|---:|
{impact_rows}

이는 실제 계단이라는 확정 결과가 아니라, 후보가 승인될 경우 예상되는 Graph 영향입니다. 특히 두 Edge는 대체 경로가 없어 현장 확인 없이 적용하면 접근 가능한 구역을 잘못 단절할 수 있습니다.

## 근거로만 유지한 객체

- 보도/보행공간: geometry 의미 근거만 기록
- 횡단보도: 위치/교차 근거만 기록
- 정밀도로지도 연석: 연석 존재 근거만 기록하고 높이는 생성하지 않음
- 육교/입체횡단: 구조물 근거만 기록하고 계단 또는 통과 불가로 단정하지 않음

DEM 경사는 90m 해상도 gate 때문에 후보에서 제외했고, 정사영상 geometry 보정은 기준점 RMSE가 없어 제외했습니다. 공공 횡단보도 접근성의 빈 값은 계속 `unknown`입니다.

## 산출물

- `data/processed/evaluation/graph_enrichment/candidate_bundle.json`
- `data/processed/evaluation/graph_enrichment/candidates.csv`
- `data/processed/evaluation/graph_enrichment/route_affecting_candidates.json`
- `data/processed/evaluation/graph_enrichment/anyang_accessibility_graph.candidate.geojson`
- `data/processed/evaluation/graph_enrichment/anyang_accessibility_graph.candidate_simulation.geojson`
- `data/processed/evaluation/graph_enrichment/route_impact_simulation.json`
- `data/processed/evaluation/graph_enrichment/metrics.json`

candidate Graph는 기본 실행 Graph가 아니며 `candidate_enrichments` 주석만 추가합니다. 승인 절차가 생기기 전에는 이 파일을 `NAVI_GRAPH_PATH`로 사용하지 않습니다.

`anyang_accessibility_graph.candidate_simulation.geojson`은 5개 `stairs=true` 제안을 별도 사본에 적용한 영향 시험 전용 파일입니다. 이 파일 역시 실행 Graph나 검증 데이터가 아닙니다.
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
    }
    candidates, skipped = derive_candidates(
        graph,
        topographic,
        hdmap,
        public_crosswalks,
        created_at=timestamp,
        dataset_ids=datasets,
    )
    preview = _preview_graph(
        graph,
        candidates,
        created_at=timestamp,
        baseline_sha256=baseline_sha,
    )
    if _routing_projection(graph) != _routing_projection(preview):
        raise RuntimeError("candidate preview changed one or more routing fields")

    route_affecting = [item for item in candidates if item["proposed_changes"]]
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
        "schema_version": "1.0",
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
            "cross_source_consensus_candidate_count": source_consensus_count,
            "candidate_counts_by_type": dict(sorted(type_counts.items())),
            "candidate_counts_by_priority": dict(sorted(priority_counts.items())),
            "skipped_counts": skipped,
        },
        "excluded_sources": {
            "dem_slope": "rejected_for_edge_update_90m_resolution",
            "orthophoto_geometry": "hold_missing_control_point_rmse",
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
        },
        "policy": {**PROVENANCE_FLAGS, "routing_graph_mutated": False},
    }
    bundle = {
        "schema_version": "1.0",
        "created_at": timestamp,
        "baseline_graph_sha256": baseline_sha,
        "status": "pending",
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
            "evidence_count": item["evidence_count"],
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
