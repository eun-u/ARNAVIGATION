#!/usr/bin/env python3
"""Fetch one bearing-selected Roadview cube face per ON:WAY approach endpoint."""

from __future__ import annotations

import csv
import json
import math
import os
import re
import shutil
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from urllib.request import Request, urlopen

from PIL import Image, ImageDraw, ImageFont


ROOT = Path("/workspace/scratch/0ad8d7d5b1e3")
INPUT = ROOT / "onway_corridor_mvp" / "approaches_80_review_queue.csv"
EVIDENCE = ROOT / "onway_corridor_mvp" / "roadview_evidence"
OUTPUT = EVIDENCE / "approaches"
CACHE = EVIDENCE / "_cube_cache"
USER_AGENT = "Mozilla/5.0 (compatible; ONWAY-MVP-manual-review/1.0)"
FACE_OFFSETS = {"front": 0.0, "right": -90.0, "back": 180.0, "left": 90.0}
LOCK = threading.Lock()


def fetch_bytes(url: str, attempts: int = 5) -> tuple[bytes, str]:
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            request = Request(url, headers={"User-Agent": USER_AGENT})
            with urlopen(request, timeout=120) as response:
                return response.read(), response.geturl()
        except Exception as exc:
            last_error = exc
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"fetch failed: {url}") from last_error


def resolve_panoid(url: str) -> tuple[str, str]:
    content, final_url = fetch_bytes(url)
    del content
    panoid = parse_qs(urlparse(final_url).query).get("panoid", [""])[0]
    if not panoid:
        match = re.search(r"panoid=(\d+)", final_url)
        panoid = match.group(1) if match else ""
    if not panoid:
        raise ValueError(f"No panoid in {final_url}")
    return panoid, final_url


def wrap180(angle: float) -> float:
    return (angle + 180) % 360 - 180


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


def select_face(target_bearing: float, pano_angle: float) -> tuple[str, float]:
    candidates = []
    for face, offset in FACE_OFFSETS.items():
        center = (pano_angle + offset) % 360
        delta = wrap180(target_bearing - center)
        candidates.append((abs(delta), face, delta))
    _, face, delta = min(candidates)
    return face, delta


def load_center_index() -> dict[str, Path]:
    index: dict[str, Path] = {}
    for path in EVIDENCE.glob("CW*/metadata.json"):
        meta = json.loads(path.read_text(encoding="utf-8"))
        sample_dir = path.parent
        for face in FACE_OFFSETS:
            image = sample_dir / f"{face}.jpg"
            if image.exists():
                index[f"{meta['panoid']}:{face}"] = image
    return index


CENTER_INDEX = load_center_index()


def get_face_image(panoid: str, img_path: str, face: str) -> Path:
    center = CENTER_INDEX.get(f"{panoid}:{face}")
    if center:
        return center
    CACHE.mkdir(parents=True, exist_ok=True)
    target = CACHE / f"{panoid}_{face}.jpg"
    with LOCK:
        if target.exists() and target.stat().st_size > 10_000:
            return target
    url = f"https://ssl.daumcdn.net/t1.daumcdn.net/map_roadview{img_path}_cube/{face}_1200.jpg"
    content, _ = fetch_bytes(url)
    if len(content) < 10_000:
        raise ValueError(f"Unexpected image size {len(content)}: {url}")
    with LOCK:
        if not target.exists():
            target.write_bytes(content)
    return target


def annotate(source: Path, row: dict[str, str], meta: dict[str, object]) -> Path:
    image = Image.open(source).convert("RGB")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=25)
    small = ImageFont.load_default(size=19)
    width, height = image.size
    delta = float(meta["face_delta_deg"])
    distance = float(meta["pano_distance_m"])
    x = width / 2 + (width / 2) * math.tan(math.radians(delta))
    y = height / 2 + (height / 2) * 2.4 / max(distance, 0.4)
    x = max(25, min(width - 25, x))
    y = max(height / 2 + 35, min(height - 30, y))
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    odraw = ImageDraw.Draw(overlay)
    odraw.rectangle((0, 0, width, 112), fill=(0, 0, 0, 175))
    odraw.line((x, height / 2, x, height - 1), fill=(0, 220, 255, 230), width=8)
    odraw.ellipse((x - 32, y - 32, x + 32, y + 32), outline=(255, 64, 64, 255), width=10)
    odraw.rectangle((max(0, x - 110), max(height / 2, y - 105), min(width, x + 110), min(height, y + 105)), outline=(255, 210, 0, 220), width=5)
    image = Image.alpha_composite(image.convert("RGBA"), overlay).convert("RGB")
    draw = ImageDraw.Draw(image)
    draw.text((16, 12), f"{row['approach_id']} | endpoint-nearest pano | face={meta['face']}", fill="white", font=font)
    draw.text((16, 62), f"distance={distance:.1f}m | delta={delta:+.1f}deg | shot={str(meta['shot_date'])[:10]}", fill="white", font=small)
    out_dir = OUTPUT / row["approach_id"]
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "target.jpg"
    image.save(out, quality=94)
    return out


def fetch_one(row: dict[str, str]) -> dict[str, object]:
    panoid, final_url = resolve_panoid(row["evidence_url"])
    node_url = f"https://rv.map.kakao.com/roadview-search/v2/node/{panoid}?SERVICE=csspano"
    node_bytes, _ = fetch_bytes(node_url)
    node = json.loads(node_bytes.decode("utf-8"))["street_view"]["street"]
    pano_lat = float(node["wgsy"])
    pano_lon = float(node["wgsx"])
    lat = float(row["lat"])
    lon = float(row["lon"])
    bearing = bearing_deg(pano_lat, pano_lon, lat, lon)
    distance = distance_m(pano_lat, pano_lon, lat, lon)
    face, delta = select_face(bearing, float(node["angle"]))
    source = get_face_image(str(panoid), str(node["img_path"]), face)
    meta: dict[str, object] = {
        "approach_id": row["approach_id"],
        "sample_id": row["sample_id"],
        "side_label": row["side_label"],
        "target_lat": lat,
        "target_lon": lon,
        "panoid": str(panoid),
        "pano_lat": pano_lat,
        "pano_lon": pano_lon,
        "pano_distance_m": round(distance, 2),
        "target_bearing_deg": round(bearing, 1),
        "pano_angle_deg": float(node["angle"]),
        "face": face,
        "face_delta_deg": round(delta, 1),
        "shot_date": str(node["shot_date"]),
        "roadview_link": row["evidence_url"],
        "resolved_url": final_url,
        "node_url": node_url,
        "status": "downloaded",
    }
    out = annotate(source, row, meta)
    meta["target_image_path"] = str(out)
    (out.parent / "metadata.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return meta


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    with INPUT.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    results: list[dict[str, object]] = []
    failures: list[dict[str, str]] = []
    workers = int(os.environ.get("ONWAY_FETCH_WORKERS", "6"))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        future_map = {pool.submit(fetch_one, row): row for row in rows}
        for future in as_completed(future_map):
            row = future_map[future]
            try:
                result = future.result()
                results.append(result)
                print(f"OK {row['approach_id']} {result['pano_distance_m']}m", flush=True)
            except Exception as exc:
                failures.append({"approach_id": row["approach_id"], "error": repr(exc)})
                print(f"FAIL {row['approach_id']} {exc!r}", flush=True)
    results.sort(key=lambda item: (int(str(item["sample_id"])[2:]), str(item["side_label"])))
    if results:
        with (OUTPUT / "approach_view_metadata.csv").open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(results[0].keys()))
            writer.writeheader()
            writer.writerows(results)
    (OUTPUT / "fetch_summary.json").write_text(
        json.dumps({"requested": len(rows), "downloaded": len(results), "failures": failures}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    if failures:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
