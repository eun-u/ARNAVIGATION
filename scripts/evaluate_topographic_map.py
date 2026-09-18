"""Inventory and conservatively match NGII topographic-map features.

Only feature codes whose meanings are confirmed by the official NGII catalog
are semantically named.  Geometry matches are review candidates, never routing
facts, and this evaluator does not mutate the baseline graph.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import re
import struct
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable
from zipfile import ZipFile

import geopandas as gpd
import pandas as pd
from pyproj import Transformer
from shapely import STRtree, make_valid
from shapely.geometry import mapping
from shapely.ops import transform, unary_union

try:
    from scripts.validate_spatial_sources import (
        GRAPH_RELATIVE_PATH,
        RAW_GRAPH_METADATA_RELATIVE_PATH,
        RAW_GRAPH_RELATIVE_PATH,
        CorridorContext,
        build_corridor_context,
        coverage_metrics,
        sha256_file,
    )
except ModuleNotFoundError:  # Direct execution from scripts/
    from validate_spatial_sources import (  # type: ignore[no-redef]
        GRAPH_RELATIVE_PATH,
        RAW_GRAPH_METADATA_RELATIVE_PATH,
        RAW_GRAPH_RELATIVE_PATH,
        CorridorContext,
        build_corridor_context,
        coverage_metrics,
        sha256_file,
    )


SOURCE_RELATIVE_PATH = Path("data/raw/ngii/digital_topographic_map")
CATALOG_RELATIVE_PATH = Path(
    "data/raw/ngii/reference/topographic_feature_catalog/2019"
)
DEFAULT_OUTPUT_DIR = Path("data/processed/evaluation/topographic_map")
OFFICIAL_CATALOG_TITLE = "수치지도 지형지물 표준코드"
OFFICIAL_CATALOG_URL = "https://www.ngii.go.kr/kor/board/view.do?sq=54745&board_code=lawinfo"

# These meanings and geometry types are explicitly present in the official
# catalog above.  Codes outside this allowlist remain inventory-only.
OFFICIAL_FEATURES: dict[str, dict[str, Any]] = {
    "A0010000": {
        "name_ko": "도로경계",
        "geometry": "area",
        "evaluation_role": "road_geometry_context",
        "mapping_enabled": False,
    },
    "A0033320": {
        "name_ko": "인도(미분류)",
        "evaluation_role": "pedestrian_area",
        "mapping_enabled": True,
    },
    "A0033324": {
        "name_ko": "인도",
        "evaluation_role": "pedestrian_area",
        "mapping_enabled": True,
    },
    "A0043325": {
        "name_ko": "횡단보도",
        "geometry": "area",
        "evaluation_role": "crossing_candidate",
        "mapping_enabled": True,
    },
    "A0063321": {
        "name_ko": "육교",
        "geometry": "area",
        "evaluation_role": "grade_separated_crossing_candidate",
        "mapping_enabled": True,
    },
    "A0123373": {
        "name_ko": "터널입구",
        "evaluation_role": "tunnel_entrance_context",
        "mapping_enabled": False,
    },
    "A0151224": {
        "name_ko": "지하철역 출입구",
        "evaluation_role": "subway_entrance_candidate",
        "mapping_enabled": True,
    },
    "A0070000": {
        "name_ko": "교량",
        "geometry": "area",
        "evaluation_role": "bridge_context",
        "mapping_enabled": False,
    },
    "C0390000": {
        "name_ko": "계단(미분류)",
        "evaluation_role": "stairs_candidate",
        "mapping_enabled": True,
    },
    "C0393323": {
        "name_ko": "계단",
        "evaluation_role": "stairs_candidate",
        "mapping_enabled": True,
    },
    "C0453322": {
        "name_ko": "지하도",
        "evaluation_role": "underground_passage_candidate",
        "mapping_enabled": True,
    },
    "C0463374": {
        "name_ko": "지하도입구",
        "evaluation_role": "underground_entrance_candidate",
        "mapping_enabled": True,
    },
    "C0520000": {
        "name_ko": "도로분리대(미분류)",
        "evaluation_role": "road_divider_context",
        "mapping_enabled": False,
    },
    "F0010000": {
        "name_ko": "등고선(미분류)",
        "evaluation_role": "contour_context",
        "mapping_enabled": False,
    },
    "F0020000": {
        "name_ko": "표고점(미분류)",
        "evaluation_role": "elevation_point_context",
        "mapping_enabled": False,
    },
}

LAYER_PATTERN = re.compile(
    r"^N(?P<scale>[13])(?P<geometry>[ALP])_"
    r"(?P<layer>[A-Z]\d{3})(?P<table>\d{4})\.shp$",
    re.IGNORECASE,
)
INVENTORY_FIELDS = (
    "sheet_id",
    "year",
    "scale",
    "archive_sha256",
    "member",
    "feature_code",
    "official_name_ko",
    "geometry_kind",
    "feature_count",
    "semantic_scope",
    "mapping_enabled",
    "attribute_encoding_status",
)


def _atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    os.replace(temporary, path)


def _atomic_write_csv(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=INVENTORY_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    os.replace(temporary, path)


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, math.ceil(percentile * len(ordered)) - 1)
    return round(ordered[index], 6)


def parse_layer_member(member: str) -> dict[str, str] | None:
    """Parse NGII shapefile naming without guessing its semantic meaning."""

    match = LAYER_PATTERN.match(Path(member).name)
    if not match:
        return None
    values = match.groupdict()
    geometry_kind = {"A": "area", "L": "line", "P": "point"}[
        values["geometry"].upper()
    ]
    return {
        "scale_prefix": values["scale"],
        "geometry_kind": geometry_kind,
        "feature_code": (values["layer"] + values["table"]).upper(),
    }


def _dbf_record_count(archive: ZipFile, shp_member: str) -> int | None:
    stem = str(Path(shp_member).with_suffix("")).replace("\\", "/")
    dbf_name = next(
        (
            name
            for name in archive.namelist()
            if name.lower() == f"{stem}.dbf".lower()
        ),
        None,
    )
    if dbf_name is None:
        return None
    with archive.open(dbf_name) as handle:
        header = handle.read(8)
    return struct.unpack("<I", header[4:8])[0] if len(header) == 8 else None


def _contains_replacement_character(value: Any) -> bool:
    if isinstance(value, str):
        return "\ufffd" in value
    return False


def _attribute_encoding_status(frame: gpd.GeoDataFrame) -> str:
    if any(_contains_replacement_character(column) for column in frame.columns):
        return "decode_replacement_detected"
    attribute_columns = [column for column in frame.columns if column != "geometry"]
    for column in attribute_columns:
        sample = frame[column].dropna().head(100)
        if any(_contains_replacement_character(value) for value in sample):
            return "decode_replacement_detected"
    return "readable"


def classify_feature_match(
    source_geometry: Any,
    edge_geometries: tuple[Any, ...],
    edge_ids: tuple[str, ...],
    *,
    tree: STRtree | None = None,
    max_distance_m: float = 15.0,
) -> dict[str, Any]:
    """Classify one source geometry as unique, ambiguous, or unmatched."""

    spatial_index = tree or STRtree(edge_geometries)
    candidate_indices = spatial_index.query(source_geometry.buffer(max_distance_m))
    candidates: list[dict[str, Any]] = []
    source_area = max(float(source_geometry.area), 1e-9)
    for raw_index in candidate_indices:
        index = int(raw_index)
        edge = edge_geometries[index]
        distance = float(source_geometry.distance(edge))
        if distance > max_distance_m:
            continue
        edge_length = max(float(edge.length), 1e-9)
        line_overlap_ratio = min(
            1.0, float(edge.intersection(source_geometry).length) / edge_length
        )
        edge_buffer = edge.buffer(5.0)
        intersection_area = float(source_geometry.intersection(edge_buffer).area)
        edge_buffer_overlap_ratio = min(
            1.0, intersection_area / max(float(edge_buffer.area), 1e-9)
        )
        source_overlap_ratio = min(1.0, intersection_area / source_area)
        overlap_score = max(line_overlap_ratio, edge_buffer_overlap_ratio)
        distance_score = max(0.0, 1.0 - distance / max_distance_m)
        score = 0.55 * overlap_score + 0.30 * distance_score + 0.15 * source_overlap_ratio
        candidates.append(
            {
                "edge_id": edge_ids[index],
                "distance_m": round(distance, 6),
                "line_overlap_ratio": round(line_overlap_ratio, 6),
                "edge_buffer_overlap_ratio": round(edge_buffer_overlap_ratio, 6),
                "source_overlap_ratio": round(source_overlap_ratio, 6),
                "score": round(score, 6),
            }
        )
    candidates.sort(key=lambda item: (-item["score"], item["distance_m"], item["edge_id"]))
    if not candidates or candidates[0]["score"] < 0.18:
        return {
            "status": "unmatched",
            "best": candidates[0] if candidates else None,
            "candidates": candidates[:5],
            "ambiguity_reason": None,
        }
    best = candidates[0]
    second = candidates[1] if len(candidates) > 1 else None
    if best["score"] < 0.28:
        status = "ambiguous"
        reason = "weak_best_score"
    elif second is not None and best["score"] - second["score"] < 0.12:
        status = "ambiguous"
        reason = "competing_edges"
    else:
        status = "unique"
        reason = None
    return {
        "status": status,
        "best": best,
        "candidates": candidates[:5],
        "ambiguity_reason": reason,
    }


def _feature_collection(
    features: list[dict[str, Any]],
    *,
    created_at: str,
    graph_sha256: str,
    purpose: str,
) -> dict[str, Any]:
    return {
        "type": "FeatureCollection",
        "metadata": {
            "schema_version": "1.0",
            "created_at": created_at,
            "purpose": purpose,
            "metric_crs": "EPSG:5179",
            "output_crs": "EPSG:4326",
            "source_graph_sha256": graph_sha256,
            "official_catalog": {
                "title": OFFICIAL_CATALOG_TITLE,
                "url": OFFICIAL_CATALOG_URL,
            },
            "derived": True,
            "verified": False,
            "graph_update_allowed": False,
        },
        "features": features,
    }


def _geojson_feature(
    geometry_5179: Any,
    properties: dict[str, Any],
    to_wgs84: Transformer,
) -> dict[str, Any]:
    return {
        "type": "Feature",
        "geometry": mapping(transform(to_wgs84.transform, geometry_5179)),
        "properties": {
            **properties,
            "derived": True,
            "verified": False,
            "graph_update_allowed": False,
        },
    }


def _load_manifest(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError("Topographic source manifest root must be an object.")
    return value


def _load_official_catalog(project_root: Path) -> tuple[dict[str, str], dict[str, Any]]:
    catalog_dir = project_root / CATALOG_RELATIVE_PATH
    manifest = _load_manifest(catalog_dir / "source_manifest.json")
    catalog_path = catalog_dir / str(manifest.get("catalog_file") or "")
    expected_sha = str(manifest.get("catalog_file_sha256") or "").lower()
    actual_sha = sha256_file(catalog_path)
    if expected_sha and actual_sha.lower() != expected_sha:
        raise RuntimeError("Official topographic feature catalog SHA-256 mismatch.")
    frame = pd.read_excel(
        catalog_path,
        sheet_name=str(manifest.get("sheet") or "지형지물 표준코드"),
        header=None,
        engine="xlrd",
    )
    lookup: dict[str, str] = {}
    for _, row in frame.iterrows():
        code = str(row.iloc[5]).strip() if pd.notna(row.iloc[5]) else ""
        if not re.fullmatch(r"[A-Z]\d{7}", code):
            continue
        small_name = str(row.iloc[4]).strip() if pd.notna(row.iloc[4]) else ""
        middle_name = str(row.iloc[3]).strip() if pd.notna(row.iloc[3]) else ""
        lookup[code] = small_name or middle_name
    return lookup, {**manifest, "catalog_file_actual_sha256": actual_sha}


def run_topographic_evaluation(
    project_root: Path,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    *,
    created_at: str | None = None,
) -> dict[str, Any]:
    project_root = project_root.resolve()
    output_dir = output_dir if output_dir.is_absolute() else project_root / output_dir
    timestamp = created_at or datetime.now().astimezone().isoformat(timespec="seconds")
    context, graph_report = build_corridor_context(
        project_root / GRAPH_RELATIVE_PATH,
        project_root / RAW_GRAPH_RELATIVE_PATH,
        project_root / RAW_GRAPH_METADATA_RELATIVE_PATH,
    )
    if context is None or graph_report.get("status") == "fail":
        raise RuntimeError("Baseline graph validation failed; topographic evaluation was not run.")

    source_dir = project_root / SOURCE_RELATIVE_PATH
    manifest = _load_manifest(source_dir / "source_manifest.json")
    catalog_lookup, catalog_manifest = _load_official_catalog(project_root)
    missing_catalog_codes = sorted(set(OFFICIAL_FEATURES) - set(catalog_lookup))
    if missing_catalog_codes:
        raise RuntimeError(
            f"Allowlisted topographic codes are absent from the official catalog: {missing_catalog_codes}"
        )
    declared_crs = str(manifest.get("crs") or "")
    if declared_crs != "EPSG:5186":
        raise RuntimeError(f"Topographic source CRS must be EPSG:5186, observed {declared_crs!r}.")

    edge_tree = STRtree(context.edges_5179)
    to_wgs84 = Transformer.from_crs("EPSG:5179", "EPSG:4326", always_xy=True)
    inventory: list[dict[str, Any]] = []
    matches: list[dict[str, Any]] = []
    new_candidates: list[dict[str, Any]] = []
    selected_geometries: list[Any] = []
    status_counts: Counter[str] = Counter()
    code_counts: Counter[str] = Counter()
    encoding_counts: Counter[str] = Counter()
    invalid_geometry_count = 0
    duplicate_feature_count = 0
    seen_feature_keys: set[str] = set()

    for tile in manifest.get("tiles") or []:
        sheet_id = str(tile.get("sheet_id") or "")
        archive_path = source_dir / str(tile.get("archive") or "")
        if not archive_path.is_file():
            candidates = sorted(
                (source_dir / str(tile.get("year")) / sheet_id).glob("*.zip")
            )
            if len(candidates) == 1:
                archive_path = candidates[0]
        if not archive_path.is_file():
            raise RuntimeError(f"Topographic archive is missing for sheet {sheet_id}.")
        archive_sha = sha256_file(archive_path)
        expected_sha = str(tile.get("archive_sha256") or "").lower()
        if expected_sha and archive_sha.lower() != expected_sha:
            raise RuntimeError(f"Topographic archive SHA-256 mismatch for sheet {sheet_id}.")

        with ZipFile(archive_path) as archive:
            corrupt = archive.testzip()
            if corrupt:
                raise RuntimeError(f"Topographic archive is corrupt: {archive_path}::{corrupt}")
            shp_members = sorted(
                name for name in archive.namelist() if name.lower().endswith(".shp")
            )
            layer_records: list[tuple[str, dict[str, str], int | None]] = []
            for member in shp_members:
                parsed = parse_layer_member(member)
                if parsed is None:
                    continue
                layer_records.append((member, parsed, _dbf_record_count(archive, member)))

        for member, parsed, feature_count in layer_records:
            feature_code = parsed["feature_code"]
            definition = OFFICIAL_FEATURES.get(feature_code)
            official_name = catalog_lookup.get(feature_code, "")
            inventory_row = {
                "sheet_id": sheet_id,
                "year": tile.get("year"),
                "scale": tile.get("scale"),
                "archive_sha256": archive_sha,
                "member": member,
                "feature_code": feature_code,
                "official_name_ko": official_name,
                "geometry_kind": parsed["geometry_kind"],
                "feature_count": feature_count,
                "semantic_scope": definition["evaluation_role"] if definition else "unmapped",
                "mapping_enabled": bool(definition and definition["mapping_enabled"]),
                "attribute_encoding_status": "not_read",
            }
            inventory.append(inventory_row)
            if not definition or not definition["mapping_enabled"]:
                continue

            vsi_path = f"/vsizip/{archive_path.resolve().as_posix()}/{member}"
            frame = gpd.read_file(vsi_path, engine="pyogrio", encoding="CP949")
            encoding_status = _attribute_encoding_status(frame)
            inventory_row["attribute_encoding_status"] = encoding_status
            encoding_counts[encoding_status] += 1
            if frame.crs is None or frame.crs.to_epsg() != 5186:
                raise RuntimeError(
                    f"Layer CRS mismatch for {sheet_id}/{member}: {frame.crs!s}"
                )
            frame = frame.to_crs("EPSG:5179")
            ufid_column = next(
                (column for column in frame.columns if str(column).upper() == "UFID"),
                None,
            )
            for index, row in frame.iterrows():
                geometry = row.geometry
                if geometry is None or geometry.is_empty:
                    invalid_geometry_count += 1
                    continue
                if not geometry.is_valid:
                    geometry = make_valid(geometry)
                if geometry.is_empty or geometry.geom_type not in {
                    "Polygon",
                    "MultiPolygon",
                    "GeometryCollection",
                    "LineString",
                    "MultiLineString",
                    "Point",
                    "MultiPoint",
                }:
                    invalid_geometry_count += 1
                    continue
                clipped = geometry.intersection(context.mask_100m_5179)
                if clipped.is_empty:
                    continue
                raw_id = str(row[ufid_column]) if ufid_column else ""
                if not raw_id or raw_id.lower() == "nan":
                    raw_id = hashlib.sha256(geometry.wkb).hexdigest()[:20]
                feature_key = f"{feature_code}:{raw_id}"
                if feature_key in seen_feature_keys:
                    duplicate_feature_count += 1
                    continue
                seen_feature_keys.add(feature_key)
                code_counts[feature_code] += 1
                selected_geometries.append(clipped)

                result = classify_feature_match(
                    clipped,
                    context.edges_5179,
                    context.edge_ids,
                    tree=edge_tree,
                )
                status_counts[result["status"]] += 1
                best = result["best"]
                common_properties = {
                    "source_feature_id": raw_id,
                    "source_feature_code": feature_code,
                    "source_feature_name_ko": official_name,
                    "evaluation_role": definition["evaluation_role"],
                    "source_sheet_id": sheet_id,
                    "source_year": tile.get("year"),
                    "source_scale": tile.get("scale"),
                    "source_archive_sha256": archive_sha,
                    "source_layer": Path(member).name,
                    "source_attribute_encoding_status": encoding_status,
                    "source_catalog_confirmed": True,
                    "match_status": result["status"],
                    "best_edge_id": best["edge_id"] if best else None,
                    "best_distance_m": best["distance_m"] if best else None,
                    "best_score": best["score"] if best else None,
                    "candidate_edge_count": len(result["candidates"]),
                    "candidate_edge_ids": [
                        candidate["edge_id"] for candidate in result["candidates"]
                    ],
                    "ambiguity_reason": result["ambiguity_reason"],
                }
                output_feature = _geojson_feature(clipped, common_properties, to_wgs84)
                if result["status"] == "unmatched":
                    if clipped.intersects(context.mask_30m_5179):
                        new_candidates.append(output_feature)
                else:
                    matches.append(output_feature)

    mapped_total = sum(status_counts.values())
    unique_count = status_counts["unique"]
    unique_rate = 100.0 * unique_count / mapped_total if mapped_total else 0.0
    matched_distances = [
        float(feature["properties"]["best_distance_m"])
        for feature in matches
        if feature["properties"]["best_distance_m"] is not None
    ]
    selected_union = unary_union(selected_geometries) if selected_geometries else None
    source_coverage = coverage_metrics(selected_union, context) if selected_union else None
    known_inventory = [row for row in inventory if row["official_name_ko"]]
    mapped_inventory = [row for row in inventory if row["mapping_enabled"]]
    total_inventory_features = sum(int(row["feature_count"] or 0) for row in inventory)
    known_inventory_features = sum(int(row["feature_count"] or 0) for row in known_inventory)
    checks = [
        {
            "code": "topographic_eval.official_semantics",
            "status": "pass",
            "message": "Only official-catalog allowlisted feature codes were semantically evaluated.",
            "evidence": {"mapping_codes": sorted(code_counts)},
        },
        {
            "code": "topographic_eval.attribute_encoding",
            "status": "warning"
            if encoding_counts["decode_replacement_detected"]
            else "pass",
            "message": "Some DBF names or values contain replacement characters; attributes were not promoted."
            if encoding_counts["decode_replacement_detected"]
            else "Selected DBF attributes decoded without replacement characters.",
            "evidence": dict(sorted(encoding_counts.items())),
        },
        {
            "code": "topographic_eval.unique_match_gate",
            "status": "pass" if unique_rate >= 80.0 else "warning",
            "message": "Unique-match rate meets the initial 80% automation gate."
            if unique_rate >= 80.0
            else "Unique-match rate is below the initial 80% automation gate; manual review remains required.",
            "evidence": {"unique_match_rate_pct": round(unique_rate, 3)},
        },
        {
            "code": "topographic_eval.graph_safety_boundary",
            "status": "pass",
            "message": "All matches and candidates remain derived, unverified, and disconnected from graph mutation.",
        },
    ]
    status = "fail" if any(item["status"] == "fail" for item in checks) else (
        "warning" if any(item["status"] == "warning" for item in checks) else "pass"
    )
    report = {
        "schema_version": "1.0",
        "created_at": timestamp,
        "status": status,
        "dataset_id": manifest.get("dataset_id"),
        "official_catalog": {
            "dataset_id": catalog_manifest.get("dataset_id"),
            "title": catalog_manifest.get("title") or OFFICIAL_CATALOG_TITLE,
            "url": catalog_manifest.get("source_page") or OFFICIAL_CATALOG_URL,
            "catalog_file_sha256": catalog_manifest.get("catalog_file_actual_sha256"),
            "allowlisted_feature_codes": OFFICIAL_FEATURES,
        },
        "graph": {
            "source_graph_sha256": context.graph_sha256,
            "edge_count": context.edge_count,
            "total_edge_length_m": round(context.total_edge_length_m, 3),
        },
        "inventory": {
            "tile_count": len(manifest.get("tiles") or []),
            "layer_instance_count": len(inventory),
            "feature_count": total_inventory_features,
            "officially_named_layer_instance_count": len(known_inventory),
            "officially_named_feature_count": known_inventory_features,
            "mapping_enabled_layer_instance_count": len(mapped_inventory),
            "mapping_enabled_feature_count_in_context": mapped_total,
        },
        "metrics": {
            "feature_counts_by_code_in_context": dict(sorted(code_counts.items())),
            "unique_match_count": unique_count,
            "ambiguous_match_count": status_counts["ambiguous"],
            "unmatched_count": status_counts["unmatched"],
            "new_object_candidate_count": len(new_candidates),
            "unique_match_rate_pct": round(unique_rate, 3),
            "matched_distance_m": {
                "median": _percentile(matched_distances, 0.5),
                "p95": _percentile(matched_distances, 0.95),
                "max": round(max(matched_distances), 6) if matched_distances else None,
            },
            "invalid_geometry_count": invalid_geometry_count,
            "duplicate_feature_count": duplicate_feature_count,
            "attribute_encoding_status_counts": dict(sorted(encoding_counts.items())),
            "source_coverage": source_coverage,
        },
        "checks": checks,
        "policy": {
            "derived": True,
            "verified": False,
            "graph_update_allowed": False,
            "routing_graph_mutated": False,
            "attributes_promoted": False,
            "new_routing_geometry_auto_accepted": False,
        },
    }
    _atomic_write_csv(output_dir / "layer_inventory.csv", inventory)
    _atomic_write_json(
        output_dir / "matches.geojson",
        _feature_collection(
            matches,
            created_at=timestamp,
            graph_sha256=context.graph_sha256,
            purpose="topographic_to_graph_review_matches",
        ),
    )
    _atomic_write_json(
        output_dir / "new_object_candidates.geojson",
        _feature_collection(
            new_candidates,
            created_at=timestamp,
            graph_sha256=context.graph_sha256,
            purpose="unmatched_topographic_features_for_manual_review",
        ),
    )
    _atomic_write_json(output_dir / "metrics.json", report)
    return report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Inventory and match allowlisted NGII topographic features."
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--created-at")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        report = run_topographic_evaluation(
            args.project_root, args.output_dir, created_at=args.created_at
        )
    except Exception as exc:  # noqa: BLE001 - CLI reserves exit 2 for internal errors
        print(f"Topographic evaluation failed: {exc}", file=sys.stderr)
        return 2
    metrics = report["metrics"]
    print(
        "Topographic evaluation: "
        f"status={report['status']} unique={metrics['unique_match_count']} "
        f"ambiguous={metrics['ambiguous_match_count']} "
        f"unmatched={metrics['unmatched_count']}"
    )
    return 1 if report["status"] == "fail" else 0


if __name__ == "__main__":
    raise SystemExit(main())
