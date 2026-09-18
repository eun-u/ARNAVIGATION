"""Evaluate the NGII DEM as an unverified routing-graph sidecar.

The evaluator deliberately never writes to the routing graph.  It samples the
coarse DEM along every baseline edge, compares nearest and bilinear sampling,
and emits candidates whose provenance and non-production status are explicit.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable
from zipfile import ZipFile

import numpy as np
import rasterio

try:
    from scripts.validate_spatial_sources import (
        GRAPH_RELATIVE_PATH,
        RAW_GRAPH_METADATA_RELATIVE_PATH,
        RAW_GRAPH_RELATIVE_PATH,
        CorridorContext,
        build_corridor_context,
        sha256_file,
    )
except ModuleNotFoundError:  # Direct execution: python scripts/evaluate_dem.py
    from validate_spatial_sources import (  # type: ignore[no-redef]
        GRAPH_RELATIVE_PATH,
        RAW_GRAPH_METADATA_RELATIVE_PATH,
        RAW_GRAPH_RELATIVE_PATH,
        CorridorContext,
        build_corridor_context,
        sha256_file,
    )


DATASET_ID = "ngii_public_dem_37612_2025"
DEM_RELATIVE_PATH = Path("data/raw/ngii/dem/2025/37612")
DEFAULT_OUTPUT_DIR = Path("data/processed/evaluation/dem")
CSV_FIELDS = (
    "edge_id",
    "edge_length_m",
    "elevation_start_m",
    "elevation_end_m",
    "elevation_start_nearest_m",
    "elevation_end_nearest_m",
    "slope_pct_signed_candidate",
    "slope_pct_abs_candidate",
    "slope_pct_signed_nearest_candidate",
    "max_segment_slope_pct_candidate",
    "sample_count",
    "valid_sample_count",
    "distinct_cell_count",
    "dem_resolution_m",
    "nearest_bilinear_endpoint_max_diff_m",
    "quality_flag",
    "hard_constraint_eligible",
    "source_dataset_id",
    "source_archive_sha256",
    "source_graph_sha256",
    "derived",
    "verified",
    "graph_update_allowed",
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
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    os.replace(temporary, path)


def _rounded(value: float | None, digits: int = 6) -> float | None:
    if value is None or not math.isfinite(value):
        return None
    return round(float(value), digits)


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, math.ceil(percentile * len(ordered)) - 1)
    return round(ordered[index], 6)


def sample_distances(length_m: float, max_interval_m: float = 45.0) -> list[float]:
    """Return endpoint-inclusive distances whose gaps never exceed the limit."""

    if length_m <= 0:
        return [0.0]
    segment_count = max(1, math.ceil(length_m / max_interval_m))
    return [length_m * index / segment_count for index in range(segment_count + 1)]


def nearest_sample(
    band: np.ma.MaskedArray,
    transform: Any,
    x: float,
    y: float,
) -> tuple[float | None, tuple[int, int] | None]:
    """Sample the cell containing ``x, y`` without resampling the raster."""

    col_float, row_float = (~transform) @ (x, y)
    row = math.floor(row_float)
    col = math.floor(col_float)
    if row < 0 or col < 0 or row >= band.shape[0] or col >= band.shape[1]:
        return None, None
    value = band[row, col]
    if np.ma.is_masked(value) or not math.isfinite(float(value)):
        return None, (row, col)
    return float(value), (row, col)


def bilinear_sample(
    band: np.ma.MaskedArray,
    transform: Any,
    x: float,
    y: float,
) -> float | None:
    """Sample at a world coordinate using the four surrounding cell centres."""

    col_corner, row_corner = (~transform) @ (x, y)
    col_value = col_corner - 0.5
    row_value = row_corner - 0.5
    col0 = math.floor(col_value)
    row0 = math.floor(row_value)
    col_fraction = col_value - col0
    row_fraction = row_value - row0
    neighbours = (
        (row0, col0, (1.0 - row_fraction) * (1.0 - col_fraction)),
        (row0, col0 + 1, (1.0 - row_fraction) * col_fraction),
        (row0 + 1, col0, row_fraction * (1.0 - col_fraction)),
        (row0 + 1, col0 + 1, row_fraction * col_fraction),
    )
    result = 0.0
    for row, col, weight in neighbours:
        if weight <= 1e-12:
            continue
        if row < 0 or col < 0 or row >= band.shape[0] or col >= band.shape[1]:
            return None
        value = band[row, col]
        if np.ma.is_masked(value) or not math.isfinite(float(value)):
            return None
        result += float(value) * weight
    return result


def _sample_edge(
    edge_id: str,
    geometry: Any,
    band: np.ma.MaskedArray,
    transform: Any,
    resolution_m: float,
    archive_sha256: str,
    graph_sha256: str,
) -> dict[str, Any]:
    length_m = float(geometry.length)
    distances = sample_distances(length_m)
    nearest_values: list[float | None] = []
    bilinear_values: list[float | None] = []
    cells: list[tuple[int, int]] = []
    for distance in distances:
        point = geometry.interpolate(distance)
        nearest, cell = nearest_sample(band, transform, point.x, point.y)
        bilinear = bilinear_sample(band, transform, point.x, point.y)
        nearest_values.append(nearest)
        bilinear_values.append(bilinear)
        if cell is not None:
            cells.append(cell)

    all_valid = all(value is not None for value in nearest_values + bilinear_values)
    valid_sample_count = sum(
        nearest is not None and bilinear is not None
        for nearest, bilinear in zip(nearest_values, bilinear_values, strict=True)
    )
    distinct_cell_count = len(set(cells))
    if not all_valid or length_m <= 1e-9:
        quality_flag = "outside_or_nodata"
    elif distinct_cell_count < 3:
        quality_flag = "insufficient_resolution"
    else:
        quality_flag = "coarse_context_only"

    start_bilinear = bilinear_values[0] if all_valid else None
    end_bilinear = bilinear_values[-1] if all_valid else None
    start_nearest = nearest_values[0] if all_valid else None
    end_nearest = nearest_values[-1] if all_valid else None
    signed_slope = None
    nearest_signed_slope = None
    max_segment_slope = None
    endpoint_difference = None
    if all_valid and length_m > 1e-9:
        assert start_bilinear is not None and end_bilinear is not None
        assert start_nearest is not None and end_nearest is not None
        signed_slope = 100.0 * (end_bilinear - start_bilinear) / length_m
        nearest_signed_slope = 100.0 * (end_nearest - start_nearest) / length_m
        segment_slopes = [
            abs(100.0 * (float(end) - float(start)) / (distances[index + 1] - distances[index]))
            for index, (start, end) in enumerate(
                zip(bilinear_values, bilinear_values[1:], strict=False)
            )
            if start is not None
            and end is not None
            and distances[index + 1] > distances[index]
        ]
        max_segment_slope = max(segment_slopes) if segment_slopes else None
        endpoint_difference = max(
            abs(start_bilinear - start_nearest),
            abs(end_bilinear - end_nearest),
        )

    return {
        "edge_id": edge_id,
        "edge_length_m": _rounded(length_m, 3),
        "elevation_start_m": _rounded(start_bilinear, 3),
        "elevation_end_m": _rounded(end_bilinear, 3),
        "elevation_start_nearest_m": _rounded(start_nearest, 3),
        "elevation_end_nearest_m": _rounded(end_nearest, 3),
        "slope_pct_signed_candidate": _rounded(signed_slope, 6),
        "slope_pct_abs_candidate": _rounded(abs(signed_slope) if signed_slope is not None else None, 6),
        "slope_pct_signed_nearest_candidate": _rounded(nearest_signed_slope, 6),
        "max_segment_slope_pct_candidate": _rounded(max_segment_slope, 6),
        "sample_count": len(distances),
        "valid_sample_count": valid_sample_count,
        "distinct_cell_count": distinct_cell_count,
        "dem_resolution_m": _rounded(resolution_m, 3),
        "nearest_bilinear_endpoint_max_diff_m": _rounded(endpoint_difference, 6),
        "quality_flag": quality_flag,
        "hard_constraint_eligible": False,
        "source_dataset_id": DATASET_ID,
        "source_archive_sha256": archive_sha256,
        "source_graph_sha256": graph_sha256,
        "derived": True,
        "verified": False,
        "graph_update_allowed": False,
    }


def _metrics(
    context: CorridorContext,
    rows: list[dict[str, Any]],
    *,
    created_at: str,
    archive_relative: str,
    archive_sha256: str,
    raster_member: str,
    raster_metadata: dict[str, Any],
) -> dict[str, Any]:
    quality_counts = Counter(str(row["quality_flag"]) for row in rows)
    valid_rows = [row for row in rows if row["quality_flag"] != "outside_or_nodata"]
    valid_length = sum(float(row["edge_length_m"]) for row in valid_rows)
    slopes = [
        float(row["slope_pct_abs_candidate"])
        for row in valid_rows
        if row["slope_pct_abs_candidate"] is not None
    ]
    sensitivity = [
        float(row["nearest_bilinear_endpoint_max_diff_m"])
        for row in valid_rows
        if row["nearest_bilinear_endpoint_max_diff_m"] is not None
    ]
    valid_edge_pct = 100.0 * len(valid_rows) / len(rows) if rows else 0.0
    valid_length_pct = (
        100.0 * valid_length / context.total_edge_length_m
        if context.total_edge_length_m
        else 0.0
    )
    resolution = float(raster_metadata["resolution_m"])
    checks = [
        {
            "code": "dem_eval.valid_edge_length_coverage",
            "status": "pass" if valid_length_pct >= 95.0 else "warning",
            "message": "Valid DEM samples cover at least 95% of graph edge length."
            if valid_length_pct >= 95.0
            else "Valid DEM samples cover less than 95% of graph edge length.",
            "evidence": {"valid_edge_length_pct": round(valid_length_pct, 3)},
        },
        {
            "code": "dem_eval.edge_resolution",
            "status": "warning" if resolution >= 90.0 else "pass",
            "message": "The DEM is too coarse for edge-level hard constraints."
            if resolution >= 90.0
            else "The DEM is finer than the coarse-resolution warning gate.",
            "evidence": {"resolution_m": resolution},
        },
        {
            "code": "dem_eval.graph_safety_boundary",
            "status": "pass",
            "message": "Every row is unverified and ineligible for graph mutation or hard constraints.",
        },
    ]
    status = "fail" if any(item["status"] == "fail" for item in checks) else (
        "warning" if any(item["status"] == "warning" for item in checks) else "pass"
    )
    return {
        "schema_version": "1.0",
        "created_at": created_at,
        "status": status,
        "dataset_id": DATASET_ID,
        "source": {
            "archive": archive_relative,
            "archive_sha256": archive_sha256,
            "raster_member": raster_member,
            **raster_metadata,
        },
        "graph": {
            "source_graph_sha256": context.graph_sha256,
            "edge_count": context.edge_count,
            "total_edge_length_m": round(context.total_edge_length_m, 3),
        },
        "metrics": {
            "evaluated_edge_count": len(rows),
            "valid_edge_count": len(valid_rows),
            "valid_edge_pct": round(valid_edge_pct, 3),
            "valid_edge_length_pct": round(valid_length_pct, 3),
            "quality_flag_counts": dict(sorted(quality_counts.items())),
            "same_cell_endpoint_edge_count": sum(
                int(row["distinct_cell_count"]) == 1 for row in rows
            ),
            "fewer_than_three_cells_edge_count": sum(
                int(row["distinct_cell_count"]) < 3 for row in rows
            ),
            "slope_pct_abs": {
                "median": _percentile(slopes, 0.5),
                "p95": _percentile(slopes, 0.95),
                "max": _rounded(max(slopes) if slopes else None, 6),
            },
            "nearest_bilinear_endpoint_difference_m": {
                "median": _percentile(sensitivity, 0.5),
                "p95": _percentile(sensitivity, 0.95),
                "max": _rounded(max(sensitivity) if sensitivity else None, 6),
            },
            "hard_constraint_eligible_edge_count": 0,
        },
        "checks": checks,
        "policy": {
            "derived": True,
            "verified": False,
            "graph_update_allowed": False,
            "routing_graph_mutated": False,
            "allowed_use": "coarse_terrain_context_only",
        },
    }


def run_dem_evaluation(
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
        raise RuntimeError("Baseline graph validation failed; DEM evaluation was not run.")

    dem_dir = project_root / DEM_RELATIVE_PATH
    archives = sorted(dem_dir.glob("*.zip"))
    if len(archives) != 1:
        raise RuntimeError(f"Expected exactly one DEM archive, found {len(archives)}.")
    archive_path = archives[0]
    archive_sha = sha256_file(archive_path)
    with ZipFile(archive_path) as archive:
        corrupt_member = archive.testzip()
        members = [name for name in archive.namelist() if name.lower().endswith(".img")]
    if corrupt_member or len(members) != 1:
        raise RuntimeError(
            f"DEM archive integrity failed: corrupt={corrupt_member!r}, IMG members={members!r}"
        )

    raster_member = members[0]
    vsi_path = f"/vsizip/{archive_path.resolve().as_posix()}/{raster_member}"
    with rasterio.open(vsi_path) as dataset:
        if dataset.crs is None or dataset.crs.to_epsg() != 5179:
            raise RuntimeError(f"DEM CRS must be EPSG:5179, observed {dataset.crs!s}.")
        band = dataset.read(1, masked=True)
        resolution_m = max(abs(float(dataset.res[0])), abs(float(dataset.res[1])))
        raster_metadata = {
            "driver": dataset.driver,
            "crs": dataset.crs.to_string(),
            "width": dataset.width,
            "height": dataset.height,
            "dtype": dataset.dtypes[0],
            "nodata": dataset.nodata,
            "resolution_m": resolution_m,
            "bounds_epsg5179": [float(value) for value in dataset.bounds],
        }
        rows = [
            _sample_edge(
                edge_id,
                geometry,
                band,
                dataset.transform,
                resolution_m,
                archive_sha,
                context.graph_sha256,
            )
            for edge_id, geometry in zip(
                context.edge_ids, context.edges_5179, strict=True
            )
        ]

    try:
        archive_relative = archive_path.relative_to(project_root).as_posix()
    except ValueError:
        archive_relative = archive_path.as_posix()
    metrics = _metrics(
        context,
        rows,
        created_at=timestamp,
        archive_relative=archive_relative,
        archive_sha256=archive_sha,
        raster_member=raster_member,
        raster_metadata=raster_metadata,
    )
    _atomic_write_csv(output_dir / "edge_slope_candidates.csv", rows)
    _atomic_write_json(output_dir / "metrics.json", metrics)
    return metrics


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Evaluate the NGII DEM without mutating the routing graph."
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
        report = run_dem_evaluation(
            args.project_root, args.output_dir, created_at=args.created_at
        )
    except Exception as exc:  # noqa: BLE001 - CLI reserves exit 2 for internal errors
        print(f"DEM evaluation failed: {exc}", file=sys.stderr)
        return 2
    metrics = report["metrics"]
    print(
        "DEM evaluation: "
        f"status={report['status']} edges={metrics['evaluated_edge_count']} "
        f"valid_length={metrics['valid_edge_length_pct']}% "
        f"hard_constraint_eligible={metrics['hard_constraint_eligible_edge_count']}"
    )
    return 1 if report["status"] == "fail" else 0


if __name__ == "__main__":
    raise SystemExit(main())
