from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.graph_store import GraphStore
from app.database import Database
from app.main import PROJECT_ROOT, create_app
from app.profiles import ProfileRegistry
from app.routing import RouteEngine
from app.services import RouteService


GRAPH_PATH = PROJECT_ROOT / "data" / "sample" / "navi_accessibility_graph.geojson"


@pytest.fixture
def store() -> GraphStore:
    return GraphStore(GRAPH_PATH)


@pytest.fixture
def engine(store: GraphStore) -> RouteEngine:
    return RouteEngine(store, ProfileRegistry())


@pytest.fixture
def database(tmp_path) -> Database:
    db = Database(tmp_path / "test.db")
    yield db
    db.close()


@pytest.fixture
def service(store: GraphStore, engine: RouteEngine, database: Database) -> RouteService:
    return RouteService(store, engine, database)


@pytest.fixture
def client(tmp_path) -> TestClient:
    app = create_app(Path(GRAPH_PATH), tmp_path / "api.db")
    with TestClient(app) as test_client:
        yield test_client
