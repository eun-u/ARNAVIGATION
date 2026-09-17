import pytest

from app.constraints import edge_constraint_reasons
from app.routing import RouteNotFoundError
from app.schemas import (
    AccessibilityProfile,
    Coordinate,
    EdgeStatusUpdate,
    RouteRequest,
)


DEMO_REQUEST = RouteRequest(
    origin=Coordinate(lat=37.4019, lon=126.9205),
    destination=Coordinate(lat=37.4001, lon=126.9240),
    profile="wheelchair",
)


def test_standard_route_calculation_succeeds(engine):
    route = engine.find_shortest_route(DEMO_REQUEST)

    assert route.edge_ids == ["E001", "E002", "E003", "E004"]
    assert route.distance_m == 379.8
    assert route.route_type == "standard"


def test_stairs_edge_is_excluded_for_wheelchair(engine):
    route = engine.find_accessible_route(DEMO_REQUEST)

    assert route.edge_ids == ["E001", "E005", "E006", "E007"]
    assert "E002" not in route.edge_ids
    stairs = next(edge for edge in route.excluded_edges if edge.edge_id == "E002")
    assert "stairs" in stairs.reasons


def test_blocked_edge_is_excluded(store, engine):
    store.update_edge_status(
        "E006", EdgeStatusUpdate(blocked=True, reason="construction")
    )

    route = engine.find_accessible_route(DEMO_REQUEST)

    assert route.edge_ids == ["E001", "E008", "E009", "E010"]
    assert "E006" not in route.edge_ids
    blocked = next(edge for edge in route.excluded_edges if edge.edge_id == "E006")
    assert "blocked" in blocked.reasons
    assert "construction" in blocked.reasons


def test_used_edge_status_change_recalculates_route(service):
    comparison = service.compare(DEMO_REQUEST)
    before = comparison.accessible

    result = service.update_edge_and_recalculate(
        "E006", EdgeStatusUpdate(blocked=True, reason="construction", session_id=comparison.session_id)
    )

    assert result.route_affected is True
    assert result.route_recalculated is True
    assert result.route_changed is True
    assert result.previous_route.edge_ids == before.edge_ids
    assert result.recalculated_route.edge_ids == ["E001", "E008", "E009", "E010"]
    assert result.recalculated_route.distance_m > before.distance_m


def test_no_accessible_route_returns_explicit_error(store, engine):
    store.update_edge_status(
        "E006", EdgeStatusUpdate(blocked=True, reason="construction")
    )
    store.update_edge_status(
        "E008", EdgeStatusUpdate(blocked=True, reason="temporary_closure")
    )

    with pytest.raises(RouteNotFoundError) as exc_info:
        engine.find_accessible_route(DEMO_REQUEST)

    assert exc_info.value.status == "no_accessible_route"


def test_synthetic_unknown_edge_requires_explicit_profile_opt_in(store):
    edge = store.get_edge("E001")
    strict_profile = AccessibilityProfile(
        name="wheelchair",
        description="strict test profile",
        allow_stairs=False,
        allow_unknown=False,
        allow_synthetic=False,
    )
    poc_profile = strict_profile.model_copy(update={"allow_synthetic": True})

    assert "unknown_accessibility" in edge_constraint_reasons(edge, strict_profile)
    assert "unknown_accessibility" not in edge_constraint_reasons(edge, poc_profile)


def test_unverified_status_update_does_not_claim_verified_state(store):
    edge = store.update_edge_status(
        "E006", EdgeStatusUpdate(blocked=False, verified=False)
    )

    assert edge["accessibility_status"] == "unknown"
    assert edge["verified"] is False


def test_session_block_excludes_edge_without_mutating_store(store, engine):
    route = engine.find_accessible_route(DEMO_REQUEST, {"E006"})

    assert route.edge_ids == ["E001", "E008", "E009", "E010"]
    temporary = next(edge for edge in route.excluded_edges if edge.edge_id == "E006")
    assert "session_blocked" in temporary.reasons
    assert store.get_edge("E006")["blocked"] is False
