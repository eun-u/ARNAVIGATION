"""Validate NaVi spatial source data without mutating the routing graph.

The validator is intentionally conservative.  It inventories immutable source
files, verifies declared integrity/CRS information, creates corridor masks from
the current OSM-derived graph, and writes machine-readable metrics.  It never
promotes a derived value to a verified accessibility fact.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import sys
import warnings
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable
from xml.etree import ElementTree
from zipfile import BadZipFile, ZipFile

try:
    import rasterio
    from pyproj import CRS, Transformer
    from rasterio.errors import NotGeoreferencedWarning
    from shapely.geometry import LineString, Point, box, mapping, shape
    from shapely.ops import transform, unary_union
except ImportError as exc:  # pragma: no cover - exercised through the CLI guard
    _GEO_IMPORT_ERROR: ImportError | None = exc
else:
    _GEO_IMPORT_ERROR = None


STATUS_RANK = {"pass": 0, "hold": 0, "warning": 1, "fail": 2}
GRAPH_RELATIVE_PATH = Path("data/processed/anyang_accessibility_graph.geojson")
RAW_GRAPH_RELATIVE_PATH = Path("data/raw/anyang_corridor_walk_20260915.graphml")
RAW_GRAPH_METADATA_RELATIVE_PATH = Path(
    "data/raw/anyang_corridor_walk_20260915.metadata.json"
)


@dataclass(frozen=True)
class CorridorContext:
    edge_ids: tuple[str, ...]
    edges_5179: tuple[Any, ...]
    graph_bbox_wgs84: tuple[float, float, float, float]
    mask_30m_5179: Any
    mask_100m_5179: Any
    graph_sha256: str
    raw_graph_sha256: str
    node_count: int
    edge_count: int
    total_edge_length_m: float
    roundtrip_max_error_m: float


def _check(
    code: str,
    status: str,
    message: str,
    evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {"code": code, "status": status, "message": message}
    if evidence:
        result["evidence"] = evidence
    return result


def _add_check(
    target: dict[str, Any],
    code: str,
    status: str,
    message: str,
    evidence: dict[str, Any] | None = None,
) -> None:
    target.setdefault("checks", []).append(_check(code, status, message, evidence))


def _finalize_status(target: dict[str, Any], *, force_hold: bool = False) -> str:
    statuses = [item["status"] for item in target.get("checks", [])]
    if "fail" in statuses:
        status = "fail"
    elif force_hold:
        status = "hold"
    elif "warning" in statuses:
        status = "warning"
    elif "hold" in statuses:
        status = "hold"
    else:
        status = "pass"
    target["status"] = status
    return status


def _source_report(
    dataset_id: str,
    source_type: str,
    relative_path: str,
    *,
    required: bool = True,
) -> dict[str, Any]:
    return {
        "dataset_id": dataset_id,
        "source_type": source_type,
        "path": relative_path.replace("\\", "/"),
        "required": required,
        "derived": False,
        "verified": False,
        "graph_update_allowed": False,
        "checks": [],
        "observed": {},
    }


def _relative(path: Path, project_root: Path) -> str:
    try:
        return path.resolve().relative_to(project_root.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def sha256_file(path: Path, *, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return value


def _atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def _transform_geometry(geometry: Any, source_crs: str, target_crs: str) -> Any:
    transformer = Transformer.from_crs(source_crs, target_crs, always_xy=True)
    return transform(transformer.transform, geometry)


def _iter_line_coordinates(geometry: Any) -> Iterable[tuple[float, float]]:
    if geometry.geom_type == "LineString":
        yield from geometry.coords
    elif geometry.geom_type == "MultiLineString":
        for part in geometry.geoms:
            yield from part.coords


def build_corridor_context(
    graph_path: Path,
    raw_graph_path: Path,
    raw_metadata_path: Path,
) -> tuple[CorridorContext | None, dict[str, Any]]:
    """Load and validate the baseline graph, returning projected corridor masks."""

    report: dict[str, Any] = {
        "path": graph_path.as_posix(),
        "derived": False,
        "verified": False,
        "graph_update_allowed": False,
        "checks": [],
        "observed": {},
    }
    required_paths = (graph_path, raw_graph_path, raw_metadata_path)
    missing = [str(path) for path in required_paths if not path.is_file()]
    if missing:
        _add_check(
            report,
            "graph.required_inputs",
            "fail",
            "A required baseline graph input is missing.",
            {"missing": missing},
        )
        _finalize_status(report)
        return None, report

    try:
        graph_data = _load_json(graph_path)
        raw_metadata = _load_json(raw_metadata_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        _add_check(
            report,
            "graph.readable",
            "fail",
            "The baseline graph or its metadata is unreadable.",
            {"error": str(exc)},
        )
        _finalize_status(report)
        return None, report

    if graph_data.get("type") != "FeatureCollection":
        _add_check(
            report,
            "graph.geojson_type",
            "fail",
            "The baseline graph is not a GeoJSON FeatureCollection.",
        )
        _finalize_status(report)
        return None, report

    metadata = graph_data.get("metadata") or {}
    declared_crs = metadata.get("crs")
    _add_check(
        report,
        "graph.crs",
        "pass" if declared_crs == "EPSG:4326" else "fail",
        "Baseline graph CRS matches EPSG:4326."
        if declared_crs == "EPSG:4326"
        else "Baseline graph CRS does not match the required EPSG:4326.",
        {"declared_crs": declared_crs},
    )

    nodes: list[Any] = []
    edges_wgs84: list[Any] = []
    node_ids: list[str] = []
    edge_ids: list[str] = []
    geometry_errors: list[str] = []
    for index, feature in enumerate(graph_data.get("features", [])):
        properties = feature.get("properties") or {}
        feature_type = properties.get("feature_type")
        try:
            geometry = shape(feature.get("geometry"))
        except Exception as exc:  # noqa: BLE001 - validation must collect failures
            geometry_errors.append(f"feature[{index}]: {exc}")
            continue
        if geometry.is_empty or not geometry.is_valid:
            geometry_errors.append(f"feature[{index}]: empty or invalid geometry")
            continue
        if feature_type == "node":
            node_ids.append(str(properties.get("node_id") or ""))
            nodes.append(geometry)
        elif feature_type == "edge":
            edge_ids.append(str(properties.get("edge_id") or ""))
            if geometry.geom_type not in {"LineString", "MultiLineString"}:
                geometry_errors.append(
                    f"feature[{index}]: edge geometry is {geometry.geom_type}"
                )
            else:
                edges_wgs84.append(geometry)

    duplicate_node_ids = len(node_ids) - len(set(node_ids))
    duplicate_edge_ids = len(edge_ids) - len(set(edge_ids))
    missing_ids = sum(not value for value in node_ids + edge_ids)
    identifiers_ok = duplicate_node_ids == duplicate_edge_ids == missing_ids == 0
    _add_check(
        report,
        "graph.identifiers",
        "pass" if identifiers_ok else "fail",
        "Graph node and edge identifiers are present and unique."
        if identifiers_ok
        else "Graph contains missing or duplicate identifiers.",
        {
            "duplicate_node_ids": duplicate_node_ids,
            "duplicate_edge_ids": duplicate_edge_ids,
            "missing_ids": missing_ids,
        },
    )
    _add_check(
        report,
        "graph.geometry",
        "pass" if not geometry_errors and edges_wgs84 else "fail",
        "Graph geometries are readable and valid."
        if not geometry_errors and edges_wgs84
        else "Graph contains unreadable, empty, invalid, or non-linear edge geometry.",
        {"errors": geometry_errors[:20], "error_count": len(geometry_errors)},
    )

    graph_sha = sha256_file(graph_path)
    raw_sha = sha256_file(raw_graph_path)
    declared_graph_raw_sha = str(metadata.get("osm_snapshot_sha256") or "").lower()
    declared_metadata_sha = str(raw_metadata.get("sha256") or "").lower()
    hashes_ok = (
        raw_sha.lower() == declared_graph_raw_sha == declared_metadata_sha
        and bool(declared_graph_raw_sha)
    )
    _add_check(
        report,
        "graph.raw_snapshot_sha256",
        "pass" if hashes_ok else "fail",
        "The raw OSM snapshot hash matches both graph metadata records."
        if hashes_ok
        else "The raw OSM snapshot hash differs from declared graph metadata.",
        {
            "actual": raw_sha,
            "graph_metadata": declared_graph_raw_sha,
            "raw_metadata": declared_metadata_sha,
        },
    )

    if geometry_errors or not edges_wgs84 or declared_crs != "EPSG:4326":
        _finalize_status(report)
        return None, report

    to_5179 = Transformer.from_crs("EPSG:4326", "EPSG:5179", always_xy=True)
    to_4326 = Transformer.from_crs("EPSG:5179", "EPSG:4326", always_xy=True)
    edges_5179 = tuple(transform(to_5179.transform, edge) for edge in edges_wgs84)
    edge_union = unary_union(edges_5179)
    mask_30m = edge_union.buffer(30.0)
    mask_100m = edge_union.buffer(100.0)

    coordinate_samples: list[tuple[float, float]] = []
    for edge in edges_wgs84:
        for coordinate in _iter_line_coordinates(edge):
            coordinate_samples.append((float(coordinate[0]), float(coordinate[1])))
            if len(coordinate_samples) >= 100:
                break
        if len(coordinate_samples) >= 100:
            break
    max_roundtrip_error = 0.0
    for lon, lat in coordinate_samples:
        x1, y1 = to_5179.transform(lon, lat)
        roundtrip_lon, roundtrip_lat = to_4326.transform(x1, y1)
        x2, y2 = to_5179.transform(roundtrip_lon, roundtrip_lat)
        max_roundtrip_error = max(max_roundtrip_error, math.hypot(x2 - x1, y2 - y1))
    roundtrip_ok = max_roundtrip_error <= 0.2
    _add_check(
        report,
        "graph.crs_roundtrip",
        "pass" if roundtrip_ok else "fail",
        "CRS round-trip error is within the project 0.2 m processing gate."
        if roundtrip_ok
        else "CRS round-trip error exceeds the project 0.2 m processing gate.",
        {"sample_count": len(coordinate_samples), "max_error_m": max_roundtrip_error},
    )

    all_geometries = nodes + edges_wgs84
    minx = min(geometry.bounds[0] for geometry in all_geometries)
    miny = min(geometry.bounds[1] for geometry in all_geometries)
    maxx = max(geometry.bounds[2] for geometry in all_geometries)
    maxy = max(geometry.bounds[3] for geometry in all_geometries)
    node_count = len(nodes)
    edge_count = len(edges_wgs84)
    raw_node_count = raw_metadata.get("nodes")
    raw_directed_edge_count = raw_metadata.get("edges")
    count_consistency = node_count == raw_node_count and (
        not isinstance(raw_directed_edge_count, int)
        or raw_directed_edge_count == edge_count * 2
    )
    _add_check(
        report,
        "graph.feature_counts",
        "pass" if count_consistency else "warning",
        "Processed graph counts are consistent with raw snapshot metadata."
        if count_consistency
        else "Processed graph counts differ from the expected undirected projection of raw metadata.",
        {
            "processed_nodes": node_count,
            "processed_edges": edge_count,
            "raw_nodes": raw_node_count,
            "raw_directed_edges": raw_directed_edge_count,
        },
    )
    total_edge_length = sum(edge.length for edge in edges_5179)
    report["observed"] = {
        "node_count": node_count,
        "edge_count": edge_count,
        "bbox_wgs84": [minx, miny, maxx, maxy],
        "total_edge_length_m": round(total_edge_length, 3),
        "graph_sha256": graph_sha,
        "raw_graph_sha256": raw_sha,
        "roundtrip_max_error_m": max_roundtrip_error,
    }
    _finalize_status(report)
    context = CorridorContext(
        edge_ids=tuple(edge_ids),
        edges_5179=edges_5179,
        graph_bbox_wgs84=(minx, miny, maxx, maxy),
        mask_30m_5179=mask_30m,
        mask_100m_5179=mask_100m,
        graph_sha256=graph_sha,
        raw_graph_sha256=raw_sha,
        node_count=node_count,
        edge_count=edge_count,
        total_edge_length_m=total_edge_length,
        roundtrip_max_error_m=max_roundtrip_error,
    )
    return context, report


def coverage_metrics(footprint_5179: Any, context: CorridorContext) -> dict[str, Any]:
    if footprint_5179 is None or footprint_5179.is_empty:
        return {
            "intersected_edge_count": 0,
            "intersected_edge_pct": 0.0,
            "fully_covered_edge_count": 0,
            "fully_covered_edge_pct": 0.0,
            "covered_edge_length_m": 0.0,
            "covered_edge_length_pct": 0.0,
            "corridor_30m_area_pct": 0.0,
            "context_100m_area_pct": 0.0,
        }
    intersected = 0
    fully_covered = 0
    covered_length = 0.0
    for edge in context.edges_5179:
        intersection_length = edge.intersection(footprint_5179).length
        if intersection_length > 1e-6:
            intersected += 1
            covered_length += intersection_length
        if edge.length <= 1e-9 or intersection_length >= edge.length - 1e-6:
            fully_covered += 1
    edge_count = len(context.edges_5179)
    mask_30_area = context.mask_30m_5179.area
    mask_100_area = context.mask_100m_5179.area
    return {
        "intersected_edge_count": intersected,
        "intersected_edge_pct": round(100.0 * intersected / edge_count, 3),
        "fully_covered_edge_count": fully_covered,
        "fully_covered_edge_pct": round(100.0 * fully_covered / edge_count, 3),
        "covered_edge_length_m": round(covered_length, 3),
        "covered_edge_length_pct": round(
            100.0 * covered_length / context.total_edge_length_m, 3
        ),
        "corridor_30m_area_pct": round(
            100.0 * context.mask_30m_5179.intersection(footprint_5179).area / mask_30_area,
            3,
        ),
        "context_100m_area_pct": round(
            100.0
            * context.mask_100m_5179.intersection(footprint_5179).area
            / mask_100_area,
            3,
        ),
    }


def corridor_mask_geojson(context: CorridorContext, created_at: str) -> dict[str, Any]:
    to_wgs84 = Transformer.from_crs("EPSG:5179", "EPSG:4326", always_xy=True)
    features = []
    for name, distance_m, geometry in (
        ("representative_corridor", 30, context.mask_30m_5179),
        ("representative_corridor_context", 100, context.mask_100m_5179),
    ):
        features.append(
            {
                "type": "Feature",
                "geometry": mapping(transform(to_wgs84.transform, geometry)),
                "properties": {
                    "name": name,
                    "buffer_m": distance_m,
                    "source_graph_sha256": context.graph_sha256,
                    "metric_crs": "EPSG:5179",
                    "output_crs": "EPSG:4326",
                    "derived": True,
                    "verified": False,
                    "graph_update_allowed": False,
                    "created_at": created_at,
                },
            }
        )
    return {
        "type": "FeatureCollection",
        "metadata": {
            "source_graph_sha256": context.graph_sha256,
            "metric_crs": "EPSG:5179",
            "output_crs": "EPSG:4326",
            "derived": True,
            "verified": False,
            "graph_update_allowed": False,
            "created_at": created_at,
        },
        "features": features,
    }


def _verify_file_declaration(
    report: dict[str, Any],
    path: Path,
    *,
    code_prefix: str,
    expected_size: int | None,
    expected_sha256: str | None,
) -> bool:
    if not path.is_file():
        _add_check(
            report,
            f"{code_prefix}.exists",
            "fail",
            "A manifest-declared file is missing.",
            {"path": path.as_posix()},
        )
        return False
    actual_size = path.stat().st_size
    size_ok = expected_size is None or actual_size == expected_size
    _add_check(
        report,
        f"{code_prefix}.size",
        "pass" if size_ok else "fail",
        "File size matches the manifest." if size_ok else "File size differs from the manifest.",
        {"path": path.as_posix(), "expected": expected_size, "actual": actual_size},
    )
    if expected_sha256:
        actual_sha = sha256_file(path)
        sha_ok = actual_sha.lower() == expected_sha256.lower()
        _add_check(
            report,
            f"{code_prefix}.sha256",
            "pass" if sha_ok else "fail",
            "SHA-256 matches the manifest."
            if sha_ok
            else "SHA-256 differs from the manifest.",
            {
                "path": path.as_posix(),
                "expected": expected_sha256.lower(),
                "actual": actual_sha.lower(),
            },
        )
        return size_ok and sha_ok
    return size_ok


def inspect_shapefile_archive(
    archive_path: Path, expected_crs: str = "EPSG:5186"
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Inspect a ZIP-contained shapefile bundle without extracting it."""

    checks: list[dict[str, Any]] = []
    observed: dict[str, Any] = {"archive": archive_path.as_posix()}
    try:
        with ZipFile(archive_path) as archive:
            corrupt_member = archive.testzip()
            if corrupt_member:
                checks.append(
                    _check(
                        "topographic.archive_crc",
                        "fail",
                        "The ZIP archive contains a corrupt member.",
                        {"member": corrupt_member},
                    )
                )
            else:
                checks.append(
                    _check(
                        "topographic.archive_crc",
                        "pass",
                        "ZIP archive CRC validation passed.",
                    )
                )
            members = [name for name in archive.namelist() if not name.endswith("/")]
            by_stem: dict[str, set[str]] = {}
            for name in members:
                member = Path(name)
                suffix = member.suffix.lower()
                if suffix in {".shp", ".shx", ".dbf", ".prj"}:
                    key = str(member.with_suffix("")).replace("\\", "/").lower()
                    by_stem.setdefault(key, set()).add(suffix)
            missing_components = {
                stem: sorted({".shp", ".shx", ".dbf", ".prj"} - suffixes)
                for stem, suffixes in by_stem.items()
                if ".shp" in suffixes
                and not {".shp", ".shx", ".dbf", ".prj"}.issubset(suffixes)
            }
            checks.append(
                _check(
                    "topographic.shapefile_components",
                    "pass" if not missing_components and by_stem else "fail",
                    "Every SHP has SHX, DBF, and PRJ companions."
                    if not missing_components and by_stem
                    else "One or more shapefile bundles are incomplete.",
                    {
                        "missing": missing_components,
                        "shapefile_count": sum(
                            ".shp" in suffixes for suffixes in by_stem.values()
                        ),
                    },
                )
            )
            prj_values: set[str] = set()
            prj_errors: list[str] = []
            for name in members:
                if not name.lower().endswith(".prj"):
                    continue
                try:
                    wkt = archive.read(name).decode("ascii", errors="strict")
                    parsed = CRS.from_wkt(wkt)
                    authority = parsed.to_authority()
                    prj_values.add(":".join(authority) if authority else parsed.to_string())
                except Exception as exc:  # noqa: BLE001 - collect all malformed PRJs
                    prj_errors.append(f"{name}: {exc}")
            crs_ok = bool(prj_values) and not prj_errors and prj_values == {expected_crs}
            checks.append(
                _check(
                    "topographic.crs",
                    "pass" if crs_ok else "fail",
                    "All PRJ files match the manifest CRS."
                    if crs_ok
                    else "PRJ data is missing, unreadable, or differs from the manifest CRS.",
                    {
                        "expected": expected_crs,
                        "observed": sorted(prj_values),
                        "errors": prj_errors[:10],
                    },
                )
            )
            observed.update(
                {
                    "member_count": len(members),
                    "shapefile_layer_count": sum(
                        ".shp" in suffixes for suffixes in by_stem.values()
                    ),
                    "crs_values": sorted(prj_values),
                }
            )
    except (BadZipFile, OSError) as exc:
        checks.append(
            _check(
                "topographic.archive_readable",
                "fail",
                "The topographic archive is unreadable.",
                {"error": str(exc)},
            )
        )
    return observed, checks


def validate_topographic_map(
    project_root: Path, context: CorridorContext | None
) -> dict[str, Any]:
    base = project_root / "data/raw/ngii/digital_topographic_map"
    manifest_path = base / "source_manifest.json"
    report = _source_report(
        "ngii_digital_topographic_map",
        "NGII_DIGITAL_TOPOGRAPHIC_MAP",
        _relative(base, project_root),
    )
    if not manifest_path.is_file():
        _add_check(report, "topographic.manifest", "fail", "Source manifest is missing.")
        _finalize_status(report)
        return report
    try:
        manifest = _load_json(manifest_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        _add_check(
            report,
            "topographic.manifest",
            "fail",
            "Source manifest is unreadable.",
            {"error": str(exc)},
        )
        _finalize_status(report)
        return report

    tiles = manifest.get("tiles") or []
    declared_crs = str(manifest.get("crs") or "")
    _add_check(
        report,
        "topographic.manifest_schema",
        "pass" if tiles and declared_crs else "fail",
        "Manifest declares tiles and CRS."
        if tiles and declared_crs
        else "Manifest is missing tile or CRS declarations.",
        {"tile_count": len(tiles), "crs": declared_crs},
    )
    footprints_by_scale: dict[str, list[Any]] = {}
    tile_summaries: list[dict[str, Any]] = []
    for tile in tiles:
        sheet_id = str(tile.get("sheet_id") or "")
        declared_archive = base / str(tile.get("archive") or "")
        archive_path = declared_archive
        if not archive_path.is_file():
            candidates = list(
                (base / str(tile.get("year")) / sheet_id).glob("*.zip")
            )
            if len(candidates) == 1:
                archive_path = candidates[0]
        file_ok = _verify_file_declaration(
            report,
            archive_path,
            code_prefix=f"topographic.tile_{sheet_id}.archive",
            expected_size=tile.get("archive_bytes"),
            expected_sha256=tile.get("archive_sha256"),
        )
        observed: dict[str, Any] = {}
        if file_ok:
            observed, checks = inspect_shapefile_archive(archive_path, declared_crs)
            for item in checks:
                item["code"] = f"topographic.tile_{sheet_id}." + item["code"].split(
                    ".", 1
                )[-1]
                report["checks"].append(item)
            actual_layers = observed.get("shapefile_layer_count")
            expected_layers = tile.get("shapefile_layer_count")
            layer_count_ok = actual_layers == expected_layers
            _add_check(
                report,
                f"topographic.tile_{sheet_id}.layer_count",
                "pass" if layer_count_ok else "fail",
                "Shapefile layer count matches the manifest."
                if layer_count_ok
                else "Shapefile layer count differs from the manifest.",
                {"expected": expected_layers, "actual": actual_layers},
            )
        companion_missing = [
            relative
            for relative in tile.get("companions", [])
            if not (base / relative).is_file()
        ]
        _add_check(
            report,
            f"topographic.tile_{sheet_id}.companions",
            "pass" if not companion_missing else "fail",
            "Manifest-declared companion files are present."
            if not companion_missing
            else "One or more manifest-declared companion files are missing.",
            {"missing": companion_missing},
        )
        footprint = None
        if tile.get("bbox_wgs84_from_metadata"):
            footprint = _transform_geometry(
                box(*tile["bbox_wgs84_from_metadata"]), "EPSG:4326", "EPSG:5179"
            )
        elif tile.get("bbox_epsg5186_from_shp_headers"):
            footprint = _transform_geometry(
                box(*tile["bbox_epsg5186_from_shp_headers"]),
                "EPSG:5186",
                "EPSG:5179",
            )
        if footprint is not None:
            footprints_by_scale.setdefault(str(tile.get("scale") or "unknown"), []).append(
                footprint
            )
        tile_summaries.append(
            {
                "sheet_id": sheet_id,
                "year": tile.get("year"),
                "scale": tile.get("scale"),
                "archive": _relative(archive_path, project_root),
                "shapefile_layer_count": observed.get("shapefile_layer_count"),
            }
        )
    report["observed"] = {
        "manifest_dataset_id": manifest.get("dataset_id"),
        "tile_count": len(tiles),
        "declared_crs": declared_crs,
        "tiles": tile_summaries,
    }
    if context and footprints_by_scale:
        scale_coverage = {
            scale: coverage_metrics(unary_union(footprints), context)
            for scale, footprints in footprints_by_scale.items()
        }
        report["coverage"] = coverage_metrics(
            unary_union([item for values in footprints_by_scale.values() for item in values]),
            context,
        )
        report["coverage_by_scale"] = scale_coverage
        _add_check(
            report,
            "topographic.coverage_available",
            "pass",
            "Manifest footprints were mapped to the representative corridor.",
        )
    elif context:
        _add_check(
            report,
            "topographic.coverage_available",
            "fail",
            "No usable tile footprint was declared.",
        )
    _finalize_status(report)
    return report


def validate_dem(project_root: Path, context: CorridorContext | None) -> dict[str, Any]:
    base = project_root / "data/raw/ngii/dem/2025/37612"
    report = _source_report(
        "ngii_public_dem_37612_2025", "NGII_DEM", _relative(base, project_root)
    )
    manifest_path = base / "source_manifest.json"
    manifest: dict[str, Any] | None = None
    if not manifest_path.is_file():
        _add_check(
            report,
            "dem.source_manifest",
            "warning",
            "No source manifest is available; a computed hash is reported but cannot be compared.",
        )
    else:
        try:
            manifest = _load_json(manifest_path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            _add_check(
                report,
                "dem.source_manifest",
                "fail",
                "DEM source manifest is unreadable.",
                {"error": str(exc)},
            )
    archives = list(base.glob("*.zip")) if base.is_dir() else []
    if len(archives) != 1:
        _add_check(
            report,
            "dem.archive_selection",
            "fail",
            "Exactly one DEM ZIP archive is required.",
            {"found": [_relative(path, project_root) for path in archives]},
        )
        _finalize_status(report)
        return report
    archive_path = archives[0]
    archive_sha = sha256_file(archive_path)
    if manifest is not None:
        declared_archive = base / str(manifest.get("archive") or "")
        declaration_ok = archive_path.resolve() == declared_archive.resolve()
        _add_check(
            report,
            "dem.manifest_archive_selection",
            "pass" if declaration_ok else "fail",
            "Selected DEM archive matches the manifest."
            if declaration_ok
            else "Selected DEM archive differs from the manifest.",
            {
                "declared": _relative(declared_archive, project_root),
                "selected": _relative(archive_path, project_root),
            },
        )
        _verify_file_declaration(
            report,
            archive_path,
            code_prefix="dem.archive",
            expected_size=manifest.get("archive_bytes"),
            expected_sha256=manifest.get("archive_sha256"),
        )
    try:
        with ZipFile(archive_path) as archive:
            corrupt_member = archive.testzip()
            img_members = [
                name for name in archive.namelist() if name.lower().endswith(".img")
            ]
        archive_ok = corrupt_member is None and len(img_members) == 1
        _add_check(
            report,
            "dem.archive_integrity",
            "pass" if archive_ok else "fail",
            "DEM archive CRC passed and contains one IMG raster."
            if archive_ok
            else "DEM archive is corrupt or does not contain exactly one IMG raster.",
            {"corrupt_member": corrupt_member, "img_members": img_members},
        )
    except (BadZipFile, OSError) as exc:
        _add_check(
            report,
            "dem.archive_integrity",
            "fail",
            "DEM archive is unreadable.",
            {"error": str(exc)},
        )
        _finalize_status(report)
        return report
    if not archive_ok:
        _finalize_status(report)
        return report

    vsi_path = f"/vsizip/{archive_path.resolve().as_posix()}/{img_members[0]}"
    try:
        with rasterio.open(vsi_path) as dataset:
            sample = dataset.read(1, masked=True)
            raster_crs = dataset.crs.to_string() if dataset.crs else None
            epsg = dataset.crs.to_epsg() if dataset.crs else None
            resolution = [abs(float(dataset.res[0])), abs(float(dataset.res[1]))]
            bounds = box(*dataset.bounds)
            if dataset.crs and epsg != 5179:
                bounds_5179 = _transform_geometry(bounds, raster_crs, "EPSG:5179")
            else:
                bounds_5179 = bounds
            valid_pixels = int(sample.count())
            total_pixels = int(sample.size)
            observed = {
                "manifest_dataset_id": manifest.get("dataset_id") if manifest else None,
                "archive": _relative(archive_path, project_root),
                "archive_bytes": archive_path.stat().st_size,
                "archive_sha256": archive_sha,
                "member": img_members[0],
                "driver": dataset.driver,
                "crs": raster_crs,
                "epsg": epsg,
                "width": dataset.width,
                "height": dataset.height,
                "dtype": dataset.dtypes[0],
                "nodata": dataset.nodata,
                "resolution_m": resolution,
                "bounds": list(dataset.bounds),
                "valid_pixel_count": valid_pixels,
                "nodata_pixel_count": total_pixels - valid_pixels,
            }
    except Exception as exc:  # noqa: BLE001 - GDAL raises several driver errors
        _add_check(
            report,
            "dem.raster_readable",
            "fail",
            "DEM raster cannot be opened or sampled.",
            {"error": str(exc)},
        )
        _finalize_status(report)
        return report
    crs_ok = observed["epsg"] == 5179
    _add_check(
        report,
        "dem.crs",
        "pass" if crs_ok else "fail",
        "DEM CRS matches EPSG:5179."
        if crs_ok
        else "DEM CRS differs from the expected EPSG:5179.",
        {"observed": observed["crs"]},
    )
    if manifest is not None:
        declared_shape = [manifest.get("width"), manifest.get("height")]
        actual_shape = [observed["width"], observed["height"]]
        declared_member = str(manifest.get("raster_member") or "")
        metadata_ok = (
            declared_shape == actual_shape
            and declared_member == observed["member"]
            and str(manifest.get("crs") or "") == "EPSG:5179"
            and float(manifest.get("resolution_m") or 0.0)
            == max(observed["resolution_m"])
        )
        _add_check(
            report,
            "dem.manifest_raster_metadata",
            "pass" if metadata_ok else "fail",
            "DEM raster metadata matches the source manifest."
            if metadata_ok
            else "DEM raster metadata differs from the source manifest.",
            {
                "declared_shape": declared_shape,
                "actual_shape": actual_shape,
                "declared_member": declared_member,
                "actual_member": observed["member"],
            },
        )
    coarse = max(observed["resolution_m"]) >= 90.0
    _add_check(
        report,
        "dem.edge_resolution",
        "warning" if coarse else "pass",
        "The 90 m DEM is too coarse for direct edge-level hard constraints."
        if coarse
        else "DEM resolution is finer than the coarse-resolution warning gate.",
        {"resolution_m": observed["resolution_m"]},
    )
    if context:
        report["coverage"] = coverage_metrics(bounds_5179, context)
        short_edges = sum(
            edge.length < max(observed["resolution_m"]) for edge in context.edges_5179
        )
        observed["edges_shorter_than_one_pixel"] = short_edges
        observed["edges_shorter_than_one_pixel_pct"] = round(
            100.0 * short_edges / len(context.edges_5179), 3
        )
    report["observed"] = observed
    _finalize_status(report)
    return report


_HTML_EXTENT_PATTERN = re.compile(
    r"name=[\"'](?P<name>minx|miny|maxx|maxy)[\"'][^>]*value=[\"'](?P<value>[-+0-9.eE]+)",
    re.IGNORECASE,
)


def _read_html_extent(path: Path) -> tuple[float, float, float, float]:
    text = path.read_text(encoding="utf-8", errors="replace")
    values = {
        match.group("name").lower(): float(match.group("value"))
        for match in _HTML_EXTENT_PATTERN.finditer(text)
    }
    required = {"minx", "miny", "maxx", "maxy"}
    if values.keys() & required != required:
        missing = sorted(required - values.keys())
        raise ValueError(f"missing extent values: {missing}")
    extent = (values["minx"], values["miny"], values["maxx"], values["maxy"])
    if extent[0] >= extent[2] or extent[1] >= extent[3]:
        raise ValueError(f"invalid extent order: {extent}")
    return extent


def validate_orthophoto(
    project_root: Path, context: CorridorContext | None
) -> dict[str, Any]:
    base = project_root / "data/raw/ngii/orthophoto/2025"
    preview_base = project_root / "data/raw/ngii/orthophoto_preview/2025"
    report = _source_report(
        "ngii_orthophoto_2025_anyang_corridor",
        "NGII_ORTHOPHOTO",
        _relative(base, project_root),
    )
    manifest_path = base / "source_manifest.json"
    preview_manifest_path = preview_base / "source_manifest.json"
    if not manifest_path.is_file() or not preview_manifest_path.is_file():
        _add_check(
            report,
            "orthophoto.manifests",
            "fail",
            "Original or preview source manifest is missing.",
            {
                "original_manifest": manifest_path.is_file(),
                "preview_manifest": preview_manifest_path.is_file(),
            },
        )
        _finalize_status(report)
        return report
    try:
        manifest = _load_json(manifest_path)
        preview_manifest = _load_json(preview_manifest_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        _add_check(
            report,
            "orthophoto.manifests",
            "fail",
            "An orthophoto manifest is unreadable.",
            {"error": str(exc)},
        )
        _finalize_status(report)
        return report

    tile_summaries: list[dict[str, Any]] = []
    for tile in manifest.get("tiles") or []:
        sheet_id = str(tile.get("sheet_id") or "")
        raster_path = base / str(tile.get("raster") or "")
        metadata_path = base / str(tile.get("metadata") or "")
        raster_ok = _verify_file_declaration(
            report,
            raster_path,
            code_prefix=f"orthophoto.tile_{sheet_id}.raster",
            expected_size=tile.get("raster_bytes"),
            expected_sha256=tile.get("raster_sha256"),
        )
        metadata_ok = _verify_file_declaration(
            report,
            metadata_path,
            code_prefix=f"orthophoto.tile_{sheet_id}.metadata",
            expected_size=tile.get("metadata_bytes"),
            expected_sha256=tile.get("metadata_sha256"),
        )
        raster_observed: dict[str, Any] = {}
        if raster_ok:
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", NotGeoreferencedWarning)
                    with rasterio.open(raster_path) as dataset:
                        raster_observed = {
                            "width": dataset.width,
                            "height": dataset.height,
                            "band_count": dataset.count,
                            "dtypes": list(dataset.dtypes),
                            "crs": dataset.crs.to_string() if dataset.crs else None,
                            "transform": list(dataset.transform),
                        }
                        expected_dimensions = tile.get("dimensions") or []
                        dimensions_ok = [dataset.width, dataset.height] == expected_dimensions
                        _add_check(
                            report,
                            f"orthophoto.tile_{sheet_id}.dimensions",
                            "pass" if dimensions_ok else "fail",
                            "Raster dimensions match the manifest."
                            if dimensions_ok
                            else "Raster dimensions differ from the manifest.",
                            {
                                "expected": expected_dimensions,
                                "actual": [dataset.width, dataset.height],
                            },
                        )
                        missing_georef = dataset.crs is None
                        _add_check(
                            report,
                            f"orthophoto.tile_{sheet_id}.georeferencing",
                            "warning" if missing_georef else "pass",
                            "Raster has no embedded georeferencing; official preview extent is used only as an evaluation footprint."
                            if missing_georef
                            else "Raster contains embedded georeferencing.",
                        )
            except Exception as exc:  # noqa: BLE001 - GDAL/TIFF errors vary
                _add_check(
                    report,
                    f"orthophoto.tile_{sheet_id}.readable",
                    "fail",
                    "Orthophoto raster is unreadable.",
                    {"error": str(exc)},
                )
        if metadata_ok:
            try:
                ElementTree.parse(metadata_path)
            except (ElementTree.ParseError, OSError) as exc:
                _add_check(
                    report,
                    f"orthophoto.tile_{sheet_id}.metadata_xml",
                    "warning",
                    "Supplied XML metadata is not well-formed and is retained only as raw evidence.",
                    {"error": str(exc)},
                )
            else:
                _add_check(
                    report,
                    f"orthophoto.tile_{sheet_id}.metadata_xml",
                    "pass",
                    "Supplied XML metadata is well-formed.",
                )
        tile_summaries.append(
            {
                "sheet_id": sheet_id,
                "corridor_tile": bool(tile.get("corridor_tile")),
                "raster": _relative(raster_path, project_root),
                **raster_observed,
            }
        )

    preview_tiles = {
        str(tile.get("sheet_id")): tile for tile in preview_manifest.get("tiles") or []
    }
    footprints: list[Any] = []
    preview_summaries: list[dict[str, Any]] = []
    for sheet_id, tile in preview_tiles.items():
        tile_dir = preview_base / sheet_id
        html_files = list(tile_dir.glob("*.html"))
        image_files = list(tile_dir.glob("*.jpg"))
        if len(html_files) != 1 or len(image_files) != 1:
            _add_check(
                report,
                f"orthophoto.preview_{sheet_id}.files",
                "fail",
                "Each preview tile requires exactly one HTML metadata file and one JPEG.",
                {"html_count": len(html_files), "jpeg_count": len(image_files)},
            )
            continue
        try:
            extent = _read_html_extent(html_files[0])
            footprint = box(*extent)
            footprints.append(footprint)
            _add_check(
                report,
                f"orthophoto.preview_{sheet_id}.extent",
                "pass",
                "Official preview metadata contains a valid EPSG:5179 extent.",
                {"extent_epsg5179": list(extent)},
            )
        except (OSError, ValueError) as exc:
            _add_check(
                report,
                f"orthophoto.preview_{sheet_id}.extent",
                "fail",
                "Official preview extent is missing or invalid.",
                {"error": str(exc)},
            )
            continue
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", NotGeoreferencedWarning)
                with rasterio.open(image_files[0]) as image:
                    actual_dimensions = [image.width, image.height]
            dimensions_ok = actual_dimensions == (tile.get("preview_dimensions") or [])
            _add_check(
                report,
                f"orthophoto.preview_{sheet_id}.dimensions",
                "pass" if dimensions_ok else "fail",
                "Preview dimensions match the manifest."
                if dimensions_ok
                else "Preview dimensions differ from the manifest.",
                {
                    "expected": tile.get("preview_dimensions"),
                    "actual": actual_dimensions,
                },
            )
        except Exception as exc:  # noqa: BLE001 - image driver errors vary
            _add_check(
                report,
                f"orthophoto.preview_{sheet_id}.readable",
                "fail",
                "Preview JPEG is unreadable.",
                {"error": str(exc)},
            )
        preview_summaries.append(
            {
                "sheet_id": sheet_id,
                "extent_epsg5179": list(extent),
                "html": _relative(html_files[0], project_root),
                "jpeg": _relative(image_files[0], project_root),
            }
        )
    report["observed"] = {
        "manifest_dataset_id": manifest.get("dataset_id"),
        "original_tile_count": len(manifest.get("tiles") or []),
        "corridor_original_tile_count": sum(
            bool(tile.get("corridor_tile")) for tile in manifest.get("tiles") or []
        ),
        "preview_tile_count": len(preview_tiles),
        "embedded_georeferencing": manifest.get("embedded_georeferencing"),
        "tiles": tile_summaries,
        "preview_tiles": preview_summaries,
    }
    if context and footprints:
        report["coverage"] = coverage_metrics(unary_union(footprints), context)
    _finalize_status(report)
    return report


def _geojson_crs_name(data: dict[str, Any]) -> str | None:
    crs = data.get("crs")
    if not crs:
        return None
    if isinstance(crs, dict):
        properties = crs.get("properties") or {}
        value = properties.get("name") or properties.get("href")
        return str(value) if value else None
    return str(crs)


def validate_precision_road_map(
    project_root: Path, context: CorridorContext | None
) -> dict[str, Any]:
    base = project_root / "data/raw/ngii/precision_road_map/2023/gyeonggi_anyang_pilot"
    manifest_path = base / "source_manifest.json"
    report = _source_report(
        "ngii_hdmap_2023_gyeonggi_anyang_pilot",
        "NGII_HDMAP",
        _relative(base, project_root),
    )
    if not manifest_path.is_file():
        _add_check(report, "hdmap.manifest", "fail", "Source manifest is missing.")
        _finalize_status(report)
        return report
    try:
        manifest = _load_json(manifest_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        _add_check(
            report,
            "hdmap.manifest",
            "fail",
            "Source manifest is unreadable.",
            {"error": str(exc)},
        )
        _finalize_status(report)
        return report
    declared_crs = str(manifest.get("crs") or "")
    files = manifest.get("files") or {}
    summaries: dict[str, Any] = {}
    for filename, declaration in files.items():
        path = base / filename
        if not path.is_file():
            _add_check(
                report,
                f"hdmap.{filename}.exists",
                "fail",
                "Manifest-declared GeoJSON file is missing.",
            )
            continue
        try:
            data = _load_json(path)
            if data.get("type") != "FeatureCollection":
                raise ValueError("root is not a FeatureCollection")
            features = data.get("features") or []
            actual_count = len(features)
            expected_count = declaration.get("features")
            count_ok = actual_count == expected_count
            _add_check(
                report,
                f"hdmap.{filename}.feature_count",
                "pass" if count_ok else "fail",
                "GeoJSON feature count matches the manifest."
                if count_ok
                else "GeoJSON feature count differs from the manifest.",
                {"expected": expected_count, "actual": actual_count},
            )
            crs_name = _geojson_crs_name(data)
            crs_ok = crs_name is None or "4326" in crs_name or "CRS84" in crs_name.upper()
            _add_check(
                report,
                f"hdmap.{filename}.crs",
                "pass" if declared_crs == "EPSG:4326" and crs_ok else "fail",
                "GeoJSON uses RFC 7946 WGS84 coordinates."
                if declared_crs == "EPSG:4326" and crs_ok
                else "GeoJSON CRS differs from the manifest EPSG:4326 declaration.",
                {"manifest_crs": declared_crs, "geojson_crs": crs_name},
            )
            unreadable_geometry = 0
            empty_geometry = 0
            invalid_topology = 0
            out_of_range = 0
            for feature in features:
                geometry_value = feature.get("geometry")
                if geometry_value is None:
                    unreadable_geometry += 1
                    continue
                try:
                    geometry = shape(geometry_value)
                except Exception:
                    unreadable_geometry += 1
                    continue
                if geometry.is_empty:
                    empty_geometry += 1
                    continue
                if not geometry.is_valid:
                    # Several HD-map safety signs are vertical 3D surfaces.  Their
                    # XY projection self-intersects even though coordinates remain
                    # readable; preserve that as a quality warning, not corruption.
                    invalid_topology += 1
                minx, miny, maxx, maxy = geometry.bounds
                if minx < -180 or maxx > 180 or miny < -90 or maxy > 90:
                    out_of_range += 1
            geometry_ok = unreadable_geometry == 0 and out_of_range == 0
            _add_check(
                report,
                f"hdmap.{filename}.geometry_readable",
                "pass" if geometry_ok else "fail",
                "GeoJSON geometries are readable WGS84 coordinates."
                if geometry_ok
                else "GeoJSON contains unreadable or out-of-range geometry.",
                {
                    "unreadable": unreadable_geometry,
                    "out_of_range": out_of_range,
                },
            )
            topology_ok = invalid_topology == 0 and empty_geometry == 0
            _add_check(
                report,
                f"hdmap.{filename}.topology",
                "pass" if topology_ok else "warning",
                "GeoJSON geometries pass 2D topology checks."
                if topology_ok
                else "Some geometries are empty or fail 2D topology checks; they must be excluded or repaired in any later mapping stage.",
                {
                    "empty": empty_geometry,
                    "invalid_2d_topology": invalid_topology,
                },
            )
            summaries[filename] = {
                "features": actual_count,
                "graph_bbox_overlap_declared": declaration.get("graph_bbox_overlap"),
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            _add_check(
                report,
                f"hdmap.{filename}.readable",
                "fail",
                "GeoJSON file is unreadable.",
                {"error": str(exc)},
            )
    report["observed"] = {
        "manifest_dataset_id": manifest.get("dataset_id"),
        "file_count": len(files),
        "declared_crs": declared_crs,
        "files": summaries,
        "notable_graph_bbox_overlap": manifest.get("notable_graph_bbox_overlap"),
    }
    footprint_values = manifest.get("source_bbox_epsg5179")
    if context and isinstance(footprint_values, list) and len(footprint_values) == 4:
        report["coverage"] = coverage_metrics(box(*footprint_values), context)
    else:
        _add_check(
            report,
            "hdmap.coverage_footprint",
            "fail",
            "Manifest source footprint is missing or malformed.",
        )
    _finalize_status(report)
    return report


def validate_crosswalks(
    project_root: Path, context: CorridorContext | None
) -> dict[str, Any]:
    base = project_root / "data/raw/anyang/crosswalks/2026"
    report = _source_report(
        "anyang_crosswalks_20260826",
        "ANYANG_PUBLIC_CROSSWALKS",
        _relative(base, project_root),
    )
    manifest_path = base / "source_manifest.json"
    manifest: dict[str, Any] | None = None
    if not manifest_path.is_file():
        _add_check(
            report,
            "crosswalk.source_manifest",
            "warning",
            "No source manifest is available; a computed hash is reported but cannot be compared.",
        )
    else:
        try:
            manifest = _load_json(manifest_path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            _add_check(
                report,
                "crosswalk.source_manifest",
                "fail",
                "Crosswalk source manifest is unreadable.",
                {"error": str(exc)},
            )
    csv_files = list(base.glob("*.csv")) if base.is_dir() else []
    if len(csv_files) != 1:
        _add_check(
            report,
            "crosswalk.file_selection",
            "fail",
            "Exactly one crosswalk CSV is required.",
            {"found": [_relative(path, project_root) for path in csv_files]},
        )
        _finalize_status(report)
        return report
    csv_path = csv_files[0]
    if manifest is not None:
        declared_file = base / str(manifest.get("file") or "")
        selected_ok = declared_file.resolve() == csv_path.resolve()
        _add_check(
            report,
            "crosswalk.manifest_file_selection",
            "pass" if selected_ok else "fail",
            "Selected crosswalk CSV matches the manifest."
            if selected_ok
            else "Selected crosswalk CSV differs from the manifest.",
            {
                "declared": _relative(declared_file, project_root),
                "selected": _relative(csv_path, project_root),
            },
        )
        _verify_file_declaration(
            report,
            csv_path,
            code_prefix="crosswalk.file",
            expected_size=manifest.get("file_bytes"),
            expected_sha256=manifest.get("file_sha256"),
        )
    required_columns = {
        "관리번호",
        "횡단보도폭",
        "횡단보도길이",
        "관할지역",
        "위도",
        "경도",
        "보도턱낮춤여부",
        "점자블록유무",
    }
    rows: list[dict[str, str]] = []
    try:
        with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            fieldnames = set(reader.fieldnames or [])
            if not required_columns.issubset(fieldnames):
                raise ValueError(
                    f"missing columns: {sorted(required_columns - fieldnames)}"
                )
            rows = [dict(row) for row in reader]
    except (OSError, UnicodeError, ValueError, csv.Error) as exc:
        _add_check(
            report,
            "crosswalk.readable",
            "fail",
            "Crosswalk CSV is unreadable or has an unexpected schema.",
            {"error": str(exc)},
        )
        _finalize_status(report)
        return report
    identifiers = [(row.get("관리번호") or "").strip() for row in rows]
    duplicate_ids = len(identifiers) - len(set(identifiers))
    missing_ids = sum(not identifier for identifier in identifiers)
    id_ok = duplicate_ids == missing_ids == 0
    _add_check(
        report,
        "crosswalk.identifiers",
        "pass" if id_ok else "fail",
        "Crosswalk management identifiers are present and unique."
        if id_ok
        else "Crosswalk management identifiers are missing or duplicated.",
        {"duplicate_count": duplicate_ids, "missing_count": missing_ids},
    )
    points_wgs84: list[Any] = []
    invalid_coordinates = 0
    for row in rows:
        try:
            lat = float((row.get("위도") or "").strip())
            lon = float((row.get("경도") or "").strip())
        except ValueError:
            invalid_coordinates += 1
            continue
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            invalid_coordinates += 1
            continue
        points_wgs84.append(Point(lon, lat))
    _add_check(
        report,
        "crosswalk.coordinates",
        "pass" if invalid_coordinates == 0 else "fail",
        "All crosswalk coordinates are valid WGS84 values."
        if invalid_coordinates == 0
        else "Crosswalk CSV contains missing or invalid coordinates.",
        {"invalid_count": invalid_coordinates},
    )
    blank_curb = sum(not (row.get("보도턱낮춤여부") or "").strip() for row in rows)
    blank_tactile = sum(not (row.get("점자블록유무") or "").strip() for row in rows)
    unknown_any = sum(
        not (row.get("보도턱낮춤여부") or "").strip()
        or not (row.get("점자블록유무") or "").strip()
        for row in rows
    )
    observed: dict[str, Any] = {
        "manifest_dataset_id": manifest.get("dataset_id") if manifest else None,
        "file": _relative(csv_path, project_root),
        "bytes": csv_path.stat().st_size,
        "sha256": sha256_file(csv_path),
        "row_count": len(rows),
        "valid_coordinate_count": len(points_wgs84),
        "duplicate_management_id_count": duplicate_ids,
        "blank_curb_lowering_count": blank_curb,
        "blank_tactile_block_count": blank_tactile,
        "rows_with_unknown_accessibility_count": unknown_any,
        "unknown_policy": "blank remains null/unknown; it is never converted to false",
    }
    if manifest is not None:
        row_count_ok = len(rows) == int(manifest.get("row_count") or -1)
        _add_check(
            report,
            "crosswalk.manifest_row_count",
            "pass" if row_count_ok else "fail",
            "Crosswalk row count matches the source manifest."
            if row_count_ok
            else "Crosswalk row count differs from the source manifest.",
            {"declared": manifest.get("row_count"), "actual": len(rows)},
        )
    if context and points_wgs84:
        to_5179 = Transformer.from_crs("EPSG:4326", "EPSG:5179", always_xy=True)
        points_5179 = [transform(to_5179.transform, point) for point in points_wgs84]
        bbox_polygon = box(*context.graph_bbox_wgs84)
        observed.update(
            {
                "within_graph_bbox_count": sum(
                    bbox_polygon.covers(point) for point in points_wgs84
                ),
                "within_corridor_30m_count": sum(
                    context.mask_30m_5179.covers(point) for point in points_5179
                ),
                "within_context_100m_count": sum(
                    context.mask_100m_5179.covers(point) for point in points_5179
                ),
            }
        )
    report["observed"] = observed
    _finalize_status(report)
    return report


def validate_off_corridor_continuous_map(project_root: Path) -> dict[str, Any]:
    base = (
        project_root
        / "data/raw/ngii/continuous_digital_map/2026/off_corridor_selection_202609174822"
    )
    manifest_path = base / "source_manifest.json"
    report = _source_report(
        "ngii_continuous_digital_map_off_corridor",
        "NGII_CONTINUOUS_DIGITAL_MAP",
        _relative(base, project_root),
        required=False,
    )
    report["coverage_excluded"] = True
    report["exclusion_reason"] = (
        "The retained selection is outside the representative corridor and is not an evaluation input."
    )
    if not manifest_path.is_file():
        _add_check(
            report,
            "continuous_map.manifest",
            "hold",
            "Off-corridor hold manifest is absent; this does not affect corridor validation.",
        )
        _finalize_status(report, force_hold=True)
        return report
    try:
        manifest = _load_json(manifest_path)
        archive_path = base / str(manifest.get("archive") or "")
        if not archive_path.is_file():
            _add_check(
                report,
                "continuous_map.archive",
                "hold",
                "Retained off-corridor archive is missing; it remains excluded from evaluation.",
            )
        else:
            expected_size = manifest.get("archive_bytes")
            actual_size = archive_path.stat().st_size
            size_ok = expected_size == actual_size
            try:
                with ZipFile(archive_path) as archive:
                    corrupt_member = archive.testzip()
            except (BadZipFile, OSError) as exc:
                corrupt_member = str(exc)
            integrity_ok = size_ok and corrupt_member is None
            _add_check(
                report,
                "continuous_map.retained_archive",
                "hold" if integrity_ok else "warning",
                "Retained off-corridor archive is intact but intentionally excluded."
                if integrity_ok
                else "Retained off-corridor archive failed an integrity check; corridor validation is unaffected.",
                {
                    "expected_bytes": expected_size,
                    "actual_bytes": actual_size,
                    "corrupt_member_or_error": corrupt_member,
                },
            )
            report["observed"] = {
                "manifest_dataset_id": manifest.get("dataset_id"),
                "manifest_status": manifest.get("status"),
                "archive": _relative(archive_path, project_root),
                "archive_sha256_computed": sha256_file(archive_path),
                "declared_sha256": None,
                "local_feature_extent_epsg5179_approx": manifest.get(
                    "local_feature_extent_epsg5179_approx"
                ),
            }
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        _add_check(
            report,
            "continuous_map.manifest",
            "warning",
            "Off-corridor hold manifest is unreadable; corridor validation is unaffected.",
            {"error": str(exc)},
        )
    _finalize_status(report, force_hold=True)
    return report


def _summary(graph: dict[str, Any], sources: list[dict[str, Any]]) -> dict[str, Any]:
    targets = [graph, *sources]
    target_counts = Counter(target.get("status", "fail") for target in targets)
    check_counts = Counter(
        check.get("status", "fail")
        for target in targets
        for check in target.get("checks", [])
    )
    global_status = "fail" if target_counts["fail"] else (
        "warning" if target_counts["warning"] else "pass"
    )
    return {
        "status": global_status,
        "source_count": len(sources),
        "validation_target_count": len(targets),
        "pass": target_counts["pass"],
        "warning": target_counts["warning"],
        "fail": target_counts["fail"],
        "hold": target_counts["hold"],
        "check_counts": {
            "pass": check_counts["pass"],
            "warning": check_counts["warning"],
            "fail": check_counts["fail"],
            "hold": check_counts["hold"],
        },
    }


def run_validation(
    project_root: Path,
    output_dir: Path,
    *,
    created_at: str | None = None,
) -> dict[str, Any]:
    if _GEO_IMPORT_ERROR is not None:
        raise RuntimeError(
            'Geospatial dependencies are missing. Install with: pip install -e ".[geo]"'
        ) from _GEO_IMPORT_ERROR
    project_root = project_root.resolve()
    output_dir = output_dir if output_dir.is_absolute() else project_root / output_dir
    timestamp = created_at or datetime.now().astimezone().isoformat(timespec="seconds")
    context, graph_report = build_corridor_context(
        project_root / GRAPH_RELATIVE_PATH,
        project_root / RAW_GRAPH_RELATIVE_PATH,
        project_root / RAW_GRAPH_METADATA_RELATIVE_PATH,
    )
    graph_report["path"] = _relative(project_root / GRAPH_RELATIVE_PATH, project_root)

    sources = [
        validate_topographic_map(project_root, context),
        validate_dem(project_root, context),
        validate_orthophoto(project_root, context),
        validate_precision_road_map(project_root, context),
        validate_crosswalks(project_root, context),
        validate_off_corridor_continuous_map(project_root),
    ]
    report = {
        "schema_version": "1.0",
        "created_at": timestamp,
        "derived": True,
        "verified": False,
        "graph_update_allowed": False,
        "common_validation": {
            "summary": _summary(graph_report, sources),
            "graph": graph_report,
            "sources": sources,
            "policy": {
                "raw_inputs_mutated": False,
                "routing_graph_mutated": False,
                "unknown_values_imputed": False,
                "ai_or_derived_values_promoted_to_verified": False,
            },
        },
    }
    if context is not None:
        _atomic_write_json(
            output_dir / "corridor_mask.geojson",
            corridor_mask_geojson(context, timestamp),
        )
    _atomic_write_json(output_dir / "metrics.json", report)
    return report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate NaVi spatial source integrity, CRS, and corridor coverage."
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Repository root (defaults to the parent of scripts/).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/processed/evaluation"),
        help="Output directory, relative to project root unless absolute.",
    )
    parser.add_argument(
        "--created-at",
        help="Fixed ISO-8601 output timestamp for reproducible test fixtures.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        report = run_validation(
            args.project_root, args.output_dir, created_at=args.created_at
        )
    except Exception as exc:  # noqa: BLE001 - CLI contract reserves exit 2
        print(f"spatial source validator internal error: {exc}", file=sys.stderr)
        return 2
    summary = report["common_validation"]["summary"]
    print(
        "spatial source validation: "
        f"status={summary['status']} pass={summary['pass']} "
        f"warning={summary['warning']} fail={summary['fail']} hold={summary['hold']}"
    )
    return 1 if summary["fail"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
