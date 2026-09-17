from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import osmnx as ox


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "raw" / "anyang_corridor_walk_20260915.graphml"
DEFAULT_METADATA = PROJECT_ROOT / "data" / "raw" / "anyang_corridor_walk_20260915.metadata.json"
DEFAULT_BBOX = (126.9185, 37.3885, 126.9312, 37.4035)
DEFAULT_AS_OF = "2026-09-15T23:59:59Z"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fetch_graph(
    output: Path,
    metadata_path: Path,
    bbox: tuple[float, float, float, float],
    as_of: str,
) -> dict:
    output.parent.mkdir(parents=True, exist_ok=True)
    ox.settings.use_cache = True
    ox.settings.cache_folder = PROJECT_ROOT / "data" / "raw" / "osmnx_cache"
    ox.settings.requests_timeout = 180
    ox.settings.overpass_settings = (
        f'[out:json][timeout:{{timeout}}]{{maxsize}}[date:"{as_of}"]'
    )
    ox.settings.useful_tags_way = list(
        dict.fromkeys(
            [
                *ox.settings.useful_tags_way,
                "access",
                "foot",
                "highway",
                "incline",
                "kerb",
                "sidewalk",
                "smoothness",
                "surface",
                "wheelchair",
                "width",
            ]
        )
    )

    graph = ox.graph.graph_from_bbox(
        bbox,
        network_type="walk",
        simplify=True,
        retain_all=True,
        truncate_by_edge=True,
    )
    ox.io.save_graphml(graph, output)

    metadata = {
        "dataset": "NaVi Anyang OSM walking network snapshot",
        "bbox_left_bottom_right_top": list(bbox),
        "as_of": as_of,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "source": "OpenStreetMap via Overpass API",
        "source_url": "https://www.openstreetmap.org/copyright",
        "license": "ODbL",
        "network_type": "walk",
        "osmnx_version": ox.__version__,
        "nodes": graph.number_of_nodes(),
        "edges": graph.number_of_edges(),
        "sha256": sha256(output),
    }
    metadata_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return metadata


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fetch and freeze the Anyang corridor OSM walking graph."
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--metadata", type=Path, default=DEFAULT_METADATA)
    parser.add_argument("--as-of", default=DEFAULT_AS_OF)
    parser.add_argument(
        "--bbox",
        nargs=4,
        type=float,
        metavar=("LEFT", "BOTTOM", "RIGHT", "TOP"),
        default=DEFAULT_BBOX,
    )
    args = parser.parse_args()
    metadata = fetch_graph(
        args.output.resolve(),
        args.metadata.resolve(),
        tuple(args.bbox),
        args.as_of,
    )
    print(json.dumps(metadata, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
