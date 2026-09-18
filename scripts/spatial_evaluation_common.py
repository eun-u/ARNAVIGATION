"""Shared helpers for provenance-safe NaVi spatial evaluations."""

from __future__ import annotations

import csv
import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

from pyproj import Transformer
from shapely import force_2d
from shapely.geometry import mapping, shape
from shapely.ops import transform
from shapely.strtree import STRtree


GRAPH_PATH = Path("data/processed/anyang_accessibility_graph.geojson")
RAW_GRAPH_PATH = Path("data/raw/anyang_corridor_walk_20260915.graphml")
RAW_GRAPH_METADATA_PATH = Path("data/raw/anyang_corridor_walk_20260915.metadata.json")
OUTPUT_ROOT = Path("data/processed/evaluation")
PROVENANCE_FLAGS = {
    "derived": True,
    "verified": False,
    "graph_update_allowed": False,
}


@dataclass(frozen=True)
class EdgeRecord:
    edge_id: str
    geometry_wgs84: Any
    geometry_5179: Any
    properties: dict[str, Any]


class EdgeMatcher:
    def __init__(self, edges: Sequence[EdgeRecord]) -> None:
        self.edges = tuple(edges)
        self.geometries = tuple(edge.geometry_5179 for edge in self.edges)
        self.tree = STRtree(self.geometries)

    def match(
        self,
        geometry_5179: Any,
        *,
        max_distance_m: float = 15.0,
        unique_margin_m: float = 2.0,
        overlap_buffer_m: float = 5.0,
    ) -> dict[str, Any]:
        geometry_5179 = force_2d(geometry_5179)
        indices = list(self.tree.query(geometry_5179.buffer(max_distance_m)))
        ranked: list[tuple[float, str, int]] = []
        for raw_index in indices:
            index = int(raw_index)
            edge = self.edges[index]
            distance = float(geometry_5179.distance(edge.geometry_5179))
            if distance <= max_distance_m:
                ranked.append((distance, edge.edge_id, index))
        ranked.sort(key=lambda item: (round(item[0], 9), item[1]))
        if not ranked:
            return {
                "mapping_status": "unmatched",
                "edge_id": None,
                "candidate_edge_ids": [],
                "distance_m": None,
                "second_distance_m": None,
                "direction_difference_deg": None,
                "overlap_ratio": 0.0,
                "method": "edge_spatial_index_nearest_15m",
            }

        best_distance, _best_id, best_index = ranked[0]
        second_distance = ranked[1][0] if len(ranked) > 1 else None
        is_unique = second_distance is None or (
            second_distance - best_distance >= unique_margin_m
        )
        best_edge = self.edges[best_index]
        if geometry_5179.geom_type in {"LineString", "MultiLineString"}:
            denominator = geometry_5179.length
            overlap_measure = geometry_5179.intersection(
                best_edge.geometry_5179.buffer(overlap_buffer_m)
            ).length
            direction_difference = _direction_difference(
                geometry_5179, best_edge.geometry_5179
            )
        elif geometry_5179.geom_type in {"Polygon", "MultiPolygon"}:
            denominator = geometry_5179.area
            overlap_measure = geometry_5179.intersection(
                best_edge.geometry_5179.buffer(overlap_buffer_m)
            ).area
            direction_difference = None
        else:
            denominator = 1.0
            overlap_measure = 1.0 if best_distance <= overlap_buffer_m else 0.0
            direction_difference = None
        overlap_ratio = min(1.0, overlap_measure / denominator) if denominator else 0.0
        return {
            "mapping_status": "unique" if is_unique else "ambiguous",
            "edge_id": best_edge.edge_id if is_unique else None,
            "candidate_edge_ids": [item[1] for item in ranked[:5]],
            "distance_m": round(best_distance, 3),
            "second_distance_m": (
                round(second_distance, 3) if second_distance is not None else None
            ),
            "direction_difference_deg": (
                round(direction_difference, 3)
                if direction_difference is not None
                else None
            ),
            "overlap_ratio": round(overlap_ratio, 6),
            "method": "edge_spatial_index_nearest_15m_margin_2m_overlap_5m",
        }


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return value


def file_sha256(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def relative_path(path: Path, project_root: Path) -> str:
    return path.resolve().relative_to(project_root.resolve()).as_posix()


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def write_csv(path: Path, rows: Sequence[dict[str, Any]], fieldnames: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def feature_collection(
    features: Sequence[dict[str, Any]],
    *,
    created_at: str,
    source_graph_sha256: str,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    collection_metadata = {
        "created_at": created_at,
        "source_graph_sha256": source_graph_sha256,
        "output_crs": "EPSG:4326",
        **PROVENANCE_FLAGS,
    }
    if metadata:
        collection_metadata.update(metadata)
    # Callers may add descriptive metadata, but they may never relax the
    # review boundary on evaluator output.
    collection_metadata.update(PROVENANCE_FLAGS)
    return {
        "type": "FeatureCollection",
        "metadata": collection_metadata,
        "features": list(features),
    }


def geometry_feature(geometry_wgs84: Any, properties: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "Feature",
        "geometry": mapping(force_2d(geometry_wgs84)),
        "properties": {**properties, **PROVENANCE_FLAGS},
    }


def load_graph_edges(project_root: Path) -> tuple[list[EdgeRecord], dict[str, Any]]:
    graph_path = project_root / GRAPH_PATH
    graph = load_json(graph_path)
    metadata = graph.get("metadata") or {}
    if metadata.get("crs") != "EPSG:4326":
        raise ValueError("baseline graph must declare EPSG:4326")
    graph_sha = file_sha256(graph_path)
    to_5179 = Transformer.from_crs("EPSG:4326", "EPSG:5179", always_xy=True)
    edges: list[EdgeRecord] = []
    seen: set[str] = set()
    for feature in graph.get("features") or []:
        properties = feature.get("properties") or {}
        if properties.get("feature_type") != "edge":
            continue
        edge_id = str(properties.get("edge_id") or "")
        if not edge_id or edge_id in seen:
            raise ValueError(f"missing or duplicate edge_id: {edge_id!r}")
        geometry_wgs84 = force_2d(shape(feature.get("geometry")))
        if geometry_wgs84.is_empty or not geometry_wgs84.is_valid:
            raise ValueError(f"invalid graph edge geometry: {edge_id}")
        geometry_5179 = transform(to_5179.transform, geometry_wgs84)
        edges.append(
            EdgeRecord(
                edge_id=edge_id,
                geometry_wgs84=geometry_wgs84,
                geometry_5179=geometry_5179,
                properties=dict(properties),
            )
        )
        seen.add(edge_id)
    if not edges:
        raise ValueError("baseline graph has no edge features")
    return edges, {
        "graph_path": GRAPH_PATH.as_posix(),
        "graph_sha256": graph_sha,
        "raw_graph_sha256": metadata.get("osm_snapshot_sha256"),
        "edge_count": len(edges),
        "verified": bool(metadata.get("verified", False)),
    }


def percentile(values: Iterable[float], percentile_value: float) -> float | None:
    ordered = sorted(float(value) for value in values if value is not None)
    if not ordered:
        return None
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * percentile_value / 100.0
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction


def transformed(geometry: Any, source_crs: str, target_crs: str) -> Any:
    transformer = Transformer.from_crs(source_crs, target_crs, always_xy=True)
    return force_2d(transform(transformer.transform, force_2d(geometry)))


def now_iso() -> str:
    from datetime import datetime

    return datetime.now().astimezone().isoformat(timespec="seconds")


def _direction_difference(first: Any, second: Any) -> float | None:
    first_angle = _dominant_angle(first)
    second_angle = _dominant_angle(second)
    if first_angle is None or second_angle is None:
        return None
    difference = abs(first_angle - second_angle) % 180.0
    return min(difference, 180.0 - difference)


def _dominant_angle(geometry: Any) -> float | None:
    longest: tuple[float, tuple[float, float], tuple[float, float]] | None = None
    parts = (
        list(geometry.geoms)
        if geometry.geom_type == "MultiLineString"
        else [geometry]
    )
    for part in parts:
        coordinates = list(part.coords)
        for start, end in zip(coordinates, coordinates[1:]):
            length = math.hypot(end[0] - start[0], end[1] - start[1])
            if longest is None or length > longest[0]:
                longest = (length, start, end)
    if longest is None or longest[0] <= 0:
        return None
    _, start, end = longest
    return math.degrees(math.atan2(end[1] - start[1], end[0] - start[0])) % 180.0
