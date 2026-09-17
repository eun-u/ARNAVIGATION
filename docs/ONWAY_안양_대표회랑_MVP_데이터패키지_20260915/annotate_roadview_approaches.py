#!/usr/bin/env python3
"""Create bearing-guided approach evidence images from Roadview cube faces.

Markers are geometric guides only. They do not prove the curb/tactile/obstacle state.
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path("/workspace/scratch/0ad8d7d5b1e3")
EVIDENCE = ROOT / "onway_corridor_mvp" / "roadview_evidence"
APPROACHES = ROOT / "onway_corridor_mvp" / "approaches_80_review_queue.csv"
METADATA = EVIDENCE / "roadview_metadata.csv"
FACE_OFFSETS = {"front": 0.0, "right": -90.0, "back": 180.0, "left": 90.0}


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
        candidates.append((abs(wrap180(target_bearing - center)), face, wrap180(target_bearing - center)))
    _, face, delta = min(candidates)
    return face, delta


def annotate(row: dict[str, str], meta: dict[str, str]) -> Image.Image:
    lat = float(row["lat"])
    lon = float(row["lon"])
    pano_lat = float(meta["pano_lat"])
    pano_lon = float(meta["pano_lon"])
    pano_angle = float(meta["pano_angle_deg"])
    bearing = bearing_deg(pano_lat, pano_lon, lat, lon)
    distance = distance_m(pano_lat, pano_lon, lat, lon)
    face, delta = select_face(bearing, pano_angle)

    image = Image.open(EVIDENCE / row["sample_id"] / f"{face}.jpg").convert("RGB")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=25)
    small = ImageFont.load_default(size=19)
    width, height = image.size
    x = width / 2 + (width / 2) * math.tan(math.radians(delta))
    estimated_camera_height = 2.4
    y = height / 2 + (height / 2) * estimated_camera_height / max(distance, 0.4)
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
    draw.text((16, 12), f"{row['approach_id']} | face={face} | bearing guide", fill="white", font=font)
    draw.text((16, 62), f"pano distance={distance:.1f}m | delta={delta:+.1f}deg | shot={meta['shot_date'][:10]}", fill="white", font=small)
    return image


def main() -> None:
    if METADATA.exists():
        with METADATA.open(encoding="utf-8-sig", newline="") as handle:
            metadata = {row["sample_id"]: row for row in csv.DictReader(handle)}
    else:
        metadata = {}
        for path in EVIDENCE.glob("CW*/metadata.json"):
            row = json.loads(path.read_text(encoding="utf-8"))
            metadata[row["sample_id"]] = {key: str(value) for key, value in row.items()}
    with APPROACHES.open(encoding="utf-8-sig", newline="") as handle:
        approaches = list(csv.DictReader(handle))

    by_sample: dict[str, list[dict[str, str]]] = {}
    for row in approaches:
        if row["sample_id"] in metadata:
            by_sample.setdefault(row["sample_id"], []).append(row)

    for sample_id, rows in by_sample.items():
        rows.sort(key=lambda row: row["side_label"])
        images = [annotate(row, metadata[sample_id]) for row in rows]
        out_dir = EVIDENCE / sample_id
        for row, image in zip(rows, images):
            image.save(out_dir / f"approach_{row['side_label']}_target.jpg", quality=93)
        canvas = Image.new("RGB", (1800, 900), "white")
        for idx, image in enumerate(images):
            image.thumbnail((900, 900), Image.Resampling.LANCZOS)
            canvas.paste(image, (idx * 900, 0))
        canvas.save(out_dir / "approach_contact.jpg", quality=93)
        print(f"OK {sample_id}")


if __name__ == "__main__":
    main()
