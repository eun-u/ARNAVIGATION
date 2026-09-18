from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from copy import deepcopy
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from .database import Database
from .graph_store import EdgeNotFoundError, GraphStore
from .routing import RouteEngine, RouteNotFoundError
from .schemas import (
    GraphEnrichmentCandidate,
    GraphEnrichmentCandidateList,
    GraphEnrichmentSimulationRequest,
    GraphEnrichmentSimulationResponse,
    GraphEnrichmentSummary,
    RouteRequest,
    RouteResult,
)


class GraphEnrichmentBundleError(RuntimeError):
    pass


class GraphEnrichmentUnavailableError(RuntimeError):
    pass


class GraphEnrichmentCandidateNotFoundError(KeyError):
    pass


class GraphEnrichmentSimulationError(ValueError):
    pass


class GraphEnrichmentCatalog:
    """Read-only catalog for spatial evaluation candidates.

    The catalog accepts only pre-review, non-applicable candidates tied to the
    exact baseline Graph file. It never writes candidates to SQLite or applies
    their proposed changes to ``GraphStore``.
    """

    SIMULATION_FIELDS = {"stairs", "slope"}

    def __init__(
        self,
        bundle_path: Path | None,
        graph_path: Path,
        store: GraphStore,
    ) -> None:
        self.bundle_path = bundle_path
        self.graph_path = graph_path
        self._candidates: dict[str, GraphEnrichmentCandidate] = {}
        self.schema_version: str | None = None
        self.created_at: str | None = None
        self.baseline_graph_sha256: str | None = None
        self.available = bundle_path is not None and bundle_path.exists()
        if self.available:
            self._load(store)

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def _load(self, store: GraphStore) -> None:
        assert self.bundle_path is not None
        try:
            payload = json.loads(self.bundle_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise GraphEnrichmentBundleError(
                f"Cannot read graph-enrichment bundle: {self.bundle_path}"
            ) from exc

        if not isinstance(payload, dict) or not isinstance(payload.get("candidates"), list):
            raise GraphEnrichmentBundleError("Candidate bundle must contain a candidates list")

        self.schema_version = str(payload.get("schema_version") or "") or None
        self.created_at = str(payload.get("created_at") or "") or None
        self.baseline_graph_sha256 = str(payload.get("baseline_graph_sha256") or "").lower() or None
        graph_sha256 = self._sha256(self.graph_path)
        if self.baseline_graph_sha256 != graph_sha256:
            raise GraphEnrichmentBundleError(
                "Candidate bundle baseline SHA-256 does not match the selected Graph"
            )

        candidates: dict[str, GraphEnrichmentCandidate] = {}
        for raw_candidate in payload["candidates"]:
            try:
                candidate = GraphEnrichmentCandidate.model_validate(raw_candidate)
            except ValidationError as exc:
                raise GraphEnrichmentBundleError("Candidate bundle schema validation failed") from exc
            if candidate.candidate_id in candidates:
                raise GraphEnrichmentBundleError(
                    f"Duplicate candidate_id: {candidate.candidate_id}"
                )
            if (
                candidate.status != "pending"
                or candidate.verified
                or candidate.graph_update_allowed
                or not candidate.requires_human_review
            ):
                raise GraphEnrichmentBundleError(
                    f"Candidate {candidate.candidate_id} crosses the pre-review safety boundary"
                )
            unsupported = set(candidate.proposed_changes) - self.SIMULATION_FIELDS
            if unsupported:
                fields = ", ".join(sorted(unsupported))
                raise GraphEnrichmentBundleError(
                    f"Candidate {candidate.candidate_id} has unsupported simulation fields: {fields}"
                )
            if "stairs" in candidate.proposed_changes and not isinstance(
                candidate.proposed_changes["stairs"], bool
            ):
                raise GraphEnrichmentBundleError(
                    f"Candidate {candidate.candidate_id} has a non-boolean stairs value"
                )
            if "slope" in candidate.proposed_changes:
                slope = candidate.proposed_changes["slope"]
                if (
                    isinstance(slope, bool)
                    or not isinstance(slope, (int, float))
                    or not math.isfinite(float(slope))
                    or not 0 <= float(slope) <= 100
                ):
                    raise GraphEnrichmentBundleError(
                        f"Candidate {candidate.candidate_id} has an invalid slope value"
                    )
            if candidate.simulation_allowed != bool(candidate.proposed_changes):
                raise GraphEnrichmentBundleError(
                    f"Candidate {candidate.candidate_id} has inconsistent simulation eligibility"
                )
            if (
                candidate.candidate_class == "diagnostic_sensitivity"
                and candidate.approval_eligible
            ):
                raise GraphEnrichmentBundleError(
                    f"Diagnostic candidate {candidate.candidate_id} cannot be approval eligible"
                )
            for reference in candidate.visual_evidence_refs:
                if (
                    reference.get("verified") is not False
                    or reference.get("graph_update_allowed") is not False
                    or reference.get("geometry_correction_allowed") is not False
                ):
                    raise GraphEnrichmentBundleError(
                        f"Candidate {candidate.candidate_id} has an unsafe visual evidence reference"
                    )
            try:
                store.get_edge(candidate.edge_id)
            except EdgeNotFoundError as exc:
                raise GraphEnrichmentBundleError(
                    f"Candidate {candidate.candidate_id} references unknown edge {candidate.edge_id}"
                ) from exc
            candidates[candidate.candidate_id] = candidate
        self._candidates = candidates

    def summary(self) -> GraphEnrichmentSummary:
        candidates = list(self._candidates.values())
        type_counts = Counter(candidate.type for candidate in candidates)
        priority_counts = Counter(candidate.priority for candidate in candidates)
        route_affecting = sum(bool(candidate.proposed_changes) for candidate in candidates)
        diagnostics = sum(
            candidate.candidate_class == "diagnostic_sensitivity"
            for candidate in candidates
        )
        return GraphEnrichmentSummary(
            available=self.available,
            schema_version=self.schema_version,
            created_at=self.created_at,
            baseline_graph_sha256=self.baseline_graph_sha256,
            baseline_matches_graph=self.available,
            candidate_count=len(candidates),
            candidate_edge_count=len({candidate.edge_id for candidate in candidates}),
            route_affecting_candidate_count=route_affecting,
            evidence_only_candidate_count=len(candidates) - route_affecting,
            diagnostic_candidate_count=diagnostics,
            approval_eligible_candidate_count=sum(
                candidate.approval_eligible for candidate in candidates
            ),
            orthophoto_referenced_candidate_count=sum(
                bool(candidate.visual_evidence_refs) for candidate in candidates
            ),
            candidate_counts_by_type=dict(sorted(type_counts.items())),
            candidate_counts_by_priority=dict(sorted(priority_counts.items())),
            all_pending=all(candidate.status == "pending" for candidate in candidates),
            all_unverified=all(not candidate.verified for candidate in candidates),
            graph_update_allowed=False,
        )

    def list_candidates(
        self,
        *,
        candidate_type: str | None = None,
        priority: str | None = None,
        candidate_class: str | None = None,
        route_affecting: bool | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> GraphEnrichmentCandidateList:
        candidates = list(self._candidates.values())
        if candidate_type is not None:
            candidates = [candidate for candidate in candidates if candidate.type == candidate_type]
        if priority is not None:
            candidates = [candidate for candidate in candidates if candidate.priority == priority]
        if candidate_class is not None:
            candidates = [
                candidate
                for candidate in candidates
                if candidate.candidate_class == candidate_class
            ]
        if route_affecting is not None:
            candidates = [
                candidate
                for candidate in candidates
                if bool(candidate.proposed_changes) is route_affecting
            ]
        candidates.sort(key=lambda item: (item.priority, item.type, item.edge_id, item.candidate_id))
        return GraphEnrichmentCandidateList(
            available=self.available,
            total=len(candidates),
            offset=offset,
            limit=limit,
            candidates=[candidate.model_copy(deep=True) for candidate in candidates[offset : offset + limit]],
        )

    def get_candidate(self, candidate_id: str) -> GraphEnrichmentCandidate:
        if not self.available:
            raise GraphEnrichmentUnavailableError("Graph-enrichment candidate bundle is unavailable")
        try:
            return self._candidates[candidate_id].model_copy(deep=True)
        except KeyError as exc:
            raise GraphEnrichmentCandidateNotFoundError(candidate_id) from exc

    def simulation_overlays(
        self, candidate_ids: list[str]
    ) -> tuple[list[GraphEnrichmentCandidate], dict[str, dict[str, Any]]]:
        if not self.available:
            raise GraphEnrichmentUnavailableError("Graph-enrichment candidate bundle is unavailable")

        selected: list[GraphEnrichmentCandidate] = []
        overlays: dict[str, dict[str, Any]] = {}
        for candidate_id in candidate_ids:
            candidate = self.get_candidate(candidate_id)
            if not candidate.simulation_allowed or not candidate.proposed_changes:
                raise GraphEnrichmentSimulationError(
                    f"Candidate {candidate_id} is evidence-only and has no routable proposal"
                )
            edge_overlay = overlays.setdefault(candidate.edge_id, {})
            for field, value in candidate.proposed_changes.items():
                if field in edge_overlay and edge_overlay[field] != value:
                    raise GraphEnrichmentSimulationError(
                        f"Candidates propose conflicting {field} values for edge {candidate.edge_id}"
                    )
                edge_overlay[field] = deepcopy(value)
            selected.append(candidate)
        return selected, overlays


class GraphEnrichmentService:
    def __init__(
        self,
        catalog: GraphEnrichmentCatalog,
        engine: RouteEngine,
        database: Database,
    ) -> None:
        self.catalog = catalog
        self.engine = engine
        self.database = database

    @staticmethod
    def _route_or_none(
        engine: RouteEngine,
        request: RouteRequest,
        overlays: dict[str, dict[str, Any]] | None = None,
    ) -> RouteResult | None:
        try:
            return engine.find_accessible_route(
                request,
                edge_attribute_overlays=overlays,
            )
        except RouteNotFoundError as exc:
            if exc.status != "no_accessible_route":
                raise
            return None

    def simulate(
        self, payload: GraphEnrichmentSimulationRequest
    ) -> GraphEnrichmentSimulationResponse:
        selected, overlays = self.catalog.simulation_overlays(payload.candidate_ids)
        route_request = RouteRequest(
            origin=payload.origin,
            destination=payload.destination,
            profile=payload.profile,
        )
        baseline = self._route_or_none(self.engine, route_request)
        simulated = self._route_or_none(self.engine, route_request, overlays)
        baseline_edges = set(baseline.edge_ids if baseline else [])
        applied_edge_ids = list(overlays)
        baseline_candidate_edges = [
            edge_id for edge_id in applied_edge_ids if edge_id in baseline_edges
        ]
        route_changed = (
            (baseline is None) != (simulated is None)
            or (
                baseline is not None
                and simulated is not None
                and (
                    baseline.edge_ids != simulated.edge_ids
                    or baseline.distance_m != simulated.distance_m
                )
            )
        )
        difference_m = (
            round(simulated.distance_m - baseline.distance_m, 1)
            if baseline is not None and simulated is not None
            else None
        )
        return GraphEnrichmentSimulationResponse(
            status="ok" if simulated is not None else "no_accessible_route",
            candidate_ids=[candidate.candidate_id for candidate in selected],
            applied_edge_ids=applied_edge_ids,
            baseline_candidate_edge_ids=baseline_candidate_edges,
            baseline=baseline,
            simulated=simulated,
            route_changed=route_changed,
            difference_m=difference_m,
            graph_revision=self.database.graph_revision,
            graph_mutated=False,
            database_mutated=False,
            warnings=[
                "검토 전 공간데이터 후보를 현재 요청에서만 임시 적용한 시뮬레이션입니다.",
                "공유 Graph와 SQLite는 변경하지 않았으며 후보를 검증된 접근성 사실로 취급하지 않습니다.",
                *(
                    [
                        "DEM 경사값은 90m 격자의 지형 맥락으로 산출한 진단값이며 현장 보도 경사나 승인 가능한 Graph 속성이 아닙니다."
                    ]
                    if any(
                        candidate.candidate_class == "diagnostic_sensitivity"
                        for candidate in selected
                    )
                    else []
                ),
            ],
        )
