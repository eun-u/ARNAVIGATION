DEMO_PAYLOAD = {
    "origin": {"lat": 37.4019, "lon": 126.9205},
    "destination": {"lat": 37.4001, "lon": 126.9240},
    "profile": "wheelchair",
}


def test_health(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["graph"] == {
        "nodes": 9,
        "edges": 10,
        "source": "derived_from_existing_anyang_corridor_context",
        "accessibility_attributes": "synthetic",
    }


def test_compare_route_api(client):
    response = client.post("/route/compare", json=DEMO_PAYLOAD)

    assert response.status_code == 200
    body = response.json()
    assert body["standard"]["distance_m"] == 379.8
    assert body["accessible"]["distance_m"] == 405.7
    assert body["difference_m"] == 25.9
    assert "stairs" in body["reasons"]
    assert "high_curb" in body["reasons"]


def test_patch_edge_recalculates_cached_route(client):
    session_id = client.post("/route/compare", json=DEMO_PAYLOAD).json()["session_id"]

    response = client.patch(
        "/edges/E006/status",
        json={"blocked": True, "reason": "construction", "session_id": session_id},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["route_affected"] is True
    assert body["route_changed"] is True
    assert body["previous_route"]["distance_m"] == 405.7
    assert body["recalculated_route"]["distance_m"] == 535.3


def test_no_accessible_route_api_shape(client):
    client.patch(
        "/edges/E006/status",
        json={"blocked": True, "reason": "construction"},
    )
    client.patch(
        "/edges/E008/status",
        json={"blocked": True, "reason": "temporary_closure"},
    )

    response = client.post("/route", json=DEMO_PAYLOAD)

    assert response.status_code == 404
    assert response.json()["status"] == "no_accessible_route"


def test_edge_status_requires_reason_when_blocked(client):
    response = client.patch("/edges/E006/status", json={"blocked": True})

    assert response.status_code == 422


def test_session_reroute_does_not_mutate_shared_graph(client):
    first = client.post("/route/compare", json=DEMO_PAYLOAD).json()
    second = client.post("/route/compare", json=DEMO_PAYLOAD).json()

    response = client.post(
        f"/route/sessions/{first['session_id']}/reroute",
        json={
            "temporary_blocked_edge_ids": ["E006"],
            "reason": "user_observed_obstacle",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "recalculated"
    assert body["route_affected"] is True
    assert body["route_changed"] is True
    assert body["previous_route"]["distance_m"] == 405.7
    assert body["recalculated_route"]["distance_m"] == 535.3
    assert body["temporary_blocked_edge_ids"] == ["E006"]
    assert client.get("/edges/E006").json()["blocked"] is False
    assert client.get(f"/route/sessions/{second['session_id']}").json()["route"]["distance_m"] == 405.7


def test_mobile_observation_stays_pending_and_unverified(client):
    session_id = client.post("/route/compare", json=DEMO_PAYLOAD).json()["session_id"]

    response = client.post(
        "/observations/candidates",
        json={
            "edge_id": "E006",
            "type": "blocked_path",
            "source": "manual_camera",
            "session_id": session_id,
            "note": "카메라 안내 중 공사 가림막을 확인",
            "lat": 37.401,
            "lon": 126.922,
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "pending"
    assert body["verified"] is False
    assert body["confidence"] is None
    assert client.get("/edges/E006").json()["blocked"] is False


def test_mobile_observation_requires_review_before_graph_update(client):
    candidate = client.post(
        "/observations/candidates",
        json={
            "edge_id": "E006",
            "type": "blocked_path",
            "source": "manual_camera",
            "note": "통행 불가 제보",
        },
    ).json()

    reviewed = client.post(
        f"/observations/candidates/{candidate['candidate_id']}/review",
        json={
            "decision": "approved",
            "result": "verified_block",
            "reviewer": "field-reviewer",
            "observed_at": "2026-09-17T10:00:00+09:00",
            "reason": "현장 사진과 위치를 검수해 공사 차단 확인",
            "measurements": {},
        },
    )

    assert reviewed.status_code == 200
    assert reviewed.json()["candidate"]["verified"] is True
    assert reviewed.json()["graph_updated"] is True
    assert client.get("/edges/E006").json()["blocked"] is True
