"""Compute report-ready metrics from the current NaVi repository data.

The script is deliberately read-only.  It distinguishes source observations,
derived candidates, synthetic fixtures, and human-verified records so that a
report cannot accidentally present proxy data as field truth.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sqlite3
import statistics
import zipfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from xml.etree import ElementTree as ET

import networkx as nx


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "docs" / "ONWAY_안양_대표회랑_MVP_데이터패키지_20260915"
EVAL = ROOT / "data" / "processed" / "evaluation"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def number(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "null"}:
        return None
    try:
        result = float(text)
    except ValueError:
        return None
    return result if math.isfinite(result) else None


def truthy(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "t", "yes", "y"}


def percentile(values: Iterable[float], q: float) -> float | None:
    ordered = sorted(float(v) for v in values if v is not None and math.isfinite(float(v)))
    if not ordered:
        return None
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * q
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def describe(values: Iterable[float], digits: int = 3) -> dict[str, float | int | None]:
    clean = [float(v) for v in values if v is not None and math.isfinite(float(v))]
    if not clean:
        return {"n": 0, "min": None, "median": None, "mean": None, "p90": None, "p95": None, "max": None}
    return {
        "n": len(clean),
        "min": round(min(clean), digits),
        "median": round(statistics.median(clean), digits),
        "mean": round(statistics.fmean(clean), digits),
        "p90": round(percentile(clean, 0.90) or 0.0, digits),
        "p95": round(percentile(clean, 0.95) or 0.0, digits),
        "max": round(max(clean), digits),
    }


def pct(numerator: float, denominator: float, digits: int = 2) -> float | None:
    if denominator == 0:
        return None
    return round(100.0 * numerator / denominator, digits)


def counts(rows: Iterable[dict[str, Any]], field: str) -> dict[str, int]:
    counter: Counter[str] = Counter()
    for row in rows:
        value = row.get(field)
        label = "(blank)" if value is None or str(value).strip() == "" else str(value)
        counter[label] += 1
    return dict(sorted(counter.items(), key=lambda item: (-item[1], item[0])))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def xlsx_sheet_rows(path: Path, sheet_name: str) -> list[list[Any]]:
    """Read cell values from one XLSX sheet without adding an Excel dependency."""
    main_ns = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    rel_ns = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    package_rel_ns = "http://schemas.openxmlformats.org/package/2006/relationships"
    with zipfile.ZipFile(path) as archive:
        shared_strings: list[str] = []
        if "xl/sharedStrings.xml" in archive.namelist():
            root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            for item in root.findall(f"{{{main_ns}}}si"):
                shared_strings.append("".join(node.text or "" for node in item.iter(f"{{{main_ns}}}t")))

        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        relationship_id = None
        for sheet in workbook.findall(f".//{{{main_ns}}}sheet"):
            if sheet.attrib.get("name") == sheet_name:
                relationship_id = sheet.attrib.get(f"{{{rel_ns}}}id")
                break
        if relationship_id is None:
            raise KeyError(f"Sheet not found: {sheet_name}")

        relationships = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        target = None
        for relationship in relationships.findall(f"{{{package_rel_ns}}}Relationship"):
            if relationship.attrib.get("Id") == relationship_id:
                target = relationship.attrib.get("Target")
                break
        if target is None:
            raise KeyError(f"Sheet relationship not found: {sheet_name}")
        normalized_target = target.lstrip("/")
        sheet_path = normalized_target if normalized_target.startswith("xl/") else "xl/" + normalized_target
        root = ET.fromstring(archive.read(sheet_path))

        rows: list[list[Any]] = []
        for row_node in root.findall(f".//{{{main_ns}}}row"):
            row_number = int(row_node.attrib.get("r", len(rows) + 1))
            while len(rows) < row_number:
                rows.append([])
            row_values = rows[row_number - 1]
            for cell in row_node.findall(f"{{{main_ns}}}c"):
                reference = cell.attrib.get("r", "A1")
                letters = "".join(char for char in reference if char.isalpha())
                column = 0
                for char in letters:
                    column = column * 26 + (ord(char.upper()) - 64)
                while len(row_values) < column:
                    row_values.append(None)
                cell_type = cell.attrib.get("t")
                value_node = cell.find(f"{{{main_ns}}}v")
                inline_node = cell.find(f"{{{main_ns}}}is")
                formula_node = cell.find(f"{{{main_ns}}}f")
                raw = value_node.text if value_node is not None else None
                if formula_node is not None:
                    value: Any = "=" + (formula_node.text or "")
                elif cell_type == "s" and raw is not None:
                    value = shared_strings[int(raw)]
                elif cell_type == "inlineStr" and inline_node is not None:
                    value = "".join(node.text or "" for node in inline_node.iter(f"{{{main_ns}}}t"))
                elif cell_type in {"str", "e"}:
                    value = raw
                elif cell_type == "b":
                    value = raw == "1"
                elif raw is None:
                    value = None
                else:
                    numeric = number(raw)
                    value = numeric if numeric is not None else raw
                    if isinstance(value, float) and value.is_integer():
                        value = int(value)
                row_values[column - 1] = value
        return rows


def xlsx_table(path: Path, sheet_name: str, header_row: int, start_row: int, end_row: int) -> list[dict[str, Any]]:
    rows = xlsx_sheet_rows(path, sheet_name)
    headers = rows[header_row - 1]
    output = []
    for row_number in range(start_row, min(end_row, len(rows)) + 1):
        values = rows[row_number - 1]
        record = {
            str(header): (values[index] if index < len(values) else None)
            for index, header in enumerate(headers)
            if header is not None
        }
        output.append(record)
    return output


def cohen_kappa(first: list[str], second: list[str]) -> float | None:
    pairs = [(a, b) for a, b in zip(first, second) if a and b]
    if not pairs:
        return None
    observed = sum(a == b for a, b in pairs) / len(pairs)
    labels = sorted({value for pair in pairs for value in pair})
    first_counts = Counter(a for a, _ in pairs)
    second_counts = Counter(b for _, b in pairs)
    expected = sum((first_counts[label] / len(pairs)) * (second_counts[label] / len(pairs)) for label in labels)
    if expected == 1:
        return 1.0
    return (observed - expected) / (1 - expected)


def analyze_graph() -> dict[str, Any]:
    path = ROOT / "data" / "processed" / "anyang_accessibility_graph.geojson"
    data = read_json(path)
    nodes = [f for f in data["features"] if f.get("properties", {}).get("feature_type") == "node"]
    edges = [f for f in data["features"] if f.get("properties", {}).get("feature_type") == "edge"]
    graph = nx.Graph()
    graph.add_nodes_from(f["properties"]["node_id"] for f in nodes)
    for feature in edges:
        props = feature["properties"]
        graph.add_edge(props["from_node"], props["to_node"], edge_id=props["edge_id"])

    components = sorted((len(component) for component in nx.connected_components(graph)), reverse=True)
    largest_nodes = max(nx.connected_components(graph), key=len) if graph.number_of_nodes() else set()
    largest_graph = graph.subgraph(largest_nodes).copy()
    largest_bridges = list(nx.bridges(largest_graph))
    pair_edge_ids: defaultdict[tuple[str, str], list[str]] = defaultdict(list)
    for feature in edges:
        props = feature["properties"]
        pair_edge_ids[tuple(sorted((props["from_node"], props["to_node"])))].append(props["edge_id"])
    bridge_impacts = []
    for start, end in largest_bridges:
        largest_graph.remove_edge(start, end)
        split_sizes = sorted((len(component) for component in nx.connected_components(largest_graph)), reverse=True)
        largest_graph.add_edge(start, end)
        bridge_impacts.append(
            {
                "edge_id": pair_edge_ids[tuple(sorted((start, end)))][0],
                "smaller_side_node_count": min(split_sizes[:2]),
                "larger_side_node_count": max(split_sizes[:2]),
            }
        )
    bridge_impacts.sort(key=lambda row: row["smaller_side_node_count"], reverse=True)
    lengths = [number(f["properties"].get("length")) for f in edges]
    lengths = [value for value in lengths if value is not None]
    degrees = dict(graph.degree())
    highway = Counter()
    for feature in edges:
        value = feature["properties"].get("highway")
        if isinstance(value, list):
            highway.update(str(item) for item in value)
        elif value:
            highway[str(value)] += 1

    def present(field: str, *, unknown_values: set[Any] | None = None) -> int:
        unknown_values = unknown_values or {None, "", "unknown"}
        return sum(f["properties"].get(field) not in unknown_values for f in edges)

    mapped_edges = [f for f in edges if f["properties"].get("crosswalk_samples")]
    demo = data.get("metadata", {}).get("demo", {}).get("expected", {})
    standard = number(demo.get("standard", {}).get("distance_m"))
    accessible_before = number(demo.get("accessible_before", {}).get("distance_m"))
    accessible_after = number(demo.get("accessible_after", {}).get("distance_m"))

    return {
        "path": str(path.relative_to(ROOT)),
        "sha256": sha256(path),
        "metadata": data.get("metadata", {}),
        "node_count": len(nodes),
        "edge_count": len(edges),
        "total_edge_length_m": round(sum(lengths), 3),
        "edge_length_m": describe(lengths),
        "topology": {
            "connected_component_count": len(components),
            "simple_node_pair_edge_count": graph.number_of_edges(),
            "parallel_extra_edge_count": len(edges) - graph.number_of_edges(),
            "largest_component_nodes": components[0] if components else 0,
            "largest_component_pct": pct(components[0], len(nodes)) if components else None,
            "component_sizes": components,
            "average_degree": round(statistics.fmean(degrees.values()), 3) if degrees else None,
            "median_degree": statistics.median(degrees.values()) if degrees else None,
            "degree_one_node_count": sum(value == 1 for value in degrees.values()),
            "degree_zero_node_count": sum(value == 0 for value in degrees.values()),
            "max_degree": max(degrees.values()) if degrees else None,
            "articulation_point_count_all_components": len(list(nx.articulation_points(graph))),
            "bridge_node_pair_count_all_components": len(list(nx.bridges(graph))),
            "articulation_point_count_largest_component": len(list(nx.articulation_points(largest_graph))),
            "bridge_node_pair_count_largest_component": len(largest_bridges),
            "largest_bridge_impacts": bridge_impacts[:10],
        },
        "edge_attributes": {
            "verified_count": sum(bool(f["properties"].get("verified")) for f in edges),
            "accessibility_status": counts((f["properties"] for f in edges), "accessibility_status"),
            "source": counts((f["properties"] for f in edges), "source"),
            "accessibility_source": counts((f["properties"] for f in edges), "accessibility_source"),
            "highway_top15": dict(highway.most_common(15)),
            "display_name_present_count": present("name", unknown_values={None, ""}),
            "non_fallback_name_count": sum(
                bool(f["properties"].get("name"))
                and f["properties"].get("name") != "OSM 보행 구간"
                for f in edges
            ),
            "surface_known_count": present("surface"),
            "slope_known_count": present("slope"),
            "width_known_count": present("width"),
            "curb_height_known_count": present("curb_height"),
            "wheelchair_accessible_known_count": present("wheelchair_accessible", unknown_values={None, "", "unknown"}),
            "stairs_count": sum(bool(f["properties"].get("stairs")) for f in edges),
            "blocked_count": sum(bool(f["properties"].get("blocked")) for f in edges),
            "demo_editable_count": sum(bool(f["properties"].get("demo_editable")) for f in edges),
            "crosswalk_mapped_edge_count": len(mapped_edges),
            "crosswalk_sample_references": sum(len(f["properties"].get("crosswalk_samples", [])) for f in mapped_edges),
        },
        "demo_route_effect": {
            "standard_distance_m": standard,
            "accessible_before_distance_m": accessible_before,
            "accessible_after_block_distance_m": accessible_after,
            "accessible_before_vs_standard_delta_m": round(accessible_before - standard, 3) if standard is not None and accessible_before is not None else None,
            "accessible_before_vs_standard_delta_pct": pct(accessible_before - standard, standard) if standard is not None and accessible_before is not None else None,
            "block_vs_accessible_before_delta_m": round(accessible_after - accessible_before, 3) if accessible_before is not None and accessible_after is not None else None,
            "block_vs_accessible_before_delta_pct": pct(accessible_after - accessible_before, accessible_before) if accessible_before is not None and accessible_after is not None else None,
            "block_vs_standard_delta_pct": pct(accessible_after - standard, standard) if standard is not None and accessible_after is not None else None,
        },
    }


def analyze_crosswalks() -> dict[str, Any]:
    raw_path = next((ROOT / "data" / "raw" / "anyang" / "crosswalks" / "2026").glob("*.csv"))
    raw = read_csv(raw_path)
    curb = Counter((row.get("보도턱낮춤여부") or "(blank)") for row in raw)
    tactile = Counter((row.get("점자블록유무") or "(blank)") for row in raw)
    rows_with_any_unknown = sum(not row.get("보도턱낮춤여부") or not row.get("점자블록유무") for row in raw)
    widths = [number(row.get("횡단보도폭")) for row in raw]
    lengths = [number(row.get("횡단보도길이")) for row in raw]
    selected = read_csv(PACKAGE / "selected_crosswalks_40.csv")
    snap = [number(row.get("osm_snap_distance_m")) for row in selected]
    corridor_distance = [number(row.get("corridor_distance_m")) for row in selected]
    chainage = [number(row.get("corridor_chainage_m")) for row in selected]
    corridor_length = 1377.3
    proxy_counts = Counter(row.get("osm_proxy_edge_id") or "(blank)" for row in selected)

    return {
        "raw_citywide": {
            "path": str(raw_path.relative_to(ROOT)),
            "sha256": sha256(raw_path),
            "row_count": len(raw),
            "unique_management_id_count": len({row.get("관리번호") for row in raw}),
            "curb_lowering": dict(curb),
            "tactile_block": dict(tactile),
            "rows_with_any_unknown": rows_with_any_unknown,
            "rows_with_any_unknown_pct": pct(rows_with_any_unknown, len(raw)),
            "curb_known_pct": pct(len(raw) - curb.get("(blank)", 0), len(raw)),
            "tactile_known_pct": pct(len(raw) - tactile.get("(blank)", 0), len(raw)),
            "width_m": describe(value for value in widths if value is not None),
            "length_m": describe(value for value in lengths if value is not None),
            "zero_dimension_row_count": sum(
                width == 0 and length == 0
                for width, length in zip(widths, lengths)
            ),
            "zero_dimension_row_pct": pct(
                sum(width == 0 and length == 0 for width, length in zip(widths, lengths)),
                len(raw),
            ),
            "administrative_area_top10": dict(Counter(row.get("관할지역") or "(blank)" for row in raw).most_common(10)),
        },
        "representative_sample": {
            "row_count": len(selected),
            "share_of_citywide_pct": pct(len(selected), len(raw), 3),
            "public_state": counts(selected, "public_state"),
            "geometry_quality": counts(selected, "geometry_quality"),
            "double_review_crosswalk_count": sum(truthy(row.get("double_review_crosswalk")) for row in selected),
            "crosswalk_width_m": describe(number(row.get("crosswalk_width_m")) for row in selected),
            "crosswalk_length_m": describe(number(row.get("crosswalk_length_m")) for row in selected),
            "osm_snap_distance_m": describe(value for value in snap if value is not None),
            "snap_over_5m_count": sum(value is not None and value > 5 for value in snap),
            "snap_over_10m_count": sum(value is not None and value > 10 for value in snap),
            "corridor_distance_m": describe(value for value in corridor_distance if value is not None),
            "within_30m_of_corridor_count": sum(value is not None and value <= 30 for value in corridor_distance),
            "over_100m_from_corridor_count": sum(value is not None and value > 100 for value in corridor_distance),
            "chainage_quarter_counts": {
                "Q1": sum(value is not None and 0 <= value <= corridor_length / 4 for value in chainage),
                "Q2": sum(value is not None and corridor_length / 4 < value <= corridor_length / 2 for value in chainage),
                "Q3": sum(value is not None and corridor_length / 2 < value <= 3 * corridor_length / 4 for value in chainage),
                "Q4": sum(value is not None and 3 * corridor_length / 4 < value <= corridor_length + 0.1 for value in chainage),
            },
            "exact_endpoint_chainage_count": sum(
                value is not None and (value == 0 or value >= corridor_length)
                for value in chainage
            ),
            "unique_proxy_edge_count": len(proxy_counts),
            "reused_proxy_edge_count": sum(value > 1 for value in proxy_counts.values()),
            "max_crosswalks_on_one_proxy_edge": max(proxy_counts.values()) if proxy_counts else 0,
            "proxy_edge_top10": dict(proxy_counts.most_common(10)),
        },
    }


def analyze_mvp_package_inventory() -> dict[str, Any]:
    geojson_path = PACKAGE / "onway_anyang_corridor_mvp.geojson"
    geojson = read_json(geojson_path)
    feature_types = Counter(
        feature.get("properties", {}).get("feature_type", "(blank)")
        for feature in geojson.get("features", [])
    )
    geometry_types = Counter(
        feature.get("geometry", {}).get("type", "(blank)")
        for feature in geojson.get("features", [])
    )
    workbook_copy = ROOT / "docs" / "ONWAY_안양_대표회랑_MVP_20260915 (1).xlsx"
    workbook_package = PACKAGE / "ONWAY_안양_대표회랑_MVP_20260915.xlsx"
    return {
        "geojson_feature_count": len(geojson.get("features", [])),
        "geojson_feature_types": dict(feature_types),
        "geojson_geometry_types": dict(geometry_types),
        "workbook_copy_sha256": sha256(workbook_copy),
        "workbook_package_sha256": sha256(workbook_package),
        "workbook_files_are_identical": sha256(workbook_copy) == sha256(workbook_package),
        "double_counting_rule": "The two MVP workbook paths are byte-identical and count as one data source.",
    }


def analyze_ai_precheck() -> dict[str, Any]:
    rows = read_csv(PACKAGE / "ai_precheck_80.csv")
    approaches = read_csv(PACKAGE / "approaches_80_review_queue.csv")
    double_rows = [row for row in rows if row.get("pass2_result")]
    first = [row.get("pass1_result", "") for row in double_rows]
    second = [row.get("pass2_result", "") for row in double_rows]
    paired_by_sample: defaultdict[str, list[str]] = defaultdict(list)
    for row in rows:
        paired_by_sample[row.get("sample_id", "")].append(row.get("final_ai_precheck_result", ""))
    paired_agreement = sum(len(values) == 2 and values[0] == values[1] for values in paired_by_sample.values())
    endpoint_patterns = Counter(
        " / ".join(values)
        for _, values in sorted(paired_by_sample.items())
        if len(values) == 2
    )
    confidences = [number(row.get("ai_confidence")) for row in rows]
    evidence_dates = []
    for row in rows:
        value = row.get("evidence_shot_date")
        if value:
            evidence_dates.append(datetime.fromisoformat(value))
    pano = [number(row.get("pano_distance_m")) for row in rows]

    confidence_by_result: dict[str, dict[str, Any]] = {}
    for label in sorted({row.get("final_ai_precheck_result", "(blank)") for row in rows}):
        values = [number(row.get("ai_confidence")) for row in rows if row.get("final_ai_precheck_result", "(blank)") == label]
        confidence_by_result[label] = describe(value for value in values if value is not None)

    return {
        "contract_status": "legacy_combined_pass_block_result; current v3 workbook marks this result as discontinued",
        "approach_count": len(rows),
        "crosswalk_count": len(paired_by_sample),
        "final_result": counts(rows, "final_ai_precheck_result"),
        "candidate_label": counts(rows, "ai_candidate_label"),
        "human_review_required": counts(rows, "human_review_required"),
        "human_approved_count": sum(bool((row.get("ai_human_approved") or "").strip()) for row in rows),
        "official_c_effect": counts(rows, "official_c_effect"),
        "confidence": describe(value for value in confidences if value is not None),
        "confidence_value_counts": dict(sorted(Counter(value for value in confidences if value is not None).items())),
        "confidence_by_result": confidence_by_result,
        "double_review": {
            "pair_count": len(double_rows),
            "agreement_count": sum(a == b for a, b in zip(first, second)),
            "agreement_pct": pct(sum(a == b for a, b in zip(first, second)), len(double_rows)),
            "cohen_kappa": round(cohen_kappa(first, second) or 0.0, 4),
            "disagreements": [
                {
                    "approach_id": row.get("approach_id"),
                    "pass1": row.get("pass1_result"),
                    "pass2": row.get("pass2_result"),
                }
                for row in double_rows
                if row.get("pass1_result") != row.get("pass2_result")
            ],
        },
        "paired_endpoint_result_agreement": {
            "same_result_crosswalk_count": paired_agreement,
            "same_result_pct": pct(paired_agreement, len(paired_by_sample)),
            "ordered_a_b_patterns": dict(endpoint_patterns),
        },
        "roadview_evidence": {
            "pano_distance_m": describe(value for value in pano if value is not None),
            "over_10m_count": sum(value is not None and value > 10 for value in pano),
            "over_20m_count": sum(value is not None and value > 20 for value in pano),
            "earliest_shot": min(evidence_dates).isoformat(sep=" ") if evidence_dates else None,
            "latest_shot": max(evidence_dates).isoformat(sep=" ") if evidence_dates else None,
        },
        "human_review_queue": {
            "review_status": counts(approaches, "review_status"),
            "reviewer_1_completed": sum(bool((row.get("reviewer_1") or "").strip()) for row in approaches),
            "reviewer_2_completed": sum(bool((row.get("reviewer_2") or "").strip()) for row in approaches),
            "adjudicated_count": sum(bool((row.get("adjudication") or "").strip()) for row in approaches),
            "double_review_required_approach_count": sum(truthy(row.get("double_review_required")) for row in approaches),
        },
    }


def analyze_routes() -> dict[str, Any]:
    rows = read_csv(PACKAGE / "route_comparison_10od_abc.csv")
    by_mode = {mode: [row for row in rows if row.get("mode") == mode] for mode in ("A", "B", "C")}
    summaries: dict[str, Any] = {}
    for mode, mode_rows in by_mode.items():
        route_distances = [number(row.get("route_distance_m")) for row in mode_rows]
        direct_distances = [number(row.get("direct_distance_m")) for row in mode_rows]
        cost = [number(row.get("weighted_cost_m")) for row in mode_rows]
        circuity = [route / direct for route, direct in zip(route_distances, direct_distances) if route is not None and direct]
        summaries[mode] = {
            "od_count": len(mode_rows),
            "route_distance_m": describe(value for value in route_distances if value is not None),
            "weighted_cost_m": describe(value for value in cost if value is not None),
            "circuity_ratio": describe(circuity),
            "unknown_proxy_edges_used_total": sum(int(number(row.get("unknown_proxy_edges_used")) or 0) for row in mode_rows),
            "public_blocked_edges_used_total": sum(int(number(row.get("public_blocked_edges_used")) or 0) for row in mode_rows),
        }

    b_rows = by_mode["B"]
    changed = [row for row in b_rows if truthy(row.get("route_changed_vs_A"))]
    all_delta_pct = [number(row.get("distance_delta_vs_A_pct")) for row in b_rows]
    changed_delta_pct = [number(row.get("distance_delta_vs_A_pct")) for row in changed]
    c_by_od = {row["od_id"]: row for row in by_mode["C"]}
    b_equals_c = all(
        row.get("route_distance_m") == c_by_od[row["od_id"]].get("route_distance_m")
        and row.get("weighted_cost_m") == c_by_od[row["od_id"]].get("weighted_cost_m")
        and row.get("unknown_proxy_edges_used") == c_by_od[row["od_id"]].get("unknown_proxy_edges_used")
        for row in b_rows
    )

    scenario_rows = read_csv(PACKAGE / "route_comparison_ai_candidate_scenario.csv")
    scenario_changed = [row for row in scenario_rows if truthy(row.get("route_changed_vs_b"))]
    scenario_delta = [number(row.get("distance_delta_vs_b_pct")) for row in scenario_rows]
    ranked = sorted(
        (
            {
                "od_id": row.get("od_id"),
                "distance_delta_vs_b_m": number(row.get("distance_delta_vs_b_m")),
                "distance_delta_vs_b_pct": number(row.get("distance_delta_vs_b_pct")),
                "candidate_edges_used_by_b": int(number(row.get("candidate_edges_used_by_b")) or 0),
            }
            for row in scenario_rows
        ),
        key=lambda row: row["distance_delta_vs_b_pct"] or 0,
        reverse=True,
    )

    return {
        "legacy_abc_diagnostic_only": {
            "current_v3_use_allowed": False,
            "reason": "The v3 review workbook discontinues these values because blank-weight, profile mixing, and centerline-proxy blocking confound the effect.",
            "mode_summary": summaries,
            "b_vs_a": {
                "changed_route_count": len(changed),
                "changed_route_pct": pct(len(changed), len(b_rows)),
                "distance_delta_pct_all_od": describe(value for value in all_delta_pct if value is not None),
                "distance_delta_pct_changed_od": describe(value for value in changed_delta_pct if value is not None),
                "distance_delta_m_total": round(sum(number(row.get("distance_delta_vs_A_m")) or 0 for row in b_rows), 3),
                "weighted_cost_delta_m_total": round(sum(number(row.get("cost_delta_vs_A_m")) or 0 for row in b_rows), 3),
                "unknown_proxy_edges_reduction_total": summaries["A"]["unknown_proxy_edges_used_total"] - summaries["B"]["unknown_proxy_edges_used_total"],
            },
            "official_c_equals_b": b_equals_c,
            "approved_ai_block_edges_total": sum(int(number(row.get("approved_ai_block_edges")) or 0) for row in by_mode["C"]),
        },
        "legacy_unofficial_cstar_diagnostic_only": {
            "current_v3_use_allowed": False,
            "reason": "The v3 review workbook prohibits submission and route-guidance use until profile-specific rules, dedicated crossing edges, and human review are complete.",
            "od_count": len(scenario_rows),
            "route_changed_count": len(scenario_changed),
            "route_changed_pct": pct(len(scenario_changed), len(scenario_rows)),
            "unavailable_count": sum(not truthy(row.get("cstar_route_available")) for row in scenario_rows),
            "distance_delta_pct": describe(value for value in scenario_delta if value is not None),
            "distance_delta_m_total": round(sum(number(row.get("distance_delta_vs_b_m")) or 0 for row in scenario_rows), 3),
            "ranked_od_impact": ranked,
        },
    }


def analyze_review_workbook_v3() -> dict[str, Any]:
    path = ROOT / "docs" / "ONWAY_안양_통합검수_v3_구조수정.xlsx"
    ai_rows = xlsx_table(path, "AI 사전판독", 6, 7, 86)
    review_rows = xlsx_table(path, "검수 대장", 6, 7, 86)
    video_rows = xlsx_table(path, "영상 근거", 6, 7, 166)
    correction_rows = xlsx_table(path, "위치보정 큐", 6, 7, 32)
    hogye_rows = xlsx_table(path, "호계1동 후보", 6, 7, 16)
    legacy_route_rows = xlsx_table(path, "경로 비교", 13, 14, 43)
    legacy_cstar_rows = xlsx_table(path, "C* 민감도", 13, 14, 23)

    return {
        "path": str(path.relative_to(ROOT)),
        "sha256": sha256(path),
        "status": "current_review_contract; human and field review incomplete",
        "ai_profile_recode": {
            "approach_count": len(ai_rows),
            "wheelchair_candidate": counts(ai_rows, "휠체어 판정 후보"),
            "visual_impairment_candidate": counts(ai_rows, "시각장애 판정 후보"),
            "hard_block_possible": counts(ai_rows, "하드차단 가능"),
            "temporality": counts(ai_rows, "시간성"),
            "submission_use": counts(ai_rows, "제출 사용"),
            "candidate_label": counts(ai_rows, "AI 후보 라벨"),
            "priority_score_rule_values": counts(ai_rows, "검수 우선순위 점수(규칙값)"),
            "human_approved_count": sum(bool(row.get("AI 사람승인")) for row in ai_rows),
            "official_c_applied_count": sum(
                bool(row.get("공식 C 반영")) and "미반영" not in str(row.get("공식 C 반영"))
                for row in ai_rows
            ),
        },
        "human_review": {
            "approach_count": len(review_rows),
            "reviewer_1_completed": sum(bool(row.get("검수자 1")) for row in review_rows),
            "result_1_completed": sum(row.get("결과 1") in {"pass", "block", "unknown"} for row in review_rows),
            "reviewer_2_completed": sum(bool(row.get("검수자 2")) for row in review_rows),
            "result_2_completed": sum(row.get("결과 2") in {"pass", "block", "unknown"} for row in review_rows),
            "adjudication_completed": sum(bool(row.get("최종 조정")) for row in review_rows),
            "selected_video_1_count": sum(bool(row.get("채택 영상 1")) for row in review_rows),
            "selected_video_2_count": sum(bool(row.get("채택 영상 2")) for row in review_rows),
            "route_update_allowed": counts(review_rows, "경로 반영 가능"),
            "submission_status": counts(review_rows, "제출 상태"),
        },
        "video_evidence": {
            "row_count": len(video_rows),
            "provider": counts(video_rows, "영상원"),
            "confirmed_url_count": sum(bool(row.get("확정 거리뷰 URL")) for row in video_rows),
            "confirmed_url_by_provider": {
                provider: sum(
                    row.get("영상원") == provider and bool(row.get("확정 거리뷰 URL"))
                    for row in video_rows
                )
                for provider in ("네이버", "카카오")
            },
            "shot_date_count": sum(bool(row.get("촬영일")) for row in video_rows),
            "human_result_1_count": sum(row.get("영상 판정 1") in {"pass", "block", "unknown"} for row in video_rows),
            "human_result_2_count": sum(row.get("영상 판정 2") in {"pass", "block", "unknown"} for row in video_rows),
            "record_source": counts(video_rows, "기록 출처"),
        },
        "location_correction": {
            "candidate_count": len(correction_rows),
            "status": counts(correction_rows, "상태"),
            "corrected_coordinate_count": sum(
                row.get("보정 위도") is not None and row.get("보정 경도") is not None
                for row in correction_rows
            ),
        },
        "hogye1_public_candidates": {
            "candidate_count": len(hogye_rows),
            "curb_lowering": counts(hogye_rows, "보도턱낮춤"),
            "tactile_block": counts(hogye_rows, "점자블록"),
            "priority_review": counts(hogye_rows, "우선 검토"),
            "verification_status": counts(hogye_rows, "검증 상태"),
        },
        "legacy_route_sheets": {
            "abc_row_count": len(legacy_route_rows),
            "abc_use_status": counts(legacy_route_rows, "사용 상태"),
            "cstar_row_count": len(legacy_cstar_rows),
            "cstar_use_status": counts(legacy_cstar_rows, "사용 상태"),
            "discontinued_reasons": [
                "The 1.15 blank-value weight, rather than explicit barriers, caused all five legacy B route changes.",
                "The legacy profile mixed tactile-paving absence into wheelchair blocking.",
                "Blocking an OSM centerline proxy overstates detours and causes shared-segment conflicts.",
            ],
        },
        "new_route_recalculation_gate": {
            "profile_specific_policy": "defined",
            "dedicated_crossing_edge_ids": 40,
            "dedicated_crossing_edges_connected_to_routable_sidewalk_graph": 0,
            "location_corrections_completed": sum(row.get("상태") == "완료" for row in correction_rows),
            "location_corrections_required": len(correction_rows),
            "first_human_reviews_completed": sum(row.get("결과 1") in {"pass", "block", "unknown"} for row in review_rows),
            "first_human_reviews_required": 80,
            "second_human_reviews_completed": sum(row.get("결과 2") in {"pass", "block", "unknown"} for row in review_rows),
            "second_human_reviews_required": 40,
            "five_ai_candidate_decisions_completed": sum(bool(row.get("AI 사람승인")) for row in review_rows),
            "five_ai_candidate_decisions_required": 5,
            "imagery_rights_and_currency": "unconfirmed",
            "current_route_result": "not calculated; the workbook intentionally leaves the new A0/B0-W/B0-V/B-lambda/C outputs blank",
        },
    }


def analyze_topographic() -> dict[str, Any]:
    metrics = read_json(EVAL / "topographic_map" / "metrics.json")
    match_features = read_json(EVAL / "topographic_map" / "matches.geojson")["features"]
    by_code: defaultdict[str, Counter[str]] = defaultdict(Counter)
    for feature in match_features:
        props = feature["properties"]
        by_code[props.get("source_feature_code", "(blank)")][props.get("match_status", "(blank)")] += 1

    code_totals = metrics["metrics"]["feature_counts_by_code_in_context"]
    code_roles = {
        "A0033320": "pedestrian_area",
        "A0043325": "crossing_candidate",
        "A0063321": "grade_separated_crossing_candidate",
        "C0390000": "stairs_candidate",
        "C0463374": "underground_entrance_candidate",
    }
    by_role: defaultdict[str, Counter[str]] = defaultdict(Counter)
    for code, total in code_totals.items():
        counter = by_code[code]
        counter["unmatched"] = total - counter.get("unique", 0) - counter.get("ambiguous", 0)
        by_role[code_roles[code]].update(counter)

    def rates(grouped: dict[str, Counter[str]]) -> dict[str, Any]:
        output = {}
        for label, counter in sorted(grouped.items()):
            total = sum(counter.values())
            output[label] = {
                "total": total,
                **dict(counter),
                "unique_pct": pct(counter.get("unique", 0), total),
                "ambiguous_pct": pct(counter.get("ambiguous", 0), total),
                "unmatched_pct": pct(counter.get("unmatched", 0), total),
            }
        return output

    return {
        "status": metrics["status"],
        "inventory": metrics["inventory"],
        "metrics": metrics["metrics"],
        "match_rates_by_code": rates(by_code),
        "match_rates_by_role": rates(by_role),
        "unmatched_promoted_to_new_object_candidate_count": metrics["metrics"]["new_object_candidate_count"],
        "unmatched_not_in_new_object_candidate_package_count": (
            metrics["metrics"]["unmatched_count"] - metrics["metrics"]["new_object_candidate_count"]
        ),
        "decision": "human_review_required_below_80pct_unique_match_gate",
        "policy": metrics["policy"],
    }


def analyze_dem() -> dict[str, Any]:
    metrics = read_json(EVAL / "dem" / "metrics.json")
    rows = read_csv(EVAL / "dem" / "edge_slope_candidates.csv")
    slope = [number(row.get("slope_pct_abs_candidate")) for row in rows]
    endpoint_difference = [number(row.get("nearest_bilinear_endpoint_max_diff_m")) for row in rows]
    return {
        "status": metrics["status"],
        "source": metrics["source"],
        "metrics": metrics["metrics"],
        "descriptive_screening_only": {
            "abs_slope_pct": describe(value for value in slope if value is not None),
            "edges_over_5pct": sum(value is not None and value > 5 for value in slope),
            "edges_over_8_33pct": sum(value is not None and value > 8.33 for value in slope),
            "edges_over_12pct": sum(value is not None and value > 12 for value in slope),
            "endpoint_interpolation_difference_m": describe(value for value in endpoint_difference if value is not None),
        },
        "policy": metrics["policy"],
    }


def analyze_cross_sources() -> dict[str, Any]:
    metrics = read_json(EVAL / "cross_sources" / "metrics.json")
    public_features = read_json(EVAL / "cross_sources" / "crosswalk_correspondence.geojson")["features"]
    distances = [number(f["properties"].get("hd_distance_m")) for f in public_features]
    graph_distances = [number(f["properties"].get("graph_distance_m")) for f in public_features]
    return {
        "status": metrics["status"],
        "metrics": metrics["metrics"],
        "hd_context_mapping_rates": {
            role: {
                **values,
                "unique_pct": pct(values.get("unique", 0), sum(values.values())),
            }
            for role, values in metrics["metrics"]["hd_graph_mapping_counts"].items()
        },
        "public_crosswalk_unknown_accessibility_pct": pct(
            metrics["metrics"]["rows_with_unknown_accessibility_count"],
            metrics["metrics"]["public_crosswalk_context_count"],
        ),
        "hd_distance_m_available": describe(value for value in distances if value is not None),
        "graph_distance_m": describe(value for value in graph_distances if value is not None),
        "decision": metrics["decision"],
        "policy": metrics["policy"],
    }


def analyze_orthophoto() -> dict[str, Any]:
    metrics = read_json(EVAL / "orthophoto" / "metrics.json")
    return {
        "status": metrics["status"],
        "metrics": metrics["metrics"],
        "decision": metrics["decision"],
        "policy": metrics["policy"],
    }


def analyze_review_queue() -> dict[str, Any]:
    rows = read_csv(EVAL / "review_queue.csv")
    edge_counts = Counter(row.get("graph_edge_id") for row in rows if row.get("graph_edge_id"))
    by_source_role: defaultdict[str, Counter[str]] = defaultdict(Counter)
    by_source_mapping: defaultdict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        by_source_role[row.get("review_source", "(blank)")][row.get("review_role", "(blank)")] += 1
        by_source_mapping[row.get("review_source", "(blank)")][row.get("mapping_status", "(blank)")] += 1
    grid: defaultdict[tuple[int, int], list[dict[str, Any]]] = defaultdict(list)
    reference_latitude = 37.397
    metres_per_degree_lon = 111_320 * math.cos(math.radians(reference_latitude))
    for row in rows:
        lon = number(row.get("longitude"))
        lat = number(row.get("latitude"))
        if lon is None or lat is None:
            continue
        cell = (math.floor(lon * metres_per_degree_lon / 100), math.floor(lat * 111_320 / 100))
        grid[cell].append(row)
    hotspots = []
    for cell_rows in sorted(grid.values(), key=len, reverse=True)[:10]:
        hotspots.append(
            {
                "candidate_count": len(cell_rows),
                "centroid_lon": round(statistics.fmean(number(row["longitude"]) or 0 for row in cell_rows), 6),
                "centroid_lat": round(statistics.fmean(number(row["latitude"]) or 0 for row in cell_rows), 6),
                "source_counts": dict(Counter(row["review_source"] for row in cell_rows)),
            }
        )
    return {
        "candidate_count": len(rows),
        "review_status": counts(rows, "review_status"),
        "derived_true_count": sum(truthy(row.get("derived")) for row in rows),
        "verified_true_count": sum(truthy(row.get("verified")) for row in rows),
        "graph_update_allowed_true_count": sum(truthy(row.get("graph_update_allowed")) for row in rows),
        "by_source": counts(rows, "review_source"),
        "by_source_role": {key: dict(value) for key, value in sorted(by_source_role.items())},
        "by_source_mapping": {key: dict(value) for key, value in sorted(by_source_mapping.items())},
        "candidate_with_graph_edge_count": sum(bool(row.get("graph_edge_id")) for row in rows),
        "unique_graph_edge_count": len(edge_counts),
        "top_candidate_edges": dict(edge_counts.most_common(15)),
        "top10_edge_candidate_share_pct": pct(sum(value for _, value in edge_counts.most_common(10)), len(rows)),
        "approximate_100m_grid_hotspots": hotspots,
    }


def analyze_validation() -> dict[str, Any]:
    summary = read_json(EVAL / "evaluation_summary.json")
    common = summary["results"]["common_validation"]
    warnings = []
    holds = []
    for target in [common.get("graph", {})] + common.get("sources", []):
        for check in target.get("checks", []):
            record = {
                "dataset_id": target.get("dataset_id", "baseline_graph"),
                "code": check.get("code"),
                "message": check.get("message"),
                "evidence": check.get("evidence"),
            }
            if check.get("status") == "warning":
                warnings.append(record)
            elif check.get("status") == "hold":
                holds.append(record)
    return {
        "created_at": summary["created_at"],
        "status": summary["status"],
        "graph": summary["graph"],
        "check_summary": common["summary"],
        "warnings": warnings,
        "holds": holds,
        "policy": common["policy"],
    }


def analyze_runtime_db() -> dict[str, Any]:
    output: dict[str, Any] = {}
    for path in sorted((ROOT / "data" / "runtime").glob("*.db")):
        connection = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
        connection.row_factory = sqlite3.Row
        table_names = [
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
            if not row[0].startswith("sqlite_")
        ]
        tables: dict[str, Any] = {}
        for table in table_names:
            row_count = connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
            columns = [row[1] for row in connection.execute(f'PRAGMA table_info("{table}")')]
            entry: dict[str, Any] = {"row_count": row_count, "columns": columns}
            if "status" in columns:
                entry["status_counts"] = {
                    str(row[0]): row[1]
                    for row in connection.execute(f'SELECT status, COUNT(*) FROM "{table}" GROUP BY status')
                }
            if "verified" in columns:
                entry["verified_counts"] = {
                    str(row[0]): row[1]
                    for row in connection.execute(f'SELECT verified, COUNT(*) FROM "{table}" GROUP BY verified')
                }
            if table == "observation_candidates":
                source_counts: Counter[str] = Counter()
                verified_counts: Counter[str] = Counter()
                candidate_ids = []
                for row in connection.execute(
                    'SELECT candidate_id, payload_json FROM "observation_candidates" ORDER BY candidate_id'
                ):
                    payload = json.loads(row["payload_json"])
                    source_counts[str(payload.get("source", "(blank)"))] += 1
                    verified_counts[str(payload.get("verified", False)).lower()] += 1
                    candidate_ids.append(row["candidate_id"])
                entry["payload_source_counts"] = dict(source_counts)
                entry["payload_verified_counts"] = dict(verified_counts)
                entry["candidate_ids"] = candidate_ids
            if table == "edge_status_history":
                entry["actor_source_counts"] = [
                    {"actor": row[0], "source": row[1], "count": row[2]}
                    for row in connection.execute(
                        'SELECT actor, source, COUNT(*) FROM "edge_status_history" '
                        'GROUP BY actor, source ORDER BY COUNT(*) DESC'
                    )
                ]
            if table == "route_sessions":
                row = connection.execute(
                    'SELECT MIN(created_at), MAX(created_at) FROM "route_sessions"'
                ).fetchone()
                entry["created_at_min"] = row[0]
                entry["created_at_max"] = row[1]
            tables[table] = entry
        connection.close()
        output[path.name] = {
            "bytes": path.stat().st_size,
            "last_modified": datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat(),
            "tables": tables,
        }
    return output


def analyze_ai_ar_availability() -> dict[str, Any]:
    telemetry_path = ROOT / "data" / "ai-evaluation" / "fixtures" / "synthetic-telemetry.csv"
    rows = read_csv(telemetry_path)
    frame_times = [number(row.get("frame_time_ms")) for row in rows]
    report_files = list((ROOT / "artifacts").rglob("*-report.json")) if (ROOT / "artifacts").exists() else []
    metrics_files = list((ROOT / "artifacts").rglob("*-metrics.csv")) if (ROOT / "artifacts").exists() else []
    frame_files = list((ROOT / "artifacts").rglob("*-frames.csv")) if (ROOT / "artifacts").exists() else []
    report_summaries = []
    for path in sorted(report_files):
        report = read_json(path)
        evaluation = report.get("evaluation", {})
        latency = evaluation.get("latency", {})
        dataset_id = report.get("datasetId") or report.get("dataset_id") or ""
        synthetic = dataset_id.startswith("synthetic") or any(
            "synthetic" in str(frame.get("context", {}).get("message", "")).lower()
            for frame in evaluation.get("frames", [])
        )
        report_summaries.append(
            {
                "dataset_id": dataset_id,
                "synthetic": synthetic,
                "frame_count": evaluation.get("frameCount"),
                "failed_frame_count": len(evaluation.get("failedFrames", [])),
                "annotated_instance_count": evaluation.get("tracking", {}).get("annotatedInstances"),
                "latency_p50_ms": latency.get("p50Millis"),
                "latency_p95_ms": latency.get("p95Millis"),
                "latency_max_ms": latency.get("maxMillis"),
            }
        )
    determinism_files = list((ROOT / "artifacts").rglob("determinism.json")) if (ROOT / "artifacts").exists() else []
    determinism = [read_json(path) for path in sorted(determinism_files)]
    real_reports = [report for report in report_summaries if not report["synthetic"]]
    synthetic_reports = [report for report in report_summaries if report["synthetic"]]
    return {
        "synthetic_fixture": {
            "row_count": len(rows),
            "duration_ms": (number(rows[-1].get("elapsed_realtime_ms")) or 0) - (number(rows[0].get("elapsed_realtime_ms")) or 0) if rows else None,
            "frame_time_ms": describe(value for value in frame_times if value is not None),
            "tracking_quality": counts(rows, "tracking_quality"),
            "depth_active_true_count": sum(truthy(row.get("depth_active")) for row in rows),
            "route_aligned_true_count": sum(truthy(row.get("route_aligned")) for row in rows),
        },
        "synthetic_offline_reports_found": len(synthetic_reports),
        "synthetic_report_summaries": synthetic_reports,
        "determinism_comparisons": {
            "count": len(determinism),
            "identical_prediction_count": sum(bool(item.get("identical_predictions")) for item in determinism),
            "compared_case_count_total": sum(int(item.get("compared_case_count", 0)) for item in determinism),
        },
        "real_offline_reports_found": len(real_reports),
        "offline_metrics_files_found_all_synthetic": len(metrics_files),
        "offline_frame_files_found_all_synthetic": len(frame_files),
        "reportable_when_real_data_arrives": [
            "overall_and_class_precision_recall_f1",
            "small_medium_large_object_recall",
            "tracking_depth_route_alignment_strata",
            "p50_p95_max_inference_latency",
            "failed_frame_rate",
            "track_id_switches_and_track_length",
            "segmentation_iou_dice_pixel_recall",
            "session_weather_lighting_device_comparison",
            "twenty_minute_fps_temperature_throttling",
        ],
        "current_conclusion": (
            "Only synthetic three-frame emulator reports are present. They demonstrate pipeline execution and prediction determinism, "
            "not field accuracy or device performance. No real detector or AR field-run report is present."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON")
    args = parser.parse_args()

    run_manifest = read_json(PACKAGE / "run_manifest.json")
    result = {
        "analysis_generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": "current repository data, read-only",
        "source_vintages": {
            "osm_as_of": read_json(ROOT / "data" / "raw" / "anyang_corridor_walk_20260915.metadata.json").get("as_of"),
            "public_crosswalk_as_of": read_json(ROOT / "data" / "raw" / "anyang" / "crosswalks" / "2026" / "source_manifest.json").get("data_as_of"),
            "topographic_map_years": [2022, 2025],
            "dem_year": 2025,
            "orthophoto_year": 2025,
            "hd_map_year": 2023,
            "roadview_shot_range_note": "computed in ai_precheck.roadview_evidence",
        },
        "integrity_and_validation": analyze_validation(),
        "graph": analyze_graph(),
        "crosswalks": analyze_crosswalks(),
        "mvp_package_inventory": analyze_mvp_package_inventory(),
        "ai_precheck": analyze_ai_precheck(),
        "routes": analyze_routes(),
        "current_v3_review_workbook": analyze_review_workbook_v3(),
        "spatial_sources": {
            "topographic_map": analyze_topographic(),
            "dem": analyze_dem(),
            "orthophoto": analyze_orthophoto(),
            "hd_map_and_public_crosswalk": analyze_cross_sources(),
        },
        "review_queue": analyze_review_queue(),
        "runtime_database": analyze_runtime_db(),
        "ai_ar_measurement_availability": analyze_ai_ar_availability(),
        "manifest_controls": {
            "completed_human_reviews": run_manifest.get("completed_human_reviews"),
            "approved_ai_candidates": run_manifest.get("approved_ai_candidates"),
            "official_c_equals_b_reason": run_manifest.get("c_equals_b_reason"),
            "limitations": run_manifest.get("limitations", []),
        },
    }
    print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=False))


if __name__ == "__main__":
    main()
