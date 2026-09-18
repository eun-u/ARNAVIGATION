"""Build a provisional orthophoto index and visual-review queue.

The raw TIFFs have no embedded GeoTIFF transform.  Official NGII preview
metadata supplies sheet extents in EPSG:5179, so this evaluator reconstructs
an affine transform as a *sidecar only*.  It never rewrites the imagery or the
routing graph, and geometry correction remains blocked until control-point
RMSE has been measured.
"""

from __future__ import annotations

import argparse
import csv
import math
import re
import sys
import warnings
from collections import Counter
from pathlib import Path
from typing import Any

import rasterio
from pyproj import Transformer
from rasterio.errors import NotGeoreferencedWarning
from rasterio.transform import from_bounds, rowcol
from shapely.geometry import Point, box
from shapely.ops import unary_union

try:
    from scripts.spatial_evaluation_common import (
        EdgeMatcher,
        PROVENANCE_FLAGS,
        feature_collection,
        file_sha256,
        geometry_feature,
        load_graph_edges,
        load_json,
        now_iso,
        relative_path,
        transformed,
        write_json,
    )
except ModuleNotFoundError:  # Direct execution from scripts/
    from spatial_evaluation_common import (  # type: ignore[no-redef]
        EdgeMatcher,
        PROVENANCE_FLAGS,
        feature_collection,
        file_sha256,
        geometry_feature,
        load_graph_edges,
        load_json,
        now_iso,
        relative_path,
        transformed,
        write_json,
    )


ORTHO_DIR = Path("data/raw/ngii/orthophoto/2025")
PREVIEW_DIR = Path("data/raw/ngii/orthophoto_preview/2025")
CROSSWALK_DIR = Path("data/raw/anyang/crosswalks/2026")
DEFAULT_OUTPUT_DIR = Path("data/processed/evaluation/orthophoto")
EXTENT_CRS = "EPSG:5179"
EXTENT_PATTERN = re.compile(
    r'name=["\'](?P<name>minx|miny|maxx|maxy)["\'][^>]*'
    r'value=["\'](?P<value>[-+0-9.eE]+)',
    re.IGNORECASE,
)


def parse_official_extent(path: Path) -> tuple[float, float, float, float]:
    text = path.read_text(encoding="utf-8", errors="replace")
    values = {
        match.group("name").lower(): float(match.group("value"))
        for match in EXTENT_PATTERN.finditer(text)
    }
    required = {"minx", "miny", "maxx", "maxy"}
    if set(values) != required:
        raise ValueError(f"official extent is incomplete: {sorted(required - set(values))}")
    extent = (values["minx"], values["miny"], values["maxx"], values["maxy"])
    if extent[0] >= extent[2] or extent[1] >= extent[3]:
        raise ValueError(f"official extent order is invalid: {extent}")
    return extent


def _read_crosswalks(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"관리번호", "위도", "경도", "보도턱낮춤여부", "점자블록유무"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"crosswalk CSV columns are missing: {sorted(missing)}")
        for raw in reader:
            try:
                lat = float(raw["위도"])
                lon = float(raw["경도"])
            except (TypeError, ValueError):
                continue
            rows.append(
                {
                    "crosswalk_id": str(raw["관리번호"]).strip(),
                    "point_wgs84": Point(lon, lat),
                    "curb_lowering": (raw.get("보도턱낮춤여부") or "").strip() or None,
                    "tactile_block": (raw.get("점자블록유무") or "").strip() or None,
                }
            )
    return rows


def _coverage(tile_union: Any, edges: list[Any]) -> dict[str, Any]:
    intersected = [edge for edge in edges if tile_union.intersects(edge)]
    total_length = sum(float(edge.length) for edge in edges)
    covered_length = sum(float(edge.intersection(tile_union).length) for edge in edges)
    return {
        "intersected_edge_count": len(intersected),
        "intersected_edge_pct": round(100.0 * len(intersected) / len(edges), 3),
        "covered_edge_length_m": round(covered_length, 3),
        "covered_edge_length_pct": round(
            100.0 * covered_length / total_length if total_length else 0.0, 3
        ),
    }


def run_orthophoto_evaluation(
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
    original_manifest = load_json(project_root / ORTHO_DIR / "source_manifest.json")
    preview_manifest = load_json(project_root / PREVIEW_DIR / "source_manifest.json")
    original_by_sheet = {
        str(tile["sheet_id"]): tile for tile in original_manifest.get("tiles") or []
    }
    preview_by_sheet = {
        str(tile["sheet_id"]): tile for tile in preview_manifest.get("tiles") or []
    }

    index_features: list[dict[str, Any]] = []
    sidecars: dict[str, dict[str, Any]] = {}
    footprints: dict[str, Any] = {}
    pixel_sizes: list[float] = []
    integrity_errors: list[str] = []
    skipped_sheets: list[str] = []
    to_wgs84 = Transformer.from_crs(EXTENT_CRS, "EPSG:4326", always_xy=True)

    for sheet_id, declaration in sorted(original_by_sheet.items()):
        if not declaration.get("corridor_tile"):
            skipped_sheets.append(sheet_id)
            continue
        preview = preview_by_sheet.get(sheet_id)
        if preview is None:
            integrity_errors.append(f"{sheet_id}: preview declaration missing")
            continue
        raster_path = project_root / ORTHO_DIR / str(declaration["raster"])
        html_files = sorted((project_root / PREVIEW_DIR / sheet_id).glob("*.html"))
        if len(html_files) != 1:
            integrity_errors.append(f"{sheet_id}: expected one preview HTML")
            continue
        expected_hash = str(declaration.get("raster_sha256") or "").lower()
        actual_hash = file_sha256(raster_path)
        if expected_hash and actual_hash.lower() != expected_hash:
            integrity_errors.append(f"{sheet_id}: raster SHA-256 mismatch")
            continue
        extent = parse_official_extent(html_files[0])
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", NotGeoreferencedWarning)
            with rasterio.open(raster_path) as dataset:
                width, height = dataset.width, dataset.height
                embedded_crs = dataset.crs.to_string() if dataset.crs else None
                embedded_transform = list(dataset.transform)
        expected_dimensions = list(declaration.get("dimensions") or [])
        if [width, height] != expected_dimensions:
            integrity_errors.append(
                f"{sheet_id}: dimensions {[width, height]} != {expected_dimensions}"
            )
            continue
        affine = from_bounds(*extent, width=width, height=height)
        pixel_x = abs(float(affine.a))
        pixel_y = abs(float(affine.e))
        pixel_sizes.extend([pixel_x, pixel_y])
        footprint_5179 = box(*extent)
        footprints[sheet_id] = footprint_5179
        footprint_wgs84 = transformed(footprint_5179, EXTENT_CRS, "EPSG:4326")
        sidecar = {
            "schema_version": "1.0",
            "created_at": timestamp,
            "sheet_id": sheet_id,
            "raster": relative_path(raster_path, project_root),
            "raster_sha256": actual_hash,
            "extent_source": relative_path(html_files[0], project_root),
            "extent_crs": EXTENT_CRS,
            "bounds": [round(value, 6) for value in extent],
            "dimensions": [width, height],
            "affine_gdal_order": [
                float(affine.c),
                float(affine.a),
                float(affine.b),
                float(affine.f),
                float(affine.d),
                float(affine.e),
            ],
            "pixel_size_m": [pixel_x, pixel_y],
            "embedded_crs": embedded_crs,
            "embedded_transform": embedded_transform,
            "control_point_count": 0,
            "control_point_rmse_m": None,
            "georeferencing_status": "provisional_extent_reconstruction",
            "tiff_rewritten": False,
            **PROVENANCE_FLAGS,
        }
        sidecars[sheet_id] = sidecar
        write_json(output_dir / "georeferencing" / f"{sheet_id}.json", sidecar)
        index_features.append(
            geometry_feature(
                footprint_wgs84,
                {
                    "sheet_id": sheet_id,
                    "raster": relative_path(raster_path, project_root),
                    "extent_source": relative_path(html_files[0], project_root),
                    "extent_crs": EXTENT_CRS,
                    "pixel_size_x_m": round(pixel_x, 6),
                    "pixel_size_y_m": round(pixel_y, 6),
                    "control_point_rmse_m": None,
                    "visual_qa_allowed": True,
                    "geometry_correction_allowed": False,
                },
            )
        )

    crosswalk_files = sorted((project_root / CROSSWALK_DIR).glob("*.csv"))
    if len(crosswalk_files) != 1:
        raise RuntimeError("exactly one Anyang crosswalk CSV is required")
    review_features: list[dict[str, Any]] = []
    review_counts: Counter[str] = Counter()
    for row in _read_crosswalks(crosswalk_files[0]):
        point_5179 = transformed(row["point_wgs84"], "EPSG:4326", EXTENT_CRS)
        if not context_100m.covers(point_5179):
            continue
        containing = [sheet for sheet, polygon in footprints.items() if polygon.covers(point_5179)]
        if not containing:
            review_counts["outside_reconstructed_tiles"] += 1
            continue
        sheet_id = sorted(containing)[0]
        affine_values = sidecars[sheet_id]["affine_gdal_order"]
        affine = rasterio.Affine.from_gdal(*affine_values)
        pixel_row, pixel_col = rowcol(affine, point_5179.x, point_5179.y)
        edge_match = matcher.match(point_5179)
        review_counts[edge_match["mapping_status"]] += 1
        review_features.append(
            geometry_feature(
                row["point_wgs84"],
                {
                    "review_id": f"ortho-crosswalk-{row['crosswalk_id']}",
                    "candidate_type": "orthophoto_crosswalk_visual_qa",
                    "crosswalk_id": row["crosswalk_id"],
                    "sheet_id": sheet_id,
                    "pixel_row": int(pixel_row),
                    "pixel_col": int(pixel_col),
                    "graph_mapping_status": edge_match["mapping_status"],
                    "graph_edge_id": edge_match["edge_id"],
                    "candidate_graph_edge_ids": edge_match["candidate_edge_ids"],
                    "graph_distance_m": edge_match["distance_m"],
                    "curb_lowering_source_value": row["curb_lowering"],
                    "tactile_block_source_value": row["tactile_block"],
                    "visual_review_status": "pending",
                    "claimed_mismatch": False,
                    "geometry_correction_allowed": False,
                },
            )
        )

    tile_union = unary_union(list(footprints.values())) if footprints else None
    gsd_target = float(original_manifest.get("metadata_ground_sample_distance_m") or 0.25)
    max_gsd_error = max((abs(value - gsd_target) for value in pixel_sizes), default=math.inf)
    checks = [
        {
            "code": "orthophoto_eval.integrity",
            "status": "pass" if not integrity_errors else "fail",
            "message": "Corridor TIFF declarations, hashes, dimensions, and preview extents agree."
            if not integrity_errors
            else "One or more corridor tiles failed integrity checks.",
            "evidence": {"errors": integrity_errors},
        },
        {
            "code": "orthophoto_eval.pixel_size",
            "status": "pass" if max_gsd_error <= 0.01 else "warning",
            "message": "Reconstructed pixel sizes agree with the declared 25 cm product."
            if max_gsd_error <= 0.01
            else "Reconstructed pixel size differs from the declared product resolution.",
            "evidence": {"declared_m": gsd_target, "max_abs_error_m": round(max_gsd_error, 6)},
        },
        {
            "code": "orthophoto_eval.control_point_rmse",
            "status": "hold",
            "message": "Geometry correction is blocked until independent control points produce an RMSE.",
            "evidence": {"control_point_count": 0, "rmse_m": None},
        },
        {
            "code": "orthophoto_eval.graph_safety_boundary",
            "status": "pass",
            "message": "Imagery outputs are visual-review evidence only and cannot mutate the graph.",
        },
    ]
    status = "fail" if integrity_errors else "warning"
    metrics = {
        "schema_version": "1.0",
        "created_at": timestamp,
        "status": status,
        "dataset_id": original_manifest.get("dataset_id"),
        "graph": graph,
        "metrics": {
            "corridor_tile_count": len(footprints),
            "skipped_non_corridor_sheets": skipped_sheets,
            "pixel_size_m_min": round(min(pixel_sizes), 6) if pixel_sizes else None,
            "pixel_size_m_max": round(max(pixel_sizes), 6) if pixel_sizes else None,
            "control_point_count": 0,
            "control_point_rmse_m": None,
            "visual_review_candidate_count": len(review_features),
            "candidate_graph_match_counts": dict(sorted(review_counts.items())),
            "graph_coverage": _coverage(tile_union, [edge.geometry_5179 for edge in edges])
            if tile_union is not None
            else None,
        },
        "decision": {
            "visual_spatial_qa": "partial_accept",
            "automatic_geometry_correction": "hold",
            "reason": "official extents reconstruct the sheet footprint, but no independent control-point RMSE exists",
        },
        "checks": checks,
        "policy": {
            **PROVENANCE_FLAGS,
            "routing_graph_mutated": False,
            "raw_tiff_mutated": False,
        },
    }
    write_json(
        output_dir / "index.geojson",
        feature_collection(
            index_features,
            created_at=timestamp,
            source_graph_sha256=graph["graph_sha256"],
            metadata={"purpose": "provisional_orthophoto_sheet_index", "metric_crs": EXTENT_CRS},
        ),
    )
    write_json(
        output_dir / "geometry_review_candidates.geojson",
        feature_collection(
            review_features,
            created_at=timestamp,
            source_graph_sha256=graph["graph_sha256"],
            metadata={"purpose": "human_visual_review_queue", "visual_review_status": "pending"},
        ),
    )
    write_json(output_dir / "metrics.json", metrics)
    return metrics


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate orthophotos for visual QA only.")
    parser.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--created-at")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = run_orthophoto_evaluation(
            args.project_root, args.output_dir, created_at=args.created_at
        )
    except Exception as exc:  # noqa: BLE001
        print(f"Orthophoto evaluation failed: {exc}", file=sys.stderr)
        return 2
    values = result["metrics"]
    print(
        "Orthophoto evaluation: "
        f"status={result['status']} tiles={values['corridor_tile_count']} "
        f"review_candidates={values['visual_review_candidate_count']} rmse=not_measured"
    )
    return 1 if result["status"] == "fail" else 0


if __name__ == "__main__":
    raise SystemExit(main())
