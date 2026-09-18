from __future__ import annotations

import json

import networkx as nx
import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from scripts.prepare_local_ar_route import (
    build_graph_payload,
    require_expected_osm_way,
    select_route_segment,
)


def _synthetic_walk_graph() -> nx.MultiDiGraph:
    graph = nx.MultiDiGraph()
    graph.add_node("A", x=127.1312, y=35.8422)
    graph.add_node("B", x=127.1319, y=35.8422)
    graph.add_node("C", x=127.1312, y=35.84235)
    graph.add_node("D", x=127.1319, y=35.84235)
    graph.add_edge("A", "B", key=0, highway="footway", osmid=12345)
    graph.add_edge(
        "C",
        "D",
        key=0,
        highway="footway",
        footway="crossing",
        osmid=99999,
    )
    return graph


def test_selects_non_crossing_25m_walking_segment() -> None:
    segment = select_route_segment(
        _synthetic_walk_graph(),
        center_lat=35.8422,
        center_lon=127.13145,
        target_length_m=25.0,
        max_center_distance_m=100.0,
    )

    assert segment["osm_way_ids"] == ["12345"]
    assert 24.9 <= segment["length_m"] <= 25.1
    assert segment["source_edge_length_m"] > segment["length_m"]
    assert segment["start_offset_m"] > 0
    assert segment["end_offset_m"] > 0
    assert segment["straightness_ratio"] == 1.0
    assert len(segment["coordinates"]) >= 2


def test_local_graph_keeps_accessibility_unknown_and_unverified() -> None:
    segment = select_route_segment(
        _synthetic_walk_graph(),
        center_lat=35.8422,
        center_lon=127.13145,
        target_length_m=25.0,
        max_center_distance_m=100.0,
    )
    payload, edge_id = build_graph_payload(
        label="공개 장소",
        segment=segment,
        fetched_at="2026-09-18T00:00:00+00:00",
    )

    edge = next(
        feature for feature in payload["features"]
        if feature["properties"].get("feature_type") == "edge"
    )
    assert payload["metadata"]["verified"] is False
    assert payload["metadata"]["accessibility_attributes"] == "unknown_unverified"
    assert payload["metadata"]["demo"]["block_edge"] == edge_id
    assert edge["properties"]["verified"] is False
    assert edge["properties"]["accessibility_status"] == "unknown"
    assert edge["properties"]["field_test_only"] is True
    assert edge["properties"]["shared_graph_mutation_allowed"] is False


def test_expected_osm_way_guard_rejects_silent_route_change() -> None:
    segment = select_route_segment(
        _synthetic_walk_graph(),
        center_lat=35.8422,
        center_lon=127.13145,
        target_length_m=25.0,
        max_center_distance_m=100.0,
    )

    require_expected_osm_way(segment, "12345")
    with pytest.raises(RuntimeError, match="expected 99999"):
        require_expected_osm_way(segment, "99999")


def test_field_graph_does_not_seed_unrelated_default_candidates(tmp_path) -> None:
    segment = select_route_segment(
        _synthetic_walk_graph(),
        center_lat=35.8422,
        center_lon=127.13145,
        target_length_m=25.0,
        max_center_distance_m=100.0,
    )
    payload, _edge_id = build_graph_payload(
        label="공개 장소",
        segment=segment,
        fetched_at="2026-09-18T00:00:00+00:00",
    )
    graph_path = tmp_path / "route.geojson"
    graph_path.write_text(json.dumps(payload), encoding="utf-8")

    with TestClient(create_app(graph_path, tmp_path / "local.db")) as client:
        health = client.get("/health")
        candidates = client.get("/observations/candidates?status=pending")

    assert health.status_code == 200
    assert health.json()["observations"]["pending"] == 0
    assert candidates.status_code == 200
    assert candidates.json() == []
