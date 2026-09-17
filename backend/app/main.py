from __future__ import annotations

import json
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Query, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .database import Database
from .graph_store import EdgeNotFoundError, GraphStore
from .profiles import ProfileRegistry
from .routing import RouteEngine, RouteNotFoundError
from .schemas import EdgeStatusResponse, EdgeStatusUpdate, ObservationCandidate, ObservationCandidateCreate, ObservationReviewRequest, ObservationReviewResponse, RouteComparison, RouteRequest, RouteResult, RouteSessionResponse, SessionRerouteRequest, SessionRerouteResponse
from .services import ObservationCandidateNotFoundError, RouteService, RouteSessionNotFoundError


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROCESSED_GRAPH_PATH = PROJECT_ROOT / "data" / "processed" / "anyang_accessibility_graph.geojson"
SAMPLE_GRAPH_PATH = PROJECT_ROOT / "data" / "sample" / "navi_accessibility_graph.geojson"
DEFAULT_GRAPH_PATH = PROCESSED_GRAPH_PATH if PROCESSED_GRAPH_PATH.exists() else SAMPLE_GRAPH_PATH
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "runtime" / "navi.db"
DEFAULT_CANDIDATES_PATH = PROJECT_ROOT / "data" / "processed" / "review_candidates.json"
FRONTEND_DIR = PROJECT_ROOT / "frontend"


def create_app(graph_path: Path | None = None, db_path: Path | None = None) -> FastAPI:
    configured_graph = os.getenv("NAVI_GRAPH_PATH", "").strip()
    configured_db = os.getenv("NAVI_DB_PATH", "").strip()
    selected_graph = graph_path or (Path(configured_graph) if configured_graph else DEFAULT_GRAPH_PATH)
    selected_db = db_path or (Path(configured_db) if configured_db else DEFAULT_DB_PATH)

    store = GraphStore(selected_graph)
    database = Database(selected_db)
    for overlay in database.edge_overlays():
        try:
            store.apply_edge_overlay(overlay["edge_id"], overlay["values"])
        except EdgeNotFoundError:
            pass
    if DEFAULT_CANDIDATES_PATH.exists():
        database.seed_candidates(json.loads(DEFAULT_CANDIDATES_PATH.read_text(encoding="utf-8")))
    profiles = ProfileRegistry()
    engine = RouteEngine(store, profiles)
    service = RouteService(store, engine, database)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        yield
        database.close()

    app = FastAPI(title="NaVi Accessibility Routing PoC", version="0.2.0", description="OSM 보행망에서 일반 경로와 접근 가능 경로를 비교하고, 검수된 현장 상태 변화 후 세션별 경로를 재계산하는 PoC", lifespan=lifespan)
    app.state.graph_store, app.state.database, app.state.route_service = store, database, service

    @app.exception_handler(RouteNotFoundError)
    async def route_not_found_handler(_request: Request, exc: RouteNotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"status": exc.status, "message": exc.message})

    @app.exception_handler(EdgeNotFoundError)
    async def edge_not_found_handler(_request: Request, exc: EdgeNotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"status": "edge_not_found", "edge_id": exc.args[0] if exc.args else "unknown"})

    @app.exception_handler(RouteSessionNotFoundError)
    async def session_not_found_handler(_request: Request, exc: RouteSessionNotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"status": "route_session_not_found", "session_id": exc.args[0]})

    @app.exception_handler(ObservationCandidateNotFoundError)
    async def candidate_not_found_handler(_request: Request, exc: ObservationCandidateNotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"status": "candidate_not_found", "candidate_id": exc.args[0]})

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok", "service": "NaVi", "database": {"schema_version": database.SCHEMA_VERSION, "graph_revision": database.graph_revision}, "observations": {"pending": len(database.list_candidates("pending"))}, "graph": {"nodes": store.node_count, "edges": store.edge_count, "source": store.metadata.get("source"), "accessibility_attributes": store.metadata.get("accessibility_attributes")}}

    @app.get("/profiles")
    def list_profiles() -> list[dict]:
        return [profile.model_dump() for profile in profiles.all()]

    @app.get("/graph")
    def graph() -> dict:
        return store.to_geojson()

    @app.post("/route", response_model=RouteResult)
    def route(payload: RouteRequest) -> RouteResult:
        return service.route(payload)

    @app.post("/route/compare", response_model=RouteComparison)
    def compare_routes(payload: RouteRequest) -> RouteComparison:
        return service.compare(payload)

    @app.get("/route/sessions/{session_id}", response_model=RouteSessionResponse)
    def route_session(session_id: str) -> RouteSessionResponse:
        return service.get_session(session_id)

    @app.post("/route/sessions/{session_id}/reroute", response_model=SessionRerouteResponse)
    def reroute_session(session_id: str, payload: SessionRerouteRequest) -> SessionRerouteResponse:
        return service.reroute_session(session_id, payload)

    @app.get("/edges/{edge_id}")
    def get_edge(edge_id: str) -> dict:
        return store.get_edge(edge_id)

    @app.get("/edges/{edge_id}/history")
    def edge_history(edge_id: str) -> list[dict]:
        store.get_edge(edge_id)
        return database.edge_history(edge_id)

    @app.patch("/edges/{edge_id}/status", response_model=EdgeStatusResponse)
    def update_edge_status(edge_id: str, payload: EdgeStatusUpdate) -> EdgeStatusResponse:
        return service.update_edge_and_recalculate(edge_id, payload)

    @app.get("/observations/candidates", response_model=list[ObservationCandidate])
    def candidates(status: str | None = Query(default=None)) -> list[ObservationCandidate]:
        return service.list_candidates(status)

    @app.post("/observations/candidates", response_model=ObservationCandidate, status_code=201)
    def create_candidate(payload: ObservationCandidateCreate) -> ObservationCandidate:
        return service.create_candidate(payload)

    @app.get("/observations/candidates/{candidate_id}", response_model=ObservationCandidate)
    def candidate(candidate_id: str) -> ObservationCandidate:
        return service.get_candidate(candidate_id)

    @app.post("/observations/candidates/{candidate_id}/review", response_model=ObservationReviewResponse)
    def review_candidate(candidate_id: str, payload: ObservationReviewRequest) -> ObservationReviewResponse:
        return service.review_candidate(candidate_id, payload)

    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(FRONTEND_DIR / "index.html")

    @app.get("/review", include_in_schema=False)
    def review() -> FileResponse:
        return FileResponse(FRONTEND_DIR / "review.html")

    return app


app = create_app()
