#!/usr/bin/env python3
"""Fetch Kakao Roadview cube faces for the ON:WAY manual pre-review.

The files are temporary evidence for human/AI-assisted visual inspection only.
They are not packaged for redistribution or model training.
"""

from __future__ import annotations

import csv
import json
import math
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from PIL import Image, ImageDraw, ImageFont
from urllib.request import Request, urlopen


ROOT = Path("/workspace/scratch/0ad8d7d5b1e3")
INPUT = ROOT / "onway_corridor_mvp" / "selected_crosswalks_40.csv"
OUTPUT = ROOT / "onway_corridor_mvp" / "roadview_evidence"
FACES = ("front", "right", "back", "left")
USER_AGENT = "Mozilla/5.0 (compatible; ONWAY-MVP-manual-review/1.0)"


def get_json(url: str, attempts: int = 4) -> dict:
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            request = Request(url, headers={"User-Agent": USER_AGENT})
            with urlopen(request, timeout=90) as response:
                return json.loads(response.read().decode("utf-8"))
        except Exception as exc:  # network evidence collection is retryable
            last_error = exc
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"JSON fetch failed after {attempts} attempts: {url}") from last_error


def resolve_panoid(lat: str, lon: str, attempts: int = 4) -> tuple[str, str]:
    url = f"https://map.kakao.com/link/roadview/{lat},{lon}"
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            request = Request(url, headers={"User-Agent": USER_AGENT})
            with urlopen(request, timeout=90) as response:
                final_url = response.geturl()
                response.read(1)
            panoid = parse_qs(urlparse(final_url).query).get("panoid", [""])[0]
            if not panoid:
                match = re.search(r"panoid=(\d+)", final_url)
                panoid = match.group(1) if match else ""
            if not panoid:
                raise ValueError(f"No panoid in redirect: {final_url}")
            return panoid, final_url
        except Exception as exc:
            last_error = exc
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"Roadview redirect failed: {url}") from last_error


def download(url: str, path: Path, attempts: int = 5) -> None:
    if path.exists() and path.stat().st_size > 10_000:
        return
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            request = Request(url, headers={"User-Agent": USER_AGENT})
            with urlopen(request, timeout=120) as response:
                content = response.read()
            if len(content) < 10_000:
                raise ValueError(f"Unexpectedly small image ({len(content)} bytes)")
            path.write_bytes(content)
            return
        except Exception as exc:
            last_error = exc
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"Image fetch failed after {attempts} attempts: {url}") from last_error


def bearing_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dl = math.radians(lon2 - lon1)
    y = math.sin(dl) * math.cos(p2)
    x = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return (math.degrees(math.atan2(y, x)) + 360) % 360


def distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6_371_000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(a))


def make_contact(sample_dir: Path, label: str) -> None:
    images = [Image.open(sample_dir / f"{face}.jpg").convert("RGB") for face in FACES]
    tile = 900
    header = 64
    canvas = Image.new("RGB", (tile * 2, (tile + header) * 2), "white")
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.load_default(size=22)
    for idx, (face, image) in enumerate(zip(FACES, images)):
        image.thumbnail((tile, tile), Image.Resampling.LANCZOS)
        x = (idx % 2) * tile
        y = (idx // 2) * (tile + header)
        canvas.paste(image, (x, y + header))
        draw.text((x + 14, y + 16), f"{label} | {face}", fill="black", font=font)
    canvas.save(sample_dir / "contact.jpg", quality=92)


def fetch_one(row: dict[str, str]) -> dict[str, object]:
    sample_id = row["sample_id"]
    lat, lon = row["lat"], row["lon"]
    sample_dir = OUTPUT / sample_id
    sample_dir.mkdir(parents=True, exist_ok=True)

    panoid, final_url = resolve_panoid(lat, lon)
    node_url = f"https://rv.map.kakao.com/roadview-search/v2/node/{panoid}?SERVICE=csspano"
    node = get_json(node_url)["street_view"]["street"]
    img_path = node["img_path"]
    cube_base = f"https://ssl.daumcdn.net/t1.daumcdn.net/map_roadview{img_path}_cube"

    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {
            pool.submit(download, f"{cube_base}/{face}_1200.jpg", sample_dir / f"{face}.jpg"): face
            for face in FACES
        }
        for future in as_completed(futures):
            future.result()

    make_contact(sample_dir, sample_id)
    pano_lat = float(node["wgsy"])
    pano_lon = float(node["wgsx"])
    target_lat = float(lat)
    target_lon = float(lon)
    result: dict[str, object] = {
        "sample_id": sample_id,
        "management_id": row["management_id"],
        "target_lat": target_lat,
        "target_lon": target_lon,
        "panoid": str(panoid),
        "pano_lat": pano_lat,
        "pano_lon": pano_lon,
        "pano_distance_m": round(distance_m(pano_lat, pano_lon, target_lat, target_lon), 2),
        "target_bearing_deg": round(bearing_deg(pano_lat, pano_lon, target_lat, target_lon), 1),
        "pano_angle_deg": float(node["angle"]),
        "shot_date": str(node["shot_date"]),
        "shot_tool": str(node.get("shot_tool", "")),
        "street_name": str(node.get("st_name", "")),
        "img_path": str(img_path),
        "roadview_link": row["roadview_center_url"],
        "resolved_url": final_url,
        "node_url": node_url,
        "contact_path": str(sample_dir / "contact.jpg"),
        "status": "downloaded",
    }
    (sample_dir / "metadata.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return result


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    with INPUT.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))

    results: list[dict[str, object]] = []
    failures: list[dict[str, str]] = []
    workers = int(os.environ.get("ONWAY_FETCH_WORKERS", "4"))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        future_map = {pool.submit(fetch_one, row): row for row in rows}
        for future in as_completed(future_map):
            row = future_map[future]
            try:
                result = future.result()
                results.append(result)
                print(f"OK {row['sample_id']} {result['shot_date']}", flush=True)
            except Exception as exc:
                failures.append({"sample_id": row["sample_id"], "error": repr(exc)})
                print(f"FAIL {row['sample_id']} {exc!r}", flush=True)

    results.sort(key=lambda item: int(str(item["sample_id"])[2:]))
    if results:
        with (OUTPUT / "roadview_metadata.csv").open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(results[0].keys()))
            writer.writeheader()
            writer.writerows(results)
    (OUTPUT / "fetch_summary.json").write_text(
        json.dumps(
            {"requested": len(rows), "downloaded": len(results), "failures": failures},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    if failures:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
