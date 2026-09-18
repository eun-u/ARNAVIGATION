from __future__ import annotations

import json

import networkx as nx
import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from scripts.prepare_local_reroute_route import (
    build_reroute_graph_payload,
    require_expected_path,
    require_expected_way_ids,
    select_reroute_paths,
)


def _synthetic_branch_graph() -> nx.MultiDiGraph:
    graph = nx.MultiDiGraph()
    coordinates = {
        "O": (127.0000, 35.0000),
        "J": (127.0002, 35.0000),
        "P": (127.0003, 34.9999),
        "M": (127.0004, 34.9998),
        "D": (127.0005, 34.9998),
        "Q": (127.0002, 34.9998),
        "R": (127.0003, 34.9997),
    }
    for node_id, (lon, lat) in coordinates.items():
        graph.add_node(node_id, x=lon, y=lat)

    def add_edge(from_node: str, to_node: str, length: float, osmid: int) -> None:
        graph.add_edge(
            from_node,
            to_node,
            key=0,
            highway="footway",
            length=length,
            osmid=osmid,
        )

    add_edge("O", "J", 20.0, 1)
    add_edge("J", "P", 10.0, 2)
    add_edge("P", "M", 20.0, 3)
    add_edge("M", "D", 10.0, 4)
    add_edge("J", "Q", 20.0, 5)
    add_edge("Q", "R", 20.0, 6)
    add_edge("R", "M", 20.0, 7)
    return graph


def _route() -> tuple[nx.MultiDiGraph, dict]:
    graph = _synthetic_branch_graph()
    route = select_reroute_paths(
        graph,
        origin_node_id="O",
        destination_node_id="D",
        block_from_node_id="J",
        block_to_node_id="P",
    )
    return graph, route


def test_selects_primary_and_longer_alternate_after_block() -> None:
    _graph, route = _route()

    assert route["primary_path"] == ["O", "J", "P", "M", "D"]
    assert route["alternate_path"] == ["O", "J", "Q", "R", "M", "D"]
    assert route["primary_length_m"] == 60.0
    assert route["alternate_length_m"] == 90.0
    assert route["detour_delta_m"] == 30.0
    assert route["shared_length_m"] == 30.0
    assert route["branch_node"] == "J"
    assert route["merge_node"] == "M"


def test_route_and_way_guards_reject_silent_osm_drift() -> None:
    _graph, route = _route()

    require_expected_path(
        route["primary_path"],
        ["O", "J", "P", "M", "D"],
        "Primary",
    )
    require_expected_way_ids(route, ["1", "2", "3", "4", "5", "6", "7"])

    with pytest.raises(RuntimeError, match="Primary path changed"):
        require_expected_path(route["primary_path"], ["O", "J", "Q", "D"], "Primary")
    with pytest.raises(RuntimeError, match="missing expected OSM ways"):
        require_expected_way_ids(route, ["999"])


def test_generated_graph_is_unverified_and_reroutes_session_locally(tmp_path) -> None:
    graph, route = _route()
    payload, contract = build_reroute_graph_payload(
        graph,
        label="분기 우회 시험",
        route=route,
        fetched_at="2026-09-18T00:00:00+00:00",
    )
    graph_path = tmp_path / "route.geojson"
    graph_path.write_text(json.dumps(payload), encoding="utf-8")

    edges = [
        feature
        for feature in payload["features"]
        if feature["properties"].get("feature_type") == "edge"
    ]
    assert payload["metadata"]["verified"] is False
    assert payload["metadata"]["accessibility_attributes"] == "unknown_unverified"
    assert payload["metadata"]["demo"]["block_edge"] == contract["block_edge_id"]
    assert all(edge["properties"]["verified"] is False for edge in edges)
    assert all(edge["properties"]["wheelchair_accessible"] is None for edge in edges)
    assert all(edge["properties"]["shared_graph_mutation_allowed"] is False for edge in edges)

    request = {
        "origin": {"lat": 35.0000, "lon": 127.0000},
        "destination": {"lat": 34.9998, "lon": 127.0005},
        "profile": "wheelchair",
    }
    with TestClient(create_app(graph_path, tmp_path / "local.db")) as client:
        comparison = client.post("/route/compare", json=request)
        assert comparison.status_code == 200
        comparison_body = comparison.json()
        assert comparison_body["accessible"]["distance_m"] == 60.0
        assert comparison_body["accessible"]["edge_ids"] == contract["primary_edge_ids"]

        reroute = client.post(
            f"/route/sessions/{comparison_body['session_id']}/reroute",
            json={
                "temporary_blocked_edge_ids": [contract["block_edge_id"]],
                "reason": "controlled_test_obstacle",
            },
        )
        assert reroute.status_code == 200
        reroute_body = reroute.json()
        assert reroute_body["route_affected"] is True
        assert reroute_body["route_changed"] is True
        assert reroute_body["recalculated_route"]["distance_m"] == 90.0
        assert reroute_body["recalculated_route"]["edge_ids"] == contract["alternate_edge_ids"]
        assert client.get(f"/edges/{contract['block_edge_id']}").json()["blocked"] is False
