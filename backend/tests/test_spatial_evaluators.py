from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from affine import Affine
from pyproj import Transformer
from shapely.geometry import LineString, box

from scripts.evaluate_cross_sources import _decode_legacy_name
from scripts.evaluate_dem import bilinear_sample, sample_distances
from scripts.evaluate_orthophoto import parse_official_extent
from scripts.evaluate_topographic_map import classify_feature_match, parse_layer_member
from scripts.build_graph_enrichment_candidates import (
    _build_orthophoto_qa_manifest,
    _preview_graph,
    _routing_projection,
    _simulation_graph,
    derive_candidates,
)
from scripts.run_spatial_evaluation import _stable_sample
from scripts.spatial_evaluation_common import feature_collection


def test_topographic_layer_code_is_parsed_without_semantic_guessing() -> None:
    parsed = parse_layer_member("N1A_C0390000.shp")

    assert parsed == {
        "scale_prefix": "1",
        "geometry_kind": "area",
        "feature_code": "C0390000",
    }


def test_topographic_match_distinguishes_unique_and_unmatched() -> None:
    edges = (
        LineString([(0, 0), (20, 0)]),
        LineString([(0, 40), (20, 40)]),
    )
    edge_ids = ("E1", "E2")

    unique = classify_feature_match(box(2, -2, 18, 2), edges, edge_ids)
    unmatched = classify_feature_match(box(100, 100, 110, 110), edges, edge_ids)

    assert unique["status"] == "unique"
    assert unique["best"]["edge_id"] == "E1"
    assert unmatched["status"] == "unmatched"


def test_dem_sampling_spacing_and_bilinear_value() -> None:
    distances = sample_distances(100.0, max_interval_m=45.0)
    gaps = [end - start for start, end in zip(distances, distances[1:])]
    raster = np.ma.array([[1.0, 3.0], [5.0, 7.0]])
    transform = Affine.translation(0, 2) * Affine.scale(1, -1)

    assert distances[0] == 0.0
    assert distances[-1] == 100.0
    assert max(gaps) <= 45.0
    assert bilinear_sample(raster, transform, 1.0, 1.0) == 4.0


def test_official_extent_parser_reads_hidden_fields(tmp_path: Path) -> None:
    path = tmp_path / "metadata.html"
    path.write_text(
        '<input name="minx" value="1">'
        '<input name="miny" value="2">'
        '<input name="maxx" value="3">'
        '<input name="maxy" value="4">',
        encoding="utf-8",
    )

    assert parse_official_extent(path) == (1.0, 2.0, 3.0, 4.0)


def test_hdmap_legacy_name_decode_is_explicit() -> None:
    assert _decode_legacy_name("º¸µµ") == "보도"


def test_provenance_flags_cannot_be_overridden() -> None:
    collection = feature_collection(
        [],
        created_at="2026-09-18T00:00:00+09:00",
        source_graph_sha256="a" * 64,
        metadata={"verified": True, "graph_update_allowed": True},
    )

    assert collection["metadata"]["derived"] is True
    assert collection["metadata"]["verified"] is False
    assert collection["metadata"]["graph_update_allowed"] is False


def test_review_sampling_is_deterministic_and_bounded() -> None:
    features = [
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [index, index]},
            "properties": {"id": index},
        }
        for index in range(50)
    ]

    first = _stable_sample(features, 30)
    second = _stable_sample(reversed(features), 30)

    assert len(first) == 30
    assert first == second


def test_graph_enrichment_promotes_only_safe_pending_candidates() -> None:
    graph = {
        "type": "FeatureCollection",
        "metadata": {"crs": "EPSG:4326"},
        "features": [
            {
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[126.92, 37.39], [126.921, 37.391]],
                },
                "properties": {
                    "feature_type": "edge",
                    "edge_id": "E1",
                    "from_node": "N1",
                    "to_node": "N2",
                    "length": 100.0,
                    "stairs": False,
                    "slope": None,
                    "width": None,
                    "curb_height": None,
                    "surface": "unknown",
                    "elevator_required": False,
                    "elevator_status": None,
                    "blocked": False,
                    "block_reason": None,
                    "wheelchair_accessible": None,
                    "accessibility_status": "unknown",
                    "accessibility_source": "osm_tags",
                    "verified": False,
                },
            },
            {
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[126.922, 37.392], [126.923, 37.393]],
                },
                "properties": {
                    "feature_type": "edge",
                    "edge_id": "E2",
                    "from_node": "N3",
                    "to_node": "N4",
                    "length": 100.0,
                    "stairs": True,
                    "slope": None,
                    "width": None,
                    "curb_height": None,
                    "surface": "unknown",
                    "elevator_required": False,
                    "elevator_status": None,
                    "blocked": False,
                    "block_reason": None,
                    "wheelchair_accessible": None,
                    "accessibility_status": "unknown",
                    "accessibility_source": "osm_tags",
                    "verified": False,
                },
            },
        ],
    }
    topographic = {
        "features": [
            {
                "properties": {
                    "match_status": "unique",
                    "best_edge_id": "E1",
                    "evaluation_role": "stairs_candidate",
                    "source_feature_id": "S1",
                    "source_feature_code": "C0390000",
                    "best_distance_m": 0.5,
                    "best_score": 0.8,
                }
            },
            {
                "properties": {
                    "match_status": "unique",
                    "best_edge_id": "E2",
                    "evaluation_role": "stairs_candidate",
                    "source_feature_id": "S2",
                }
            },
            {
                "properties": {
                    "match_status": "ambiguous",
                    "best_edge_id": "E1",
                    "evaluation_role": "crossing_candidate",
                    "source_feature_id": "S3",
                }
            },
        ]
    }
    hdmap = {
        "features": [
            {
                "properties": {
                    "graph_mapping_status": "unique",
                    "graph_edge_id": "E1",
                    "evaluation_role": "crosswalk_polygon",
                    "source_feature_id": "HD1",
                }
            }
        ]
    }
    public_crosswalks = {
        "features": [
            {
                "properties": {
                    "graph_mapping_status": "unique",
                    "graph_edge_id": "E1",
                    "hd_match_status": "matched_near",
                    "public_crosswalk_id": "CW1",
                    "hd_crosswalk_id": "HD1",
                }
            }
        ]
    }

    candidates, skipped = derive_candidates(
        graph,
        topographic,
        hdmap,
        public_crosswalks,
        created_at="2026-09-18T00:00:00+09:00",
        dataset_ids={"topographic": "TOPO", "hdmap": "HD", "crosswalk": "CW"},
    )

    assert len(candidates) == 2
    stairs = next(item for item in candidates if item["type"] == "stairs_attribute_candidate")
    crossing = next(item for item in candidates if item["type"] == "crosswalk_geometry_evidence")
    assert stairs["edge_id"] == "E1"
    assert stairs["proposed_changes"] == {"stairs": True}
    assert stairs["status"] == "pending"
    assert stairs["verified"] is False
    assert stairs["graph_update_allowed"] is False
    assert crossing["proposed_changes"] == {}
    assert crossing["mapping_quality"] == "cross_source_consensus"
    assert skipped["stairs_already_present"] == 1
    assert skipped["topographic_not_unique"] == 1

    preview = _preview_graph(
        graph,
        candidates,
        created_at="2026-09-18T00:00:00+09:00",
        baseline_sha256="a" * 64,
    )
    assert _routing_projection(preview) == _routing_projection(graph)
    preview_edge = next(
        feature
        for feature in preview["features"]
        if feature["properties"].get("edge_id") == "E1"
    )
    assert len(preview_edge["properties"]["candidate_enrichments"]) == 2

    simulation = _simulation_graph(
        graph,
        [stairs],
        created_at="2026-09-18T00:00:00+09:00",
        baseline_sha256="a" * 64,
    )
    baseline_edge = next(
        feature
        for feature in graph["features"]
        if feature["properties"].get("edge_id") == "E1"
    )
    simulated_edge = next(
        feature
        for feature in simulation["features"]
        if feature["properties"].get("edge_id") == "E1"
    )
    assert baseline_edge["properties"]["stairs"] is False
    assert simulated_edge["properties"]["stairs"] is True
    assert simulation["metadata"]["candidate_simulation"]["runtime_use_allowed"] is False


def test_dem_candidates_are_diagnostic_only_and_threshold_gated() -> None:
    graph = {
        "features": [
            {
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[126.92, 37.39], [126.921, 37.391]],
                },
                "properties": {
                    "feature_type": "edge",
                    "edge_id": "E1",
                    "slope": None,
                },
            }
        ]
    }
    rows = [
        {
            "edge_id": "E1",
            "quality_flag": "coarse_context_only",
            "slope_pct_abs_candidate": "9.25",
            "slope_pct_signed_candidate": "-9.25",
            "dem_resolution_m": "90",
            "distinct_cell_count": "3",
            "nearest_bilinear_endpoint_max_diff_m": "4.2",
        }
    ]

    candidates, skipped = derive_candidates(
        graph,
        {"features": []},
        {"features": []},
        {"features": []},
        rows,
        created_at="2026-09-18T00:00:00+09:00",
        dataset_ids={"topographic": "TOPO", "hdmap": "HD", "crosswalk": "CW", "dem": "DEM"},
    )

    assert skipped == {}
    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate["type"] == "dem_slope_diagnostic_candidate"
    assert candidate["proposed_changes"] == {"slope": 9.25}
    assert candidate["candidate_class"] == "diagnostic_sensitivity"
    assert candidate["simulation_allowed"] is True
    assert candidate["approval_eligible"] is False
    assert candidate["graph_update_allowed"] is False
    assert candidate["evidence"][0]["hard_constraint_eligible"] is False


def test_orthophoto_manifest_attaches_visual_only_pixel_reference(tmp_path: Path) -> None:
    evaluation_root = tmp_path / "data/processed/evaluation"
    orthophoto_dir = evaluation_root / "orthophoto"
    sidecar_dir = orthophoto_dir / "georeferencing"
    sidecar_dir.mkdir(parents=True)
    x, y = Transformer.from_crs("EPSG:4326", "EPSG:5179", always_xy=True).transform(
        126.92,
        37.39,
    )
    bounds = [x - 100, y - 100, x + 100, y + 100]
    affine = Affine.translation(bounds[0], bounds[3]) * Affine.scale(0.25, -0.25)
    (orthophoto_dir / "metrics.json").write_text(
        json.dumps(
            {
                "dataset_id": "ORTHO",
                "metrics": {
                    "pixel_size_m_min": 0.25,
                    "pixel_size_m_max": 0.25,
                    "control_point_count": 0,
                    "control_point_rmse_m": None,
                    "graph_coverage": {"intersected_edge_pct": 100.0},
                },
            }
        ),
        encoding="utf-8",
    )
    (sidecar_dir / "T1.json").write_text(
        json.dumps(
            {
                "sheet_id": "T1",
                "bounds": bounds,
                "affine_gdal_order": list(affine.to_gdal()),
                "raster": "data/raw/test.tif",
                "raster_sha256": "a" * 64,
                "pixel_size_m": [0.25, 0.25],
                "control_point_count": 0,
                "control_point_rmse_m": None,
            }
        ),
        encoding="utf-8",
    )
    candidates = [
        {
            "candidate_id": "GEC-1",
            "lat": 37.39,
            "lon": 126.92,
            "visual_evidence_refs": [],
        }
    ]

    manifest = _build_orthophoto_qa_manifest(
        tmp_path,
        evaluation_root,
        candidates,
        created_at="2026-09-18T00:00:00+09:00",
        baseline_sha256="b" * 64,
    )

    assert manifest["status"] == "visual_qa_only"
    assert manifest["quality_gate"]["control_point_rmse_m"] is None
    assert manifest["metrics"]["referenced_candidate_count"] == 1
    reference = candidates[0]["visual_evidence_refs"][0]
    assert reference["sheet_id"] == "T1"
    assert reference["geometry_correction_allowed"] is False
    assert reference["graph_update_allowed"] is False
    assert reference["verified"] is False
