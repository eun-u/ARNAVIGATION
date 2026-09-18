"""Build report-ready tables and figures from the current NaVi data.

The package is analytical only. It never mutates source data, the shared
routing graph, review decisions, or candidate approval state. All spatial
matches, priority scores, and route effects remain derived/unverified until a
human review explicitly approves them.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from typing import Any, Iterable

import networkx as nx


ROOT = Path(__file__).resolve().parents[1]
GRAPH_PATH = ROOT / "data" / "processed" / "anyang_accessibility_graph.geojson"
EVAL_DIR = ROOT / "data" / "processed" / "evaluation"
PACKAGE_DIR = ROOT / "docs" / "ONWAY_안양_대표회랑_MVP_데이터패키지_20260915"
OUTPUT_DIR = ROOT / "artifacts" / "report-analysis-20260918"
REPORT_PATH = ROOT / "docs" / "report_ready_data_analysis_20260918.md"
ANALYSIS_YEAR = 2026

COLORS = {
    "ink": "#172033",
    "muted": "#667085",
    "grid": "#DDE3EA",
    "pale": "#EEF2F6",
    "blue": "#2F6BFF",
    "teal": "#159D9A",
    "amber": "#E9A23B",
    "coral": "#D95D4F",
    "violet": "#7A5AF8",
    "green": "#348A5B",
    "white": "#FFFFFF",
}


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def number(value: Any) -> float | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def pct(numerator: float, denominator: float, digits: int = 2) -> float:
    return round(100.0 * numerator / denominator, digits) if denominator else 0.0


def percentile(values: Iterable[float], quantile: float) -> float | None:
    ordered = sorted(float(value) for value in values if math.isfinite(float(value)))
    if not ordered:
        return None
    position = (len(ordered) - 1) * quantile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] * (1 - fraction) + ordered[upper] * fraction


def svg_text(
    x: float,
    y: float,
    value: Any,
    *,
    size: int = 22,
    weight: int = 400,
    fill: str | None = None,
    anchor: str = "start",
) -> str:
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" '
        f'font-weight="{weight}" fill="{fill or COLORS["ink"]}" '
        f'text-anchor="{anchor}">{escape(str(value))}</text>'
    )


def svg_document(
    title: str,
    subtitle: str,
    body: list[str],
    *,
    height: int,
    source: str = "ARNAVIGATION 데이터 분석, 2026-09-18",
) -> str:
    width = 1200
    header = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#FFFFFF"/>',
        '<style>text { font-family: Pretendard, "Noto Sans KR", "Malgun Gothic", Arial, sans-serif; }</style>',
        svg_text(64, 64, title, size=32, weight=700),
        svg_text(64, 100, subtitle, size=18, fill=COLORS["muted"]),
    ]
    footer = [
        svg_text(64, height - 34, source, size=15, fill=COLORS["muted"]),
        "</svg>",
    ]
    return "\n".join(header + body + footer) + "\n"


def write_100pct_stacked_chart(
    path: Path,
    *,
    title: str,
    subtitle: str,
    rows: list[tuple[str, list[tuple[str, float, str]]]],
    legend: list[tuple[str, str]],
    source: str = "ARNAVIGATION 데이터 분석, 2026-09-18",
) -> None:
    height = 245 + 90 * len(rows)
    x0, width = 300.0, 820.0
    body: list[str] = []
    for tick in (0, 25, 50, 75, 100):
        x = x0 + width * tick / 100
        body.append(f'<line x1="{x:.1f}" y1="135" x2="{x:.1f}" y2="{height - 95}" stroke="{COLORS["grid"]}" stroke-width="1"/>')
        body.append(svg_text(x, 128, f"{tick}%", size=15, fill=COLORS["muted"], anchor="middle"))
    for index, (label, segments) in enumerate(rows):
        y = 165 + index * 90
        body.append(svg_text(64, y + 30, label, size=21, weight=600))
        cursor = x0
        for segment_label, value, color in segments:
            segment_width = width * value / 100
            body.append(f'<rect x="{cursor:.1f}" y="{y:.1f}" width="{segment_width:.1f}" height="42" rx="4" fill="{color}"/>')
            if segment_width >= 72:
                body.append(svg_text(cursor + segment_width / 2, y + 29, f"{value:.2f}%", size=16, weight=700, fill=COLORS["white"], anchor="middle"))
            elif segment_width > 0:
                body.append(svg_text(cursor + segment_width / 2, y - 8, f"{value:.2f}%", size=14, weight=700, fill=color, anchor="middle"))
            cursor += segment_width
    legend_y = height - 72
    legend_x = 300
    for label, color in legend:
        body.append(f'<rect x="{legend_x}" y="{legend_y - 16}" width="18" height="18" rx="3" fill="{color}"/>')
        body.append(svg_text(legend_x + 28, legend_y, label, size=16, fill=COLORS["muted"]))
        legend_x += 220
    path.write_text(svg_document(title, subtitle, body, height=height, source=source), encoding="utf-8")


def write_horizontal_bar_chart(
    path: Path,
    *,
    title: str,
    subtitle: str,
    rows: list[tuple[str, float, str, str | None]],
    source: str = "ARNAVIGATION 데이터 분석, 2026-09-18",
) -> None:
    height = 235 + 72 * len(rows)
    x0, width = 340.0, 750.0
    maximum = max((value for _, value, _, _ in rows), default=1)
    scale_max = maximum * 1.12 if maximum else 1
    body: list[str] = []
    for index, (label, value, color, display) in enumerate(rows):
        y = 145 + index * 72
        body.append(svg_text(64, y + 27, label, size=19, weight=600))
        body.append(f'<rect x="{x0}" y="{y}" width="{width}" height="38" rx="5" fill="{COLORS["pale"]}"/>')
        body.append(f'<rect x="{x0}" y="{y}" width="{width * value / scale_max:.1f}" height="38" rx="5" fill="{color}"/>')
        body.append(svg_text(x0 + width * value / scale_max + 12, y + 27, display or f"{value:g}", size=18, weight=700))
    path.write_text(svg_document(title, subtitle, body, height=height, source=source), encoding="utf-8")


def load_graph() -> tuple[dict[str, Any], nx.MultiGraph, dict[str, dict[str, Any]]]:
    data = read_json(GRAPH_PATH)
    graph = nx.MultiGraph()
    edges: dict[str, dict[str, Any]] = {}
    for feature in data["features"]:
        properties = feature.get("properties", {})
        if properties.get("feature_type") == "node":
            graph.add_node(properties["node_id"])
        elif properties.get("feature_type") == "edge":
            edge_id = properties["edge_id"]
            edge = dict(properties)
            edge["length"] = float(properties.get("length") or 0.0)
            edges[edge_id] = edge
            graph.add_edge(
                properties["from_node"],
                properties["to_node"],
                key=edge_id,
                **edge,
            )
    return data, graph, edges


def edge_removal_metric(
    graph: nx.MultiGraph,
    edge: dict[str, Any],
) -> dict[str, Any]:
    edge_id = edge["edge_id"]
    start, end = edge["from_node"], edge["to_node"]
    length = float(edge.get("length") or 0.0)
    graph.remove_edge(start, end, key=edge_id)
    try:
        try:
            alternate = float(nx.shortest_path_length(graph, start, end, weight="length"))
            status = "alternate_route"
        except nx.NetworkXNoPath:
            alternate = None
            status = "disconnected"
    finally:
        graph.add_edge(start, end, key=edge_id, **edge)
    ratio = alternate / length if alternate is not None and length > 0 else None
    return {
        "edge_id": edge_id,
        "from_node": start,
        "to_node": end,
        "original_edge_length_m": round(length, 3),
        "alternative_status": status,
        "alternative_route_length_m": round(alternate, 3) if alternate is not None else None,
        "detour_m": round(alternate - length, 3) if alternate is not None else None,
        "alternative_ratio": round(ratio, 4) if ratio is not None else None,
        "is_bridge_edge": alternate is None,
    }


def source_year(properties: dict[str, Any]) -> int | None:
    explicit = number(properties.get("source_year"))
    if explicit is not None:
        return int(explicit)
    return {
        "public_crosswalk": 2026,
        "dem": 2025,
        "orthophoto": 2025,
        "hdmap": 2023,
    }.get(str(properties.get("review_source")))


def normalized_edge_id(properties: dict[str, Any], edges: dict[str, Any]) -> str | None:
    candidate = (
        properties.get("graph_edge_id")
        or properties.get("best_edge_id")
        or properties.get("edge_id")
    )
    return str(candidate) if candidate in edges else None


def mapping_status(properties: dict[str, Any]) -> str:
    value = properties.get("graph_mapping_status") or properties.get("match_status")
    if value:
        return str(value)
    if properties.get("review_source") == "dem":
        return "insufficient_resolution"
    return "not_linked"


def mapping_distance(properties: dict[str, Any]) -> float | None:
    for key in ("graph_distance_m", "best_distance_m"):
        value = number(properties.get(key))
        if value is not None:
            return value
    return None


def add_unique_evidence(
    evidence: defaultdict[str, set[str]],
    years: defaultdict[str, set[int]],
    *,
    edge_id: str | None,
    source: str,
    year: int,
    edges: dict[str, Any],
) -> None:
    if edge_id and edge_id in edges:
        evidence[edge_id].add(source)
        years[edge_id].add(year)


def build_evidence_index(
    edges: dict[str, Any],
) -> tuple[defaultdict[str, set[str]], defaultdict[str, set[int]]]:
    evidence: defaultdict[str, set[str]] = defaultdict(set)
    years: defaultdict[str, set[int]] = defaultdict(set)

    topographic = read_json(EVAL_DIR / "topographic_map" / "matches.geojson")["features"]
    for feature in topographic:
        props = feature["properties"]
        if props.get("match_status") == "unique":
            add_unique_evidence(
                evidence,
                years,
                edge_id=props.get("best_edge_id"),
                source="수치지형도",
                year=int(props.get("source_year") or 2025),
                edges=edges,
            )

    public = read_json(EVAL_DIR / "cross_sources" / "crosswalk_correspondence.geojson")["features"]
    for feature in public:
        props = feature["properties"]
        if props.get("graph_mapping_status") == "unique":
            add_unique_evidence(
                evidence,
                years,
                edge_id=props.get("graph_edge_id"),
                source="공공 횡단보도",
                year=2026,
                edges=edges,
            )

    hdmap = read_json(EVAL_DIR / "cross_sources" / "hdmap_graph_candidates.geojson")["features"]
    for feature in hdmap:
        props = feature["properties"]
        if props.get("graph_mapping_status") == "unique":
            add_unique_evidence(
                evidence,
                years,
                edge_id=props.get("graph_edge_id"),
                source="HD Map",
                year=int(props.get("source_year") or 2023),
                edges=edges,
            )

    orthophoto = read_json(EVAL_DIR / "orthophoto" / "geometry_review_candidates.geojson")["features"]
    for feature in orthophoto:
        props = feature["properties"]
        if props.get("graph_mapping_status") == "unique":
            add_unique_evidence(
                evidence,
                years,
                edge_id=props.get("graph_edge_id"),
                source="정사영상",
                year=2025,
                edges=edges,
            )
    return evidence, years


def analyze() -> tuple[dict[str, Any], dict[str, list[dict[str, Any]]]]:
    graph_sha_before = sha256(GRAPH_PATH)
    graph_data, graph, edges = load_graph()
    simple_graph = nx.Graph(graph)
    articulation_nodes = set(nx.articulation_points(simple_graph))
    edge_metric_cache: dict[str, dict[str, Any]] = {}

    def edge_metric(edge_id: str | None) -> dict[str, Any] | None:
        if not edge_id or edge_id not in edges:
            return None
        if edge_id not in edge_metric_cache:
            metric = edge_removal_metric(graph, edges[edge_id])
            metric["articulation_adjacent"] = (
                metric["from_node"] in articulation_nodes
                or metric["to_node"] in articulation_nodes
            )
            edge_metric_cache[edge_id] = metric
        return edge_metric_cache[edge_id]

    raw_crosswalk_path = next((ROOT / "data" / "raw" / "anyang" / "crosswalks" / "2026").glob("*.csv"))
    raw_crosswalks = read_csv(raw_crosswalk_path)
    missingness: dict[str, dict[str, Any]] = {}
    for label, field in (("보도턱 낮춤", "보도턱낮춤여부"), ("점자블록", "점자블록유무")):
        entered = sum(bool(row.get(field, "").strip()) for row in raw_crosswalks)
        blank = len(raw_crosswalks) - entered
        missingness[label] = {
            "entered": entered,
            "blank": blank,
            "entry_rate_pct": pct(entered, len(raw_crosswalks)),
            "missing_rate_pct": pct(blank, len(raw_crosswalks)),
        }

    topographic_metrics = read_json(EVAL_DIR / "topographic_map" / "metrics.json")
    topographic_features = read_json(EVAL_DIR / "topographic_map" / "matches.geojson")["features"]
    role_specs = [
        ("A0033320", "pedestrian_area", "보행공간"),
        ("A0043325", "crossing_candidate", "횡단보도"),
        ("A0063321", "grade_separated_crossing_candidate", "육교"),
        ("C0390000", "stairs_candidate", "계단"),
        ("C0463374", "underground_entrance_candidate", "지하도 입구"),
    ]
    code_totals = topographic_metrics["metrics"]["feature_counts_by_code_in_context"]
    topographic_rows: list[dict[str, Any]] = []
    for code, role, label in role_specs:
        matched_features = [
            feature
            for feature in topographic_features
            if feature["properties"].get("source_feature_code") == code
        ]
        statuses = Counter(feature["properties"].get("match_status") for feature in matched_features)
        total = int(code_totals[code])
        statuses["unmatched"] = total - statuses["unique"] - statuses["ambiguous"]
        topographic_rows.append(
            {
                "object_type": label,
                "role": role,
                "total": total,
                "unique": statuses["unique"],
                "ambiguous": statuses["ambiguous"],
                "unmatched": statuses["unmatched"],
                "unique_pct": pct(statuses["unique"], total),
                "ambiguous_pct": pct(statuses["ambiguous"], total),
                "unmatched_pct": pct(statuses["unmatched"], total),
            }
        )
    topographic_total = sum(row["total"] for row in topographic_rows)
    topographic_unique = sum(row["unique"] for row in topographic_rows)

    precheck = read_csv(PACKAGE_DIR / "ai_precheck_80.csv")
    paired: defaultdict[str, dict[str, str]] = defaultdict(dict)
    for row in precheck:
        paired[row["sample_id"]][row["side_label"]] = row["final_ai_precheck_result"]
    paired_rows = [
        {
            "sample_id": sample_id,
            "a_result": values.get("A"),
            "b_result": values.get("B"),
            "same": values.get("A") == values.get("B"),
        }
        for sample_id, values in sorted(paired.items())
    ]
    paired_same = sum(row["same"] for row in paired_rows)
    paired_different = len(paired_rows) - paired_same

    mappings = read_json(ROOT / "data" / "processed" / "onway_crosswalk_mappings.json")
    mapped = [row for row in mappings if row.get("mapping_status") == "mapped" and row.get("edge_id") in edges]
    crosswalk_edge_groups: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in mapped:
        crosswalk_edge_groups[row["edge_id"]].append(row)
    crosswalk_sensitivity_rows: list[dict[str, Any]] = []
    for edge_id, group in crosswalk_edge_groups.items():
        metric = dict(edge_metric(edge_id) or {})
        metric["sample_ids"] = ", ".join(row["sample_id"] for row in group)
        metric["crosswalk_count"] = len(group)
        crosswalk_sensitivity_rows.append(metric)
    crosswalk_sensitivity_rows.sort(
        key=lambda row: (
            row["alternative_status"] != "disconnected",
            -(row.get("alternative_ratio") or 0),
            row["edge_id"],
        )
    )
    alternate_ratios = [row["alternative_ratio"] for row in crosswalk_sensitivity_rows if row["alternative_ratio"] is not None]
    snap_distances = [float(row["distance_m"]) for row in mapped]
    bridge_sample_ids = sorted(
        row["sample_id"]
        for row in mapped
        if (edge_metric(row["edge_id"]) or {}).get("is_bridge_edge")
    )
    articulation_sample_ids = sorted(
        row["sample_id"]
        for row in mapped
        if (edge_metric(row["edge_id"]) or {}).get("articulation_adjacent")
    )

    review_features = read_json(EVAL_DIR / "review_queue.geojson")["features"]
    source_counts = Counter(feature["properties"]["review_source"] for feature in review_features)
    source_labels = {
        "topographic_map": "수치지형도 매칭",
        "public_crosswalk": "공공 횡단보도",
        "topographic_map_unmatched": "수치지형도 미매칭",
        "hdmap": "HD Map",
        "dem": "DEM",
        "orthophoto": "정사영상",
    }
    review_source_rows = [
        {"source": source, "label": source_labels[source], "count": source_counts[source]}
        for source in source_labels
    ]
    linked_candidate_edge_ids = [
        normalized_edge_id(feature["properties"], edges)
        for feature in review_features
        if normalized_edge_id(feature["properties"], edges)
    ]

    evidence_by_edge, years_by_edge = build_evidence_index(edges)
    evidence_rows: list[dict[str, Any]] = []
    evidence_band_counts: Counter[str] = Counter()
    combination_counts: Counter[str] = Counter()
    temporal_band_counts: Counter[str] = Counter()
    for edge_id in sorted(edges):
        sources = sorted(evidence_by_edge[edge_id])
        count = len(sources)
        band = "0개 (OSM only)" if count == 0 else "1개" if count == 1 else "2개" if count == 2 else "3개 이상"
        evidence_band_counts[band] += 1
        combination = "OSM only" if not sources else "OSM + " + " + ".join(sources)
        combination_counts[combination] += 1
        all_years = {2026, *years_by_edge[edge_id]}
        gap = max(all_years) - min(all_years)
        temporal_band = "0년" if gap == 0 else "1년" if gap == 1 else "2년" if gap == 2 else "3년" if gap == 3 else "4년 이상"
        temporal_band_counts[temporal_band] += 1
        evidence_rows.append(
            {
                "edge_id": edge_id,
                "candidate_evidence_layer_count": count,
                "candidate_evidence_layers": ";".join(sources),
                "evidence_band": band,
                "source_years": ";".join(str(year) for year in sorted(all_years)),
                "temporal_gap_years": gap,
                "dem_90m_context_available": True,
                "human_verified": False,
                "note": "공간 레이어 연결 수이며 독립적 사실 확인 수가 아님",
            }
        )

    priority_rows: list[dict[str, Any]] = []
    for feature in review_features:
        props = feature["properties"]
        edge_id = normalized_edge_id(props, edges)
        status = mapping_status(props)
        distance = mapping_distance(props)
        metric = edge_metric(edge_id)

        structural = 0
        if metric:
            if metric["is_bridge_edge"]:
                structural += 20
            if metric["articulation_adjacent"]:
                structural += 10
            ratio = metric.get("alternative_ratio")
            if ratio is None:
                structural += 10
            elif ratio >= 5:
                structural += 10
            elif ratio >= 3:
                structural += 7
            elif ratio >= 1.5:
                structural += 4
        structural = min(structural, 40)

        spatial = {
            "unique": 0,
            "ambiguous": 12,
            "unmatched": 20,
            "insufficient_resolution": 15,
            "not_linked": 20,
        }.get(status, 15)
        if distance is not None:
            spatial += 10 if distance > 10 else 8 if distance > 6 else 4 if distance > 3 else 0
        elif edge_id is None:
            spatial += 10
        spatial = min(spatial, 30)

        evidence_count = len(evidence_by_edge[edge_id]) if edge_id else 0
        evidence_gap = 20 if evidence_count == 0 else 15 if evidence_count == 1 else 8 if evidence_count == 2 else 0

        candidate_year = source_year(props)
        relevant_years = {2026, *years_by_edge[edge_id]} if edge_id else {2026}
        if candidate_year:
            relevant_years.add(candidate_year)
        temporal_gap = max(relevant_years) - min(relevant_years)
        temporal = 0 if temporal_gap == 0 else 3 if temporal_gap == 1 else 6 if temporal_gap == 2 else 8 if temporal_gap == 3 else 10

        score = structural + spatial + evidence_gap + temporal
        band = "high" if score >= 60 else "medium" if score >= 35 else "low"
        priority_rows.append(
            {
                "review_queue_id": props.get("review_queue_id"),
                "review_source": props.get("review_source"),
                "review_role": props.get("review_role"),
                "source_feature_id": props.get("source_feature_id") or props.get("public_crosswalk_id") or props.get("crosswalk_id") or props.get("edge_id"),
                "graph_edge_id": edge_id,
                "mapping_status": status,
                "mapping_distance_m": round(distance, 3) if distance is not None else None,
                "source_year": candidate_year,
                "bridge_edge": bool(metric and metric["is_bridge_edge"]),
                "articulation_adjacent": bool(metric and metric["articulation_adjacent"]),
                "alternative_ratio": metric.get("alternative_ratio") if metric else None,
                "linked_candidate_evidence_layers": evidence_count,
                "temporal_gap_years": temporal_gap,
                "structural_score_40": structural,
                "spatial_uncertainty_score_30": spatial,
                "evidence_gap_score_20": evidence_gap,
                "temporal_risk_score_10": temporal,
                "review_priority_score_100": score,
                "priority_band": band,
                "status": "advisory_unvalidated_priority; pending; verified=false; graph_update_allowed=false",
            }
        )
    priority_rows.sort(
        key=lambda row: (-row["review_priority_score_100"], str(row["review_queue_id"]))
    )
    for rank, row in enumerate(priority_rows, start=1):
        row["priority_rank"] = rank
    priority_band_counts = Counter(row["priority_band"] for row in priority_rows)

    correspondence = read_json(EVAL_DIR / "cross_sources" / "crosswalk_correspondence.geojson")["features"]
    correspondence_counts = Counter(feature["properties"].get("hd_match_status") for feature in correspondence)
    hd_inside = sum(
        correspondence_counts[key] for key in ("matched_near", "nearby_review", "unmatched")
    )

    legacy_block_rows = [row for row in precheck if row.get("final_ai_precheck_result") == "block"]
    legacy_block_labels = Counter(row.get("ai_candidate_label") for row in legacy_block_rows)

    route_impact = read_json(EVAL_DIR / "graph_enrichment" / "route_impact_simulation.json")
    route_rows: list[dict[str, Any]] = []
    stairs_candidates = [
        candidate
        for candidate in route_impact["candidate_edges"]
        if candidate.get("proposed_changes", {}).get("stairs") is True
    ]
    for index, candidate in enumerate(stairs_candidates, start=1):
        route_rows.append(
            {
                "case": f"#{index}",
                "candidate_id": candidate["candidate_id"],
                "edge_id": candidate["edge_id"],
                "before_m": candidate["before"]["distance_m"],
                "after_status": candidate["after"]["status"],
                "after_m": candidate["after"]["distance_m"],
                "difference_m": candidate.get("difference_m"),
                "interpretation": "가상 적용 민감도; 성과 측정값 아님; Graph 미반영",
            }
        )

    validation = read_json(EVAL_DIR / "evaluation_summary.json")
    dem = read_json(EVAL_DIR / "dem" / "metrics.json")
    graph_enrichment = read_json(EVAL_DIR / "graph_enrichment" / "metrics.json")
    graph_sha_after = sha256(GRAPH_PATH)

    summary: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": "current repository data; report analysis only",
        "safety": {
            "graph_sha256_before": graph_sha_before,
            "graph_sha256_after": graph_sha_after,
            "graph_unchanged": graph_sha_before == graph_sha_after,
            "raw_inputs_mutated": False,
            "routing_graph_mutated": False,
            "human_review_decisions_created": False,
            "candidate_values_promoted_to_verified": False,
        },
        "crosswalk_accessibility_missingness": {
            "citywide_crosswalk_count": len(raw_crosswalks),
            "attributes": missingness,
        },
        "paired_endpoint_ai_precheck": {
            "scope_warning": "대표 회랑 비무작위 표본의 AI 사전판독 결과이며 안양시 전체 현장 상태로 일반화할 수 없음",
            "crosswalk_count": len(paired_rows),
            "same_count": paired_same,
            "different_count": paired_different,
            "different_pct": pct(paired_different, len(paired_rows), 1),
        },
        "topographic_graph_matching": {
            "object_count": topographic_total,
            "unique_count": topographic_unique,
            "unique_pct": pct(topographic_unique, topographic_total, 3),
            "by_object": topographic_rows,
        },
        "review_queue": {
            "candidate_count": len(review_features),
            "by_source": review_source_rows,
            "with_graph_edge_count": len(linked_candidate_edge_ids),
            "with_graph_edge_pct": pct(len(linked_candidate_edge_ids), len(review_features)),
            "unique_graph_edge_count": len(set(linked_candidate_edge_ids)),
            "graph_edge_coverage_pct": pct(len(set(linked_candidate_edge_ids)), len(edges)),
            "status": "pending",
            "verified_true_count": 0,
            "graph_update_allowed_true_count": 0,
        },
        "crosswalk_graph_representation": {
            "sample_count": len(mapped),
            "unique_graph_edge_count": len(crosswalk_edge_groups),
            "compressed_unit_count": len(mapped) - len(crosswalk_edge_groups),
            "compressed_unit_pct": pct(len(mapped) - len(crosswalk_edge_groups), len(mapped)),
            "max_crosswalks_on_one_edge": max(len(group) for group in crosswalk_edge_groups.values()),
            "snap_distance_m": {
                "median": round(statistics.median(snap_distances), 3),
                "mean": round(statistics.fmean(snap_distances), 3),
                "p95": round(percentile(snap_distances, 0.95) or 0.0, 3),
                "max": round(max(snap_distances), 3),
                "le_1m": sum(value <= 1 for value in snap_distances),
                "gt_1_le_3m": sum(1 < value <= 3 for value in snap_distances),
                "gt_3_le_5m": sum(3 < value <= 5 for value in snap_distances),
                "gt_5m": sum(value > 5 for value in snap_distances),
                "gt_10m": sum(value > 10 for value in snap_distances),
            },
        },
        "crosswalk_edge_sensitivity": {
            "unique_edge_count": len(crosswalk_sensitivity_rows),
            "no_alternative_edge_count": sum(row["is_bridge_edge"] for row in crosswalk_sensitivity_rows),
            "no_alternative_sample_ids": bridge_sample_ids,
            "alternative_available_edge_count": len(alternate_ratios),
            "alternative_ratio_median": round(statistics.median(alternate_ratios), 2),
            "alternative_ratio_p90": round(percentile(alternate_ratios, 0.90) or 0.0, 2),
            "alternative_ratio_max": round(max(alternate_ratios), 2),
            "bridge_crosswalk_count": len(bridge_sample_ids),
            "articulation_adjacent_crosswalk_count": len(articulation_sample_ids),
            "articulation_adjacent_crosswalk_pct": pct(len(articulation_sample_ids), len(mapped)),
            "articulation_adjacent_sample_ids": articulation_sample_ids,
            "scope_warning": "현재 OSM 기반 Proxy Graph의 구조 민감도이며 실제 보행 우회거리 추정값이 아님",
        },
        "review_priority": {
            "method_status": "derived advisory heuristic; not calibrated or human-validated",
            "formula": {
                "structural_criticality": "0-40: bridge 20, articulation adjacency 10, alternative-route ratio 0-10",
                "spatial_uncertainty": "0-30: mapping status 0-20 plus distance/no-edge 0-10",
                "evidence_gap": "0-20: fewer uniquely linked candidate evidence layers scores higher",
                "temporal_risk": "0-10: 2026 OSM and linked/candidate source-year span",
                "bands": "high >=60, medium 35-59, low <35",
            },
            "candidate_count": len(priority_rows),
            "band_counts": dict(priority_band_counts),
            "top10": priority_rows[:10],
        },
        "evidence_coverage": {
            "definition": "OSM 외에 unique로 연결된 공간 레이어 수; 독립적 확인 또는 사람 검증 수가 아님",
            "edge_count": len(edges),
            "band_counts": dict(evidence_band_counts),
            "combination_top10": dict(combination_counts.most_common(10)),
            "human_verified_edge_count": 0,
            "dem_note": "90m DEM context는 전 Edge에 있으나 hard constraint 근거에서 제외",
        },
        "temporal_consistency": {
            "edge_gap_band_counts": dict(temporal_band_counts),
            "source_vintages": {
                "topographic_map": "2022/2025",
                "hd_map": 2023,
                "dem": 2025,
                "orthophoto": 2025,
                "roadview": 2025,
                "public_crosswalk": 2026,
                "osm": 2026,
            },
        },
        "cross_source_correspondence": {
            "public_crosswalk_context_count": len(correspondence),
            "inside_hd_coverage_count": hd_inside,
            "direct_near_match_count": correspondence_counts["matched_near"],
            "direct_near_match_pct_inside": pct(correspondence_counts["matched_near"], hd_inside, 1),
            "including_nearby_review_count": correspondence_counts["matched_near"] + correspondence_counts["nearby_review"],
            "including_nearby_review_pct_inside": pct(correspondence_counts["matched_near"] + correspondence_counts["nearby_review"], hd_inside, 1),
            "outside_hd_coverage_count": correspondence_counts["outside_hd_coverage"],
            "interpretation": "정확도가 아니라 객체 정의와 geometry 단위 차이로 단순 자동 Join이 어렵다는 지표",
        },
        "ai_policy_separation": {
            "legacy_block_candidate_count": len(legacy_block_rows),
            "candidate_labels": dict(legacy_block_labels),
            "tactile_absent_count": legacy_block_labels["tactile_absent_candidate"],
            "tactile_absent_share_pct": pct(legacy_block_labels["tactile_absent_candidate"], len(legacy_block_rows)),
            "wheelchair_hard_constraint_note": "현 wheelchair hard-constraint에는 tactile absence가 없음. 인식 결과와 사용자별 정책 판단을 분리해야 함.",
        },
        "route_impact_simulation": {
            "scope_warning": "미승인 stairs 후보를 가상 적용한 민감도 분석; 성과 또는 실제 경로 결과가 아님",
            "case_count": len(route_rows),
            "changed_count": sum(candidate.get("route_changed") for candidate in stairs_candidates),
            "no_route_count": sum(candidate["after"].get("status") == "no_accessible_route" for candidate in stairs_candidates),
            "cases": route_rows,
            "current_full_diagnostic_count": len(route_impact["candidate_edges"]),
            "current_full_diagnostic_no_route_count": route_impact["candidate_edge_no_route_count"],
            "current_dem_slope_diagnostic_count": len(route_impact["candidate_edges"]) - len(stairs_candidates),
            "full_diagnostic_note": "현재 파일에는 90m DEM slope 진단 후보가 추가되어 있으나 hard constraint 승인 대상이 아니므로 핵심 Figure에서 제외",
        },
        "graph": {
            "node_count": sum(feature.get("properties", {}).get("feature_type") == "node" for feature in graph_data["features"]),
            "edge_count": len(edges),
            "connected_component_count": nx.number_connected_components(simple_graph),
            "largest_component_pct": pct(len(max(nx.connected_components(simple_graph), key=len)), simple_graph.number_of_nodes()),
            "articulation_point_count": len(articulation_nodes),
            "bridge_edge_pair_count": len(list(nx.bridges(simple_graph))),
            "proxy_warning": "OSM 기반 Proxy Graph 구조이며 실제 안양 보행망 위험도를 뜻하지 않음",
        },
        "validation": {
            "status": validation["status"],
            "check_counts": validation["results"]["common_validation"]["summary"]["check_counts"],
            "graph_unchanged": validation["graph"]["unchanged"],
        },
        "dem": {
            "edge_count": dem["graph"]["edge_count"],
            "under_3_cells_count": dem["metrics"]["fewer_than_three_cells_edge_count"],
            "under_3_cells_pct": pct(
                dem["metrics"]["fewer_than_three_cells_edge_count"],
                dem["graph"]["edge_count"],
            ),
            "same_90m_cell_count": dem["metrics"]["same_cell_endpoint_edge_count"],
            "hard_constraint_eligible_edge_count": dem["metrics"]["hard_constraint_eligible_edge_count"],
        },
        "graph_enrichment_safety": graph_enrichment["safety"],
    }

    assert len(raw_crosswalks) == 2728
    assert all(item["blank"] == 2553 for item in missingness.values())
    assert topographic_total == 1351 and topographic_unique == 390
    assert len(review_features) == 414
    assert len(linked_candidate_edge_ids) == 325 and len(set(linked_candidate_edge_ids)) == 192
    assert len(mapped) == 40 and len(crosswalk_edge_groups) == 30
    assert paired_different == 19
    assert len(route_rows) == 5 and summary["route_impact_simulation"]["no_route_count"] == 2
    assert len(edges) == 723
    assert graph_sha_before == graph_sha_after

    tables = {
        "topographic": topographic_rows,
        "review_sources": review_source_rows,
        "paired_endpoints": paired_rows,
        "crosswalk_sensitivity": crosswalk_sensitivity_rows,
        "review_priority": priority_rows,
        "evidence_coverage": evidence_rows,
        "route_impact": route_rows,
    }
    return summary, tables


def write_figures(summary: dict[str, Any], tables: dict[str, list[dict[str, Any]]]) -> None:
    missing = summary["crosswalk_accessibility_missingness"]["attributes"]
    write_100pct_stacked_chart(
        OUTPUT_DIR / "figure_01_crosswalk_missingness.svg",
        title="안양시 횡단보도 접근성 속성 입력 현황",
        subtitle="횡단보도 2,728건의 보도턱·점자블록 입력률 — 두 속성 모두 93.59% 공란",
        rows=[
            (label, [("입력", values["entry_rate_pct"], COLORS["blue"]), ("공란", values["missing_rate_pct"], COLORS["pale"])])
            for label, values in missing.items()
        ],
        legend=[("접근성 정보 입력", COLORS["blue"]), ("공란", COLORS["pale"])],
    )

    endpoint = summary["paired_endpoint_ai_precheck"]
    write_100pct_stacked_chart(
        OUTPUT_DIR / "figure_02_endpoint_difference.svg",
        title="대표 횡단보도 양단 AI 사전판독 차이",
        subtitle="비무작위 대표 회랑 표본 40건 — 안양시 전체 현장 상태로 일반화하지 않음",
        rows=[
            (
                "A/B 접근부",
                [
                    ("동일", pct(endpoint["same_count"], endpoint["crosswalk_count"], 1), COLORS["teal"]),
                    ("상이", endpoint["different_pct"], COLORS["coral"]),
                ],
            )
        ],
        legend=[("A/B 동일 21건", COLORS["teal"]), ("A/B 상이 19건", COLORS["coral"])],
        source="AI 사전판독 반복자료 기반, ARNAVIGATION 2026-09-18",
    )

    topo_rows = []
    for row in tables["topographic"]:
        topo_rows.append(
            (
                row["object_type"],
                [
                    ("Unique", row["unique_pct"], COLORS["blue"]),
                    ("Ambiguous", row["ambiguous_pct"], COLORS["amber"]),
                    ("Unmatched", row["unmatched_pct"], COLORS["coral"]),
                ],
            )
        )
    write_100pct_stacked_chart(
        OUTPUT_DIR / "figure_03_topographic_matching.svg",
        title="공간객체별 Routing Graph 매칭 품질",
        subtitle="수치지형도 1,351개 객체와 OSM 기반 Proxy Graph의 자동매칭 결과",
        rows=topo_rows,
        legend=[("Unique", COLORS["blue"]), ("Ambiguous", COLORS["amber"]), ("Unmatched", COLORS["coral"])],
    )

    write_horizontal_bar_chart(
        OUTPUT_DIR / "figure_04_review_candidate_sources.svg",
        title="공간데이터 기반 Human Review 후보 414건",
        subtitle="모든 후보는 pending · verified=false이며 사람 승인 전 Graph에 반영되지 않음",
        rows=[(row["label"], row["count"], COLORS["blue"], f'{row["count"]}건') for row in tables["review_sources"]],
    )

    route_rows = tables["route_impact"]
    body: list[str] = []
    x0, width, maximum = 270.0, 800.0, 1400.0
    height = 650
    for tick in (0, 350, 700, 1050, 1400):
        x = x0 + width * tick / maximum
        body.append(f'<line x1="{x:.1f}" y1="145" x2="{x:.1f}" y2="535" stroke="{COLORS["grid"]}"/>')
        body.append(svg_text(x, 133, f"{tick:,}m", size=15, fill=COLORS["muted"], anchor="middle"))
    for index, row in enumerate(route_rows):
        y = 170 + index * 72
        before_x = x0 + width * row["before_m"] / maximum
        body.append(svg_text(64, y + 22, row["case"], size=20, weight=700))
        body.append(f'<circle cx="{before_x:.1f}" cy="{y + 15}" r="8" fill="{COLORS["teal"]}"/>')
        body.append(svg_text(before_x, y + 46, f'{row["before_m"]:.1f}m', size=15, fill=COLORS["teal"], anchor="middle"))
        if row["after_m"] is None:
            body.append(f'<line x1="{before_x:.1f}" y1="{y + 15}" x2="{x0 + width:.1f}" y2="{y + 15}" stroke="{COLORS["coral"]}" stroke-width="4" stroke-dasharray="9 8"/>')
            body.append(svg_text(x0 + width + 20, y + 22, "경로 없음", size=17, weight=700, fill=COLORS["coral"]))
        else:
            after_x = x0 + width * row["after_m"] / maximum
            body.append(f'<line x1="{before_x:.1f}" y1="{y + 15}" x2="{after_x:.1f}" y2="{y + 15}" stroke="{COLORS["coral"]}" stroke-width="5"/>')
            body.append(f'<circle cx="{after_x:.1f}" cy="{y + 15}" r="9" fill="{COLORS["coral"]}"/>')
            body.append(svg_text(after_x, y - 2, f'{row["after_m"]:,.1f}m', size=15, weight=700, fill=COLORS["coral"], anchor="middle"))
    body.append(f'<circle cx="70" cy="570" r="7" fill="{COLORS["teal"]}"/>')
    body.append(svg_text(84, 576, "적용 전", size=16, fill=COLORS["muted"]))
    body.append(f'<circle cx="175" cy="570" r="7" fill="{COLORS["coral"]}"/>')
    body.append(svg_text(189, 576, "가상 적용 후", size=16, fill=COLORS["muted"]))
    (OUTPUT_DIR / "figure_05_unverified_route_impact.svg").write_text(
        svg_document(
            "미검증 stairs 후보의 경로 민감도",
            "5개 후보를 가상 적용한 진단 — 성과 측정값이나 실제 서비스 경로가 아님",
            body,
            height=height,
        ),
        encoding="utf-8",
    )

    representation = summary["crosswalk_graph_representation"]
    write_horizontal_bar_chart(
        OUTPUT_DIR / "figure_06_crosswalk_graph_compression.svg",
        title="횡단보도 접근성 공간단위 손실",
        subtitle="대표 횡단보도 40건이 현재 Proxy Graph에서는 30개 Edge로 압축",
        rows=[
            ("실제 횡단보도 표본", representation["sample_count"], COLORS["blue"], "40개"),
            ("연결된 고유 Graph Edge", representation["unique_graph_edge_count"], COLORS["teal"], "30개"),
        ],
    )

    evidence = summary["evidence_coverage"]["band_counts"]
    evidence_order = ["0개 (OSM only)", "1개", "2개", "3개 이상"]
    evidence_colors = [COLORS["pale"], COLORS["blue"], COLORS["teal"], COLORS["violet"]]
    write_horizontal_bar_chart(
        OUTPUT_DIR / "figure_07_evidence_coverage.svg",
        title="Graph Edge별 공간 증거 레이어 커버리지",
        subtitle="Unique로 연결된 OSM 외 후보 레이어 수 — 독립 검증 수가 아니며 사람 검증 Edge는 0개",
        rows=[(label, evidence.get(label, 0), color, f'{evidence.get(label, 0)}개 Edge') for label, color in zip(evidence_order, evidence_colors)],
    )

    priority = summary["review_priority"]["band_counts"]
    write_horizontal_bar_chart(
        OUTPUT_DIR / "figure_08_review_priority.svg",
        title="Human Review 후보 우선순위 분포",
        subtitle="구조 중요도·공간 불확실성·증거 공백·시점 차이를 합친 미보정 자문 점수",
        rows=[
            ("High (60점 이상)", priority.get("high", 0), COLORS["coral"], f'{priority.get("high", 0)}건'),
            ("Medium (35–59점)", priority.get("medium", 0), COLORS["amber"], f'{priority.get("medium", 0)}건'),
            ("Low (35점 미만)", priority.get("low", 0), COLORS["teal"], f'{priority.get("low", 0)}건'),
        ],
    )


def render_png_copies() -> int:
    """Render SVG figures to PNG when the dev Playwright runtime is available."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return 0

    rendered = 0
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(
                viewport={"width": 1200, "height": 900},
                device_scale_factor=1,
            )
            for svg_path in sorted(OUTPUT_DIR.glob("figure_*.svg")):
                page.goto(svg_path.resolve().as_uri(), wait_until="load")
                height = int(page.locator("svg").get_attribute("height") or 900)
                page.set_viewport_size({"width": 1200, "height": height})
                page.screenshot(path=str(svg_path.with_suffix(".png")))
                rendered += 1
            browser.close()
    except Exception:
        # SVG is the canonical report figure; PNG is a convenience copy.
        return 0
    return rendered


def report_markdown(summary: dict[str, Any], tables: dict[str, list[dict[str, Any]]]) -> str:
    missing = summary["crosswalk_accessibility_missingness"]
    topo = summary["topographic_graph_matching"]
    queue = summary["review_queue"]
    paired = summary["paired_endpoint_ai_precheck"]
    representation = summary["crosswalk_graph_representation"]
    sensitivity = summary["crosswalk_edge_sensitivity"]
    priority = summary["review_priority"]
    cross_source = summary["cross_source_correspondence"]
    validation = summary["validation"]
    dem = summary["dem"]
    route = summary["route_impact_simulation"]

    top_sensitivity = sorted(
        (row for row in tables["crosswalk_sensitivity"] if row["alternative_ratio"] is not None),
        key=lambda row: row["alternative_ratio"],
        reverse=True,
    )[:5]
    top_priority = tables["review_priority"][:10]

    lines = [
        "# ARNAVIGATION 보고서용 데이터 분석 패키지",
        "",
        "> 기준일: 2026-09-18  ",
        "> 분석 범위: 현재 저장소의 공식 원자료와 파생 평가 산출물  ",
        "> 안전 경계: 후보·AI 판독·자동매칭 결과는 모두 미검증 파생자료이며 사람 승인 전 Graph에 반영하지 않음",
        "",
        "## 한 문장 결론",
        "",
        f"공공 횡단보도 접근성 속성은 {missing['attributes']['보도턱 낮춤']['missing_rate_pct']:.2f}%가 공란이고, 대표 회랑 표본에서는 양단 AI 사전판독이 {paired['different_pct']:.1f}% 달랐으며, 수치지형도 객체의 자동 Unique Match는 {topo['unique_pct']:.2f}%에 그쳤다. 따라서 NaVi는 다중 공간자료에서 {queue['candidate_count']}개의 검수 후보를 만들되, 미승인 후보를 즉시 경로에 적용하지 않는 Human-in-the-loop 구조를 유지해야 한다.",
        "",
        "## 보고서 핵심 논리선",
        "",
        f"1. 기존 공공데이터: 접근성 속성 {missing['attributes']['보도턱 낮춤']['missing_rate_pct']:.2f}% 공란",
        f"2. 표현 단위: 대표 회랑 표본 {paired['crosswalk_count']}건 중 {paired['different_count']}건({paired['different_pct']:.1f}%)에서 A/B 사전판독 상이",
        f"3. 자동통합 한계: 수치지형도 {topo['object_count']:,}객체 중 Unique {topo['unique_count']}건({topo['unique_pct']:.2f}%)",
        f"4. 검수 작업화: 6개 생성원에서 Human Review 후보 {queue['candidate_count']}건 구성",
        f"5. 승인 필요성: stairs 후보 5건 가상 적용 시 최대 +1,205.8m, 2건은 대체 경로 없음",
        "",
        "## 1. 안양시 횡단보도 접근성 데이터 결측률",
        "",
        "| 접근성 속성 | 입력 | 공란 | 입력률 | 공란률 |",
        "|---|---:|---:|---:|---:|",
    ]
    for label, values in missing["attributes"].items():
        lines.append(f"| {label} | {values['entered']:,} | {values['blank']:,} | {values['entry_rate_pct']:.2f}% | {values['missing_rate_pct']:.2f}% |")
    lines += [
        "",
        "![안양시 횡단보도 접근성 속성 입력 현황](../artifacts/report-analysis-20260918/figure_01_crosswalk_missingness.svg)",
        "",
        "보고서 문장: 안양시 횡단보도 현황 2,728건을 분석한 결과, 보도턱 낮춤 여부와 점자블록 유무의 데이터 입력률은 각각 6.41%에 그쳤으며 93.59%는 공란으로 확인되었다. 기존 공공데이터만으로는 이동약자 경로판단에 필요한 세부 접근성 상태를 충분히 구성하기 어렵다.",
        "",
        "## 2. 동일 횡단보도의 양단 접근부 차이",
        "",
        f"대표 회랑 횡단보도 {paired['crosswalk_count']}건을 A/B 접근부로 나눈 AI 사전판독 결과, 동일 {paired['same_count']}건과 상이 {paired['different_count']}건으로 상이 비율은 {paired['different_pct']:.1f}%였다.",
        "",
        "![대표 횡단보도 양단 AI 사전판독 차이](../artifacts/report-analysis-20260918/figure_02_endpoint_difference.svg)",
        "",
        "주의: 이는 비무작위 대표 회랑 표본의 AI 사전판독 결과다. 사람 Ground Truth가 아니므로 ‘안양시 횡단보도의 47.5%’로 일반화하거나 실제 시설 상태로 표현하면 안 된다.",
        "",
        "## 3. 수치지형도 자동매칭",
        "",
        "| 객체 | 전체 | Unique | Ambiguous | Unmatched |",
        "|---|---:|---:|---:|---:|",
    ]
    for row in tables["topographic"]:
        lines.append(f"| {row['object_type']} | {row['total']:,} | {row['unique_pct']:.2f}% | {row['ambiguous_pct']:.2f}% | {row['unmatched_pct']:.2f}% |")
    lines += [
        "",
        f"전체 Unique Match는 {topo['unique_count']} / {topo['object_count']:,} = {topo['unique_pct']:.2f}%다. 특히 계단 객체의 76.21%가 현재 Proxy Graph에 자동 대응되지 않았다.",
        "",
        "![공간객체별 Routing Graph 매칭 품질](../artifacts/report-analysis-20260918/figure_03_topographic_matching.svg)",
        "",
        "## 4. Human Review 후보 414건",
        "",
        "| 생성원 | 건수 |",
        "|---|---:|",
    ]
    for row in tables["review_sources"]:
        lines.append(f"| {row['label']} | {row['count']} |")
    lines += [
        f"| 합계 | {queue['candidate_count']} |",
        "",
        f"Graph Edge ID가 연결된 후보는 {queue['with_graph_edge_count']}건({queue['with_graph_edge_pct']:.2f}%), 연결된 고유 Edge는 {queue['unique_graph_edge_count']}개로 전체 723개 Edge의 {queue['graph_edge_coverage_pct']:.2f}%다. 전 후보는 pending, verified=false, graph_update_allowed=false 상태다.",
        "",
        "![공간데이터 기반 Human Review 후보](../artifacts/report-analysis-20260918/figure_04_review_candidate_sources.svg)",
        "",
        "## 5. 미검증 속성의 경로 영향",
        "",
        "| 후보 | 적용 전 | 가상 적용 후 | 영향 |",
        "|---|---:|---:|---:|",
    ]
    for row in tables["route_impact"]:
        after = "경로 없음" if row["after_m"] is None else f"{row['after_m']:,.1f}m"
        impact = "단절" if row["difference_m"] is None else f"+{row['difference_m']:,.1f}m"
        lines.append(f"| {row['case']} | {row['before_m']:,.1f}m | {after} | {impact} |")
    lines += [
        "",
        f"현재 최신 시뮬레이션 파일에는 총 {route['current_full_diagnostic_count']}건이 있으나, 이 중 {route['current_dem_slope_diagnostic_count']}건은 90m DEM slope 진단 후보로 hard constraint 승인 대상이 아니다. 따라서 본문 Figure는 요청 범위이자 승인 가능 후보인 stairs 5건만 분리해 사용한다.",
        "",
        "![미검증 stairs 후보의 경로 민감도](../artifacts/report-analysis-20260918/figure_05_unverified_route_impact.svg)",
        "",
        "해석: 접근성 속성 하나를 잘못 hard constraint로 반영하면 큰 우회나 현재 Proxy Graph상의 단절을 만들 수 있다. 이 수치는 후보를 실제 Graph에 반영한 성과가 아니라, AI → Candidate → Human Review → 승인 후 반영 구조가 필요한 이유를 보여주는 가상 민감도다.",
        "",
        "## 6. 추가 구조 분석",
        "",
        "### 6.1 접근성 공간단위 손실",
        "",
        f"대표 횡단보도 {representation['sample_count']}건은 실제 Graph에서 {representation['unique_graph_edge_count']}개 Edge로 연결되어 {representation['compressed_unit_count']}개 공간단위({representation['compressed_unit_pct']:.1f}%)가 압축된다. 한 Edge에는 최대 {representation['max_crosswalks_on_one_edge']}개 횡단보도가 연결된다.",
        "",
        f"Snap 거리는 중앙값 {representation['snap_distance_m']['median']:.3f}m, 평균 {representation['snap_distance_m']['mean']:.3f}m, p95 {representation['snap_distance_m']['p95']:.3f}m, 최대 {representation['snap_distance_m']['max']:.3f}m다. 대체로 위치는 가깝지만 시설 표현 단위가 손실되는 문제를 분리해서 봐야 한다.",
        "",
        "![횡단보도 접근성 공간단위 손실](../artifacts/report-analysis-20260918/figure_06_crosswalk_graph_compression.svg)",
        "",
        "### 6.2 횡단보도 Edge 제거 민감도",
        "",
        f"연결된 고유 Edge {sensitivity['unique_edge_count']}개 중 {sensitivity['no_alternative_edge_count']}개는 제거 후 양 끝 Node 간 대체 경로가 없었다({', '.join(sensitivity['no_alternative_sample_ids'])}). 나머지 {sensitivity['alternative_available_edge_count']}개의 대체경로/기존 Edge 길이 배율은 중앙값 {sensitivity['alternative_ratio_median']:.2f}배, p90 {sensitivity['alternative_ratio_p90']:.2f}배, 최대 {sensitivity['alternative_ratio_max']:.2f}배다.",
        "",
        "| 표본 | 기존 Edge | 대체경로 | 배율 |",
        "|---|---:|---:|---:|",
    ]
    for row in top_sensitivity:
        lines.append(f"| {row['sample_ids']} | {row['original_edge_length_m']:.1f}m | {row['alternative_route_length_m']:.1f}m | {row['alternative_ratio']:.2f}배 |")
    lines += [
        "",
        f"표본 40건 중 Bridge Edge 위 횡단보도는 {sensitivity['bridge_crosswalk_count']}건, Articulation Node 인접 횡단보도는 {sensitivity['articulation_adjacent_crosswalk_count']}건({sensitivity['articulation_adjacent_crosswalk_pct']:.1f}%)이다. 이는 현장 위험도가 아니라 현재 OSM 기반 Proxy Graph의 우회 연결 부족을 나타낸다.",
        "",
        "### 6.3 검수 우선순위 점수",
        "",
        "점수는 구조 중요도 40점, 공간 불확실성 30점, 증거 공백 20점, 자료 시점 차이 10점으로 구성했다. 아직 사람 검수 결과로 보정되지 않은 자문용 휴리스틱이며 후보의 사실성·위험도 점수가 아니다.",
        "",
        f"분포: High {priority['band_counts'].get('high', 0)}건, Medium {priority['band_counts'].get('medium', 0)}건, Low {priority['band_counts'].get('low', 0)}건.",
        "",
        "![Human Review 후보 우선순위 분포](../artifacts/report-analysis-20260918/figure_08_review_priority.svg)",
        "",
        "| 순위 | 후보 | 생성원 | 역할 | 점수 | 구조 | 공간 | 증거 | 시점 |",
        "|---:|---|---|---|---:|---:|---:|---:|---:|",
    ]
    for row in top_priority:
        lines.append(
            f"| {row['priority_rank']} | {row['review_queue_id']} | {row['review_source']} | {row['review_role']} | {row['review_priority_score_100']} | {row['structural_score_40']} | {row['spatial_uncertainty_score_30']} | {row['evidence_gap_score_20']} | {row['temporal_risk_score_10']} |"
        )
    lines += [
        "",
        "### 6.4 Cross-source 단순 Join 한계",
        "",
        f"HD Map coverage 내부 공공 횡단보도 {cross_source['inside_hd_coverage_count']}건 중 직접 근접 대응은 {cross_source['direct_near_match_count']}건({cross_source['direct_near_match_pct_inside']:.1f}%), 주변 검토까지 포함하면 {cross_source['including_nearby_review_count']}건({cross_source['including_nearby_review_pct_inside']:.1f}%)이다. 이는 HD Map 정확도가 낮다는 뜻이 아니라 서로 다른 객체 정의와 geometry 단위 때문에 단순 자동 Join이 어렵다는 뜻이다.",
        "",
        "### 6.5 Edge별 증거 커버리지와 시점",
        "",
        "![Graph Edge별 공간 증거 레이어 커버리지](../artifacts/report-analysis-20260918/figure_07_evidence_coverage.svg)",
        "",
        "커버리지는 OSM 외에 Unique로 연결된 공공 횡단보도·수치지형도·HD Map·정사영상 레이어 수다. 정사영상 후보는 공공 횡단보도 위치를 영상에 투영한 QA 단위이므로 독립 관측 확인으로 해석하지 않는다. 사람 검증 Edge는 현재 0개다.",
        "",
        "자료 시점은 수치지형도 2022/2025, HD Map 2023, DEM·정사영상·로드뷰 2025, 공공 횡단보도·OSM 2026으로 섞여 있다. `table_06_evidence_coverage.csv`에 Edge별 시점 차이를 함께 기록했다.",
        "",
        "### 6.6 AI 인식과 사용자 정책 분리",
        "",
        f"기존 AI block 후보 {summary['ai_policy_separation']['legacy_block_candidate_count']}건 중 tactile_absent_candidate가 {summary['ai_policy_separation']['tactile_absent_count']}건({summary['ai_policy_separation']['tactile_absent_share_pct']:.1f}%)이다. 현 wheelchair hard constraint에는 점자블록 부재가 포함되지 않는다. 따라서 ‘점자블록이 보이지 않음’이라는 perception 결과와 사용자 프로필별 routing policy를 분리해야 한다.",
        "",
        "## 7. 보조 검증 결과",
        "",
        f"- Validation Check: Pass {validation['check_counts']['pass']}, Warning {validation['check_counts']['warning']}, Hold {validation['check_counts']['hold']}, Fail {validation['check_counts']['fail']}",
        f"- 평가 전후 Graph SHA-256 동일: {str(validation['graph_unchanged']).lower()}",
        f"- DEM: {dem['under_3_cells_count']} / {dem['edge_count']} Edge({dem['under_3_cells_pct']:.2f}%)가 3개 미만 Cell, 동일 90m Cell {dem['same_90m_cell_count']}개, hard constraint 사용 가능 Edge {dem['hard_constraint_eligible_edge_count']}개",
        "- 결론: 90m DEM은 도시 보행 Edge의 개별 경사를 hard constraint로 쓰기에 해상도가 부족하다.",
        "",
        "## 8. Figure 설명문",
        "",
        "1. Figure 1 — 안양시 횡단보도 2,728건의 보도턱·점자블록 속성 입력률. 두 속성 모두 93.59%가 공란이다.",
        "2. Figure 2 — 대표 회랑 횡단보도 40건의 A/B 접근부 AI 사전판독 비교. 19건(47.5%)에서 결과 차이가 관찰되었다.",
        "3. Figure 3 — 수치지형도 공간객체와 OSM 기반 Proxy Graph의 매칭 결과. 계단 등 접근성 핵심 객체에서 자동매칭 한계가 두드러진다.",
        "4. Figure 4 — 서로 다른 공간자료에서 자동 추출한 Human Review 후보 414건의 구성. 모든 후보는 사람 검증 전까지 Graph에 반영되지 않는다.",
        "5. Figure 5 — 미승인 stairs 후보 5건을 가상 적용한 경로 민감도. 최대 +1,205.8m와 2건의 대체경로 부재가 나타났으나 성과 측정값은 아니다.",
        "6. Figure 6 — 대표 횡단보도 40건이 현재 Proxy Graph에서 30개 Edge로 압축되는 접근성 공간단위 손실.",
        "7. Figure 7 — 723개 Edge별 OSM 외 후보 증거 레이어 연결 수. 레이어 수는 사람 검증 또는 독립 확인 수와 다르다.",
        "8. Figure 8 — 414개 검수 후보의 미보정 자문용 우선순위 분포. 현장검수 결과가 쌓이면 가중치와 구간을 재보정해야 한다.",
        "",
        "## 9. 산출물과 재현",
        "",
        "```powershell",
        ".\\.venv\\Scripts\\python.exe -X utf8 scripts\\build_report_analysis_package.py",
        "```",
        "",
        "- 요약: `artifacts/report-analysis-20260918/analysis_summary.json`",
        "- 우선순위 전체: `artifacts/report-analysis-20260918/table_05_review_priority_414.csv`",
        "- Edge 증거/시점: `artifacts/report-analysis-20260918/table_06_evidence_coverage.csv`",
        "- 입력 체크섬: `artifacts/report-analysis-20260918/input_manifest.csv`",
        "",
        "이 분석 과정은 원자료와 공용 Graph를 수정하지 않았으며, 실행 전후 Graph SHA-256이 동일하다.",
        "",
    ]
    return "\n".join(lines)


def write_outputs(summary: dict[str, Any], tables: dict[str, list[dict[str, Any]]]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    write_json(OUTPUT_DIR / "analysis_summary.json", summary)
    write_csv(
        OUTPUT_DIR / "table_01_topographic_matching.csv",
        tables["topographic"],
        ["object_type", "role", "total", "unique", "ambiguous", "unmatched", "unique_pct", "ambiguous_pct", "unmatched_pct"],
    )
    write_csv(
        OUTPUT_DIR / "table_02_review_candidate_sources.csv",
        tables["review_sources"],
        ["source", "label", "count"],
    )
    write_csv(
        OUTPUT_DIR / "table_03_paired_endpoint_ai_precheck.csv",
        tables["paired_endpoints"],
        ["sample_id", "a_result", "b_result", "same"],
    )
    write_csv(
        OUTPUT_DIR / "table_04_crosswalk_edge_sensitivity.csv",
        tables["crosswalk_sensitivity"],
        [
            "sample_ids",
            "crosswalk_count",
            "edge_id",
            "from_node",
            "to_node",
            "original_edge_length_m",
            "alternative_status",
            "alternative_route_length_m",
            "detour_m",
            "alternative_ratio",
            "is_bridge_edge",
            "articulation_adjacent",
        ],
    )
    priority_fields = [
        "priority_rank",
        "review_queue_id",
        "review_source",
        "review_role",
        "source_feature_id",
        "graph_edge_id",
        "mapping_status",
        "mapping_distance_m",
        "source_year",
        "bridge_edge",
        "articulation_adjacent",
        "alternative_ratio",
        "linked_candidate_evidence_layers",
        "temporal_gap_years",
        "structural_score_40",
        "spatial_uncertainty_score_30",
        "evidence_gap_score_20",
        "temporal_risk_score_10",
        "review_priority_score_100",
        "priority_band",
        "status",
    ]
    write_csv(OUTPUT_DIR / "table_05_review_priority_414.csv", tables["review_priority"], priority_fields)
    write_csv(
        OUTPUT_DIR / "table_06_evidence_coverage.csv",
        tables["evidence_coverage"],
        [
            "edge_id",
            "candidate_evidence_layer_count",
            "candidate_evidence_layers",
            "evidence_band",
            "source_years",
            "temporal_gap_years",
            "dem_90m_context_available",
            "human_verified",
            "note",
        ],
    )
    write_csv(
        OUTPUT_DIR / "table_07_unverified_route_impact.csv",
        tables["route_impact"],
        ["case", "candidate_id", "edge_id", "before_m", "after_status", "after_m", "difference_m", "interpretation"],
    )

    input_paths = [
        GRAPH_PATH,
        next((ROOT / "data" / "raw" / "anyang" / "crosswalks" / "2026").glob("*.csv")),
        ROOT / "data" / "processed" / "onway_crosswalk_mappings.json",
        EVAL_DIR / "review_queue.geojson",
        EVAL_DIR / "topographic_map" / "matches.geojson",
        EVAL_DIR / "cross_sources" / "crosswalk_correspondence.geojson",
        EVAL_DIR / "cross_sources" / "hdmap_graph_candidates.geojson",
        EVAL_DIR / "orthophoto" / "geometry_review_candidates.geojson",
        EVAL_DIR / "graph_enrichment" / "route_impact_simulation.json",
        PACKAGE_DIR / "ai_precheck_80.csv",
    ]
    manifest = [
        {
            "path": str(path.relative_to(ROOT)).replace("\\", "/"),
            "bytes": path.stat().st_size,
            "sha256": sha256(path),
        }
        for path in input_paths
    ]
    write_csv(OUTPUT_DIR / "input_manifest.csv", manifest, ["path", "bytes", "sha256"])
    write_figures(summary, tables)
    render_png_copies()
    REPORT_PATH.write_text(report_markdown(summary, tables), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary", action="store_true", help="Print the compact summary after writing outputs")
    args = parser.parse_args()
    summary, tables = analyze()
    write_outputs(summary, tables)
    result = {
        "report": str(REPORT_PATH.relative_to(ROOT)),
        "output_dir": str(OUTPUT_DIR.relative_to(ROOT)),
        "graph_unchanged": summary["safety"]["graph_unchanged"],
        "core_metrics": {
            "crosswalk_missing_pct": summary["crosswalk_accessibility_missingness"]["attributes"]["보도턱 낮춤"]["missing_rate_pct"],
            "paired_endpoint_difference_pct": summary["paired_endpoint_ai_precheck"]["different_pct"],
            "topographic_unique_pct": summary["topographic_graph_matching"]["unique_pct"],
            "review_candidate_count": summary["review_queue"]["candidate_count"],
            "route_simulation_no_route_count": summary["route_impact_simulation"]["no_route_count"],
        },
    }
    if args.summary:
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
