from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile

import numpy as np
import rasterio
from pyproj import CRS

from scripts.validate_spatial_sources import (
    _summary,
    build_corridor_context,
    corridor_mask_geojson,
    inspect_shapefile_archive,
    sha256_file,
    validate_crosswalks,
    validate_orthophoto,
)


def _write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def _baseline_fixture(tmp_path: Path, *, declared_raw_sha: str | None = None):
    raw_graph = tmp_path / "source.graphml"
    raw_graph.write_bytes(b"immutable graph snapshot")
    actual_raw_sha = hashlib.sha256(raw_graph.read_bytes()).hexdigest()
    graph = {
        "type": "FeatureCollection",
        "metadata": {
            "crs": "EPSG:4326",
            "osm_snapshot_sha256": declared_raw_sha or actual_raw_sha,
            "verified": False,
        },
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [126.92, 37.39]},
                "properties": {"feature_type": "node", "node_id": "N1"},
            },
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [126.921, 37.391]},
                "properties": {"feature_type": "node", "node_id": "N2"},
            },
            {
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[126.92, 37.39], [126.921, 37.391]],
                },
                "properties": {"feature_type": "edge", "edge_id": "E1"},
            },
        ],
    }
    graph_path = tmp_path / "graph.geojson"
    metadata_path = tmp_path / "source.metadata.json"
    _write_json(graph_path, graph)
    _write_json(
        metadata_path,
        {
            "nodes": 2,
            "edges": 2,
            "sha256": declared_raw_sha or actual_raw_sha,
        },
    )
    return graph_path, raw_graph, metadata_path


def test_build_corridor_masks_and_roundtrip(tmp_path: Path) -> None:
    graph_path, raw_graph, metadata_path = _baseline_fixture(tmp_path)

    context, report = build_corridor_context(graph_path, raw_graph, metadata_path)

    assert context is not None
    assert report["status"] == "pass"
    assert context.node_count == 2
    assert context.edge_count == 1
    assert context.mask_30m_5179.area > 0
    assert context.mask_100m_5179.area > context.mask_30m_5179.area
    assert context.roundtrip_max_error_m <= 0.2


def test_raw_graph_hash_mismatch_is_failure(tmp_path: Path) -> None:
    graph_path, raw_graph, metadata_path = _baseline_fixture(
        tmp_path, declared_raw_sha="0" * 64
    )

    _context, report = build_corridor_context(graph_path, raw_graph, metadata_path)

    assert report["status"] == "fail"
    check = next(
        item for item in report["checks"] if item["code"] == "graph.raw_snapshot_sha256"
    )
    assert check["status"] == "fail"


def test_incomplete_shapefile_archive_is_failure(tmp_path: Path) -> None:
    archive_path = tmp_path / "incomplete.zip"
    with ZipFile(archive_path, "w") as archive:
        archive.writestr("roads.shp", b"placeholder")
        archive.writestr("roads.dbf", b"placeholder")
        archive.writestr("roads.prj", CRS.from_epsg(5186).to_wkt())

    _observed, checks = inspect_shapefile_archive(archive_path)

    component_check = next(
        item for item in checks if item["code"] == "topographic.shapefile_components"
    )
    assert component_check["status"] == "fail"
    assert component_check["evidence"]["missing"]["roads"] == [".shx"]


def _write_test_raster(path: Path, *, driver: str, count: int = 3) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = np.zeros((count, 3, 4), dtype=np.uint8)
    with rasterio.open(
        path,
        "w",
        driver=driver,
        width=4,
        height=3,
        count=count,
        dtype="uint8",
    ) as dataset:
        dataset.write(data)


def test_orthophoto_missing_georeferencing_is_warning(tmp_path: Path) -> None:
    original = tmp_path / "data/raw/ngii/orthophoto/2025"
    preview = tmp_path / "data/raw/ngii/orthophoto_preview/2025"
    tif = original / "T1" / "original.tif"
    xml = original / "T1" / "metadata.xml"
    jpg = preview / "T1" / "preview.jpg"
    html = preview / "T1" / "metadata.html"
    _write_test_raster(tif, driver="GTiff")
    _write_test_raster(jpg, driver="JPEG")
    xml.write_text("<metadata />", encoding="utf-8")
    html.write_text(
        '<input name="minx" value="949000">'
        '<input name="miny" value="1933000">'
        '<input name="maxx" value="950000">'
        '<input name="maxy" value="1934000">',
        encoding="utf-8",
    )
    _write_json(
        original / "source_manifest.json",
        {
            "dataset_id": "ortho-fixture",
            "embedded_georeferencing": False,
            "tiles": [
                {
                    "sheet_id": "T1",
                    "corridor_tile": True,
                    "raster": "T1/original.tif",
                    "raster_bytes": tif.stat().st_size,
                    "raster_sha256": sha256_file(tif),
                    "dimensions": [4, 3],
                    "metadata": "T1/metadata.xml",
                    "metadata_bytes": xml.stat().st_size,
                    "metadata_sha256": sha256_file(xml),
                }
            ],
        },
    )
    _write_json(
        preview / "source_manifest.json",
        {
            "dataset_id": "preview-fixture",
            "tiles": [{"sheet_id": "T1", "preview_dimensions": [4, 3]}],
        },
    )

    report = validate_orthophoto(tmp_path, None)

    assert report["status"] == "warning"
    georef = next(
        item
        for item in report["checks"]
        if item["code"] == "orthophoto.tile_T1.georeferencing"
    )
    assert georef["status"] == "warning"
    assert not any(item["status"] == "fail" for item in report["checks"])


def test_crosswalk_invalid_coordinates_fail_and_blanks_remain_unknown(
    tmp_path: Path,
) -> None:
    base = tmp_path / "data/raw/anyang/crosswalks/2026"
    base.mkdir(parents=True)
    path = base / "crosswalks.csv"
    fields = [
        "관리번호",
        "횡단보도폭",
        "횡단보도길이",
        "관할지역",
        "위도",
        "경도",
        "보도턱낮춤여부",
        "점자블록유무",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerow(
            {
                "관리번호": "CW1",
                "위도": "37.39",
                "경도": "126.92",
                "보도턱낮춤여부": "",
                "점자블록유무": "",
            }
        )
        writer.writerow(
            {
                "관리번호": "CW2",
                "위도": "not-a-number",
                "경도": "126.93",
                "보도턱낮춤여부": "Y",
                "점자블록유무": "N",
            }
        )

    report = validate_crosswalks(tmp_path, None)

    assert report["status"] == "fail"
    assert report["observed"]["rows_with_unknown_accessibility_count"] == 1
    assert "never converted to false" in report["observed"]["unknown_policy"]
    coordinate_check = next(
        item for item in report["checks"] if item["code"] == "crosswalk.coordinates"
    )
    assert coordinate_check["status"] == "fail"


def test_outputs_never_claim_verified_or_graph_update(tmp_path: Path) -> None:
    graph_path, raw_graph, metadata_path = _baseline_fixture(tmp_path)
    context, _report = build_corridor_context(graph_path, raw_graph, metadata_path)
    assert context is not None

    mask = corridor_mask_geojson(context, "2026-09-18T00:00:00+09:00")

    assert mask["metadata"]["derived"] is True
    assert mask["metadata"]["verified"] is False
    assert mask["metadata"]["graph_update_allowed"] is False
    assert all(feature["properties"]["verified"] is False for feature in mask["features"])
    assert all(
        feature["properties"]["graph_update_allowed"] is False
        for feature in mask["features"]
    )


def test_hold_does_not_fail_global_summary() -> None:
    graph = {"status": "pass", "checks": []}
    sources = [
        {"status": "warning", "checks": []},
        {"status": "hold", "checks": []},
    ]

    summary = _summary(graph, sources)

    assert summary["status"] == "warning"
    assert summary["fail"] == 0
    assert summary["hold"] == 1
