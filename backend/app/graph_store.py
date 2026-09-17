from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any

import networkx as nx

from .schemas import EdgeStatusUpdate


class GraphDataError(RuntimeError):
    pass


class EdgeNotFoundError(KeyError):
    pass


class GraphStore:
    """Thread-safe in-memory routing graph backed by a versioned GeoJSON file."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = RLock()
        self.graph = nx.MultiGraph()
        self.metadata: dict[str, Any] = {}
        self._edge_index: dict[str, tuple[str, str, str]] = {}
        self._load()

    def _load(self) -> None:
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        if payload.get("type") != "FeatureCollection":
            raise GraphDataError("Graph GeoJSON must be a FeatureCollection")
        self.metadata = deepcopy(payload.get("metadata", {}))
        for feature in payload.get("features", []):
            props = deepcopy(feature.get("properties", {}))
            if props.pop("feature_type", None) != "node":
                continue
            node_id = props.pop("node_id", None)
            coordinates = feature.get("geometry", {}).get("coordinates", [])
            if not node_id or len(coordinates) != 2:
                raise GraphDataError("Every node needs node_id and Point coordinates")
            self.graph.add_node(node_id, node_id=node_id, lon=float(coordinates[0]), lat=float(coordinates[1]), **props)

        for feature in payload.get("features", []):
            props = deepcopy(feature.get("properties", {}))
            if props.pop("feature_type", None) != "edge":
                continue
            edge_id, from_node, to_node = props.get("edge_id"), props.get("from_node"), props.get("to_node")
            geometry = feature.get("geometry", {}).get("coordinates", [])
            if not edge_id or not from_node or not to_node:
                raise GraphDataError("Every edge needs edge_id, from_node, and to_node")
            if from_node not in self.graph or to_node not in self.graph:
                raise GraphDataError(f"Edge {edge_id} references an unknown node")
            if edge_id in self._edge_index:
                raise GraphDataError(f"Duplicate edge_id: {edge_id}")
            if len(geometry) < 2:
                raise GraphDataError(f"Edge {edge_id} needs LineString geometry")
            props["geometry"] = deepcopy(geometry)
            self.graph.add_edge(from_node, to_node, key=edge_id, **props)
            self._edge_index[edge_id] = (from_node, to_node, edge_id)
        if not self.graph.nodes or not self.graph.edges:
            raise GraphDataError("Graph must contain nodes and edges")

    @property
    def node_count(self) -> int:
        return self.graph.number_of_nodes()

    @property
    def edge_count(self) -> int:
        return self.graph.number_of_edges()

    def snapshot(self) -> nx.MultiGraph:
        with self._lock:
            return self.graph.copy(as_view=False)

    def get_edge(self, edge_id: str) -> dict[str, Any]:
        with self._lock:
            try:
                from_node, to_node, key = self._edge_index[edge_id]
            except KeyError as exc:
                raise EdgeNotFoundError(edge_id) from exc
            attrs = deepcopy(self.graph.edges[from_node, to_node, key])
            return {**attrs, "edge_id": edge_id, "from_node": from_node, "to_node": to_node}

    def get_node(self, node_id: str) -> dict[str, Any]:
        with self._lock:
            if node_id not in self.graph:
                raise KeyError(node_id)
            return deepcopy(self.graph.nodes[node_id])

    def apply_edge_overlay(self, edge_id: str, values: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            try:
                from_node, to_node, key = self._edge_index[edge_id]
            except KeyError as exc:
                raise EdgeNotFoundError(edge_id) from exc
            self.graph.edges[from_node, to_node, key].update(deepcopy(values))
            return self.get_edge(edge_id)

    def update_edge_status(self, edge_id: str, update: EdgeStatusUpdate) -> dict[str, Any]:
        return self.apply_edge_overlay(edge_id, {
            "blocked": update.blocked,
            "block_reason": update.reason,
            "accessibility_status": ("verified_block" if update.blocked else "verified_pass") if update.verified else "unknown",
            "status_source": update.status_source,
            "verified": update.verified,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })

    def to_geojson(self) -> dict[str, Any]:
        with self._lock:
            features: list[dict[str, Any]] = []
            for node_id, attrs in self.graph.nodes(data=True):
                props = deepcopy(attrs)
                lon, lat = props.pop("lon"), props.pop("lat")
                props.update(feature_type="node", node_id=node_id)
                features.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": [lon, lat]}, "properties": props})
            for from_node, to_node, _key, attrs in self.graph.edges(data=True, keys=True):
                props = deepcopy(attrs)
                geometry = props.pop("geometry")
                props.update(feature_type="edge", from_node=from_node, to_node=to_node)
                features.append({"type": "Feature", "geometry": {"type": "LineString", "coordinates": geometry}, "properties": props})
            return {"type": "FeatureCollection", "metadata": deepcopy(self.metadata), "features": features}
