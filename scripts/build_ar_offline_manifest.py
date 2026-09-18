"""Build a deterministic M2 replay manifest from an M1 MP4/telemetry pair.

This importer intentionally uses only the Python standard library.  The MP4 is
decoded later by Android's MediaMetadataRetriever, while this step aligns sample
positions to the nearest M1 telemetry row and records provenance hashes.
"""

from __future__ import annotations

import argparse
import bisect
import csv
import hashlib
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


REQUIRED_COLUMNS = (
    "elapsed_realtime_ms",
    "tracking_quality",
    "depth_active",
    "route_aligned",
    "tracking_loss_count",
    "last_recovery_ms",
    "frame_time_ms",
    "message",
)
SUPPORTED_ROTATIONS = (0, 90, 180, 270)


class ManifestImportError(ValueError):
    """Raised when an input pair cannot form a trustworthy replay manifest."""


@dataclass(frozen=True)
class TelemetrySample:
    elapsed_realtime_ms: int
    tracking_quality: str
    depth_active: bool
    route_aligned: bool
    tracking_loss_count: int
    last_recovery_ms: int | None
    frame_time_ms: float
    message: str | None


def _parse_bool(value: str, *, row_number: int, column: str) -> bool:
    normalized = value.strip().lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    raise ManifestImportError(
        f"row {row_number}: {column} must be true or false, got {value!r}"
    )


def _parse_int(
    value: str, *, row_number: int, column: str, optional: bool = False
) -> int | None:
    normalized = value.strip()
    if optional and not normalized:
        return None
    try:
        return int(normalized)
    except ValueError as error:
        raise ManifestImportError(
            f"row {row_number}: {column} must be an integer, got {value!r}"
        ) from error


def read_telemetry(path: Path) -> list[TelemetrySample]:
    if not path.is_file():
        raise ManifestImportError(f"telemetry CSV does not exist: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != list(REQUIRED_COLUMNS):
            raise ManifestImportError(
                "telemetry header must exactly match: " + ",".join(REQUIRED_COLUMNS)
            )
        samples: list[TelemetrySample] = []
        for row_number, row in enumerate(reader, start=2):
            timestamp = _parse_int(
                row["elapsed_realtime_ms"],
                row_number=row_number,
                column="elapsed_realtime_ms",
            )
            loss_count = _parse_int(
                row["tracking_loss_count"],
                row_number=row_number,
                column="tracking_loss_count",
            )
            recovery = _parse_int(
                row["last_recovery_ms"],
                row_number=row_number,
                column="last_recovery_ms",
                optional=True,
            )
            try:
                frame_time = float(row["frame_time_ms"].strip())
            except ValueError as error:
                raise ManifestImportError(
                    f"row {row_number}: frame_time_ms must be numeric"
                ) from error
            if not math.isfinite(frame_time) or frame_time < 0:
                raise ManifestImportError(
                    f"row {row_number}: frame_time_ms must be finite and non-negative"
                )
            tracking_quality = row["tracking_quality"].strip()
            if not tracking_quality:
                raise ManifestImportError(
                    f"row {row_number}: tracking_quality must not be blank"
                )
            assert timestamp is not None and loss_count is not None
            if timestamp < 0 or loss_count < 0 or (recovery is not None and recovery < 0):
                raise ManifestImportError(
                    f"row {row_number}: telemetry counters must be non-negative"
                )
            samples.append(
                TelemetrySample(
                    elapsed_realtime_ms=timestamp,
                    tracking_quality=tracking_quality,
                    depth_active=_parse_bool(
                        row["depth_active"],
                        row_number=row_number,
                        column="depth_active",
                    ),
                    route_aligned=_parse_bool(
                        row["route_aligned"],
                        row_number=row_number,
                        column="route_aligned",
                    ),
                    tracking_loss_count=loss_count,
                    last_recovery_ms=recovery,
                    frame_time_ms=frame_time,
                    message=row["message"].strip() or None,
                )
            )

    if not samples:
        raise ManifestImportError("telemetry CSV must contain at least one sample")
    timestamps = [sample.elapsed_realtime_ms for sample in samples]
    if any(current <= previous for previous, current in zip(timestamps, timestamps[1:])):
        raise ManifestImportError("elapsed_realtime_ms values must be strictly increasing")
    return samples


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _sample_positions(duration_ms: int, interval_ms: int) -> list[int]:
    if interval_ms <= 0:
        raise ManifestImportError("sample interval must be positive")
    positions = list(range(0, duration_ms + 1, interval_ms))
    if positions[-1] != duration_ms:
        positions.append(duration_ms)
    return positions


def _nearest_sample(
    samples: list[TelemetrySample], relative_timestamps: list[int], position_ms: int
) -> TelemetrySample:
    insertion = bisect.bisect_left(relative_timestamps, position_ms)
    candidates = []
    if insertion < len(samples):
        candidates.append(samples[insertion])
    if insertion > 0:
        candidates.append(samples[insertion - 1])
    origin = samples[0].elapsed_realtime_ms
    return min(
        candidates,
        key=lambda sample: (
            abs((sample.elapsed_realtime_ms - origin) - position_ms),
            sample.elapsed_realtime_ms,
        ),
    )


def _relative_dataset_path(path: Path, manifest_directory: Path) -> str:
    try:
        return path.resolve().relative_to(manifest_directory.resolve()).as_posix()
    except ValueError as error:
        raise ManifestImportError(
            f"input must be inside the manifest directory: {path}"
        ) from error


def _load_annotations(path: Path | None) -> dict[str, dict[str, Any]]:
    if path is None:
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ManifestImportError(f"could not read annotation JSON: {path}") from error
    if not isinstance(value, dict) or not all(
        isinstance(key, str) and isinstance(item, dict) for key, item in value.items()
    ):
        raise ManifestImportError(
            "annotation JSON must be an object keyed by case_id with object values"
        )
    allowed = {"annotations", "segmentation"}
    for case_id, item in value.items():
        unknown = set(item) - allowed
        if unknown:
            raise ManifestImportError(
                f"annotation entry {case_id!r} has unsupported keys: {sorted(unknown)}"
            )
    return value


def build_manifest(
    *,
    video_path: Path,
    telemetry_path: Path,
    output_path: Path,
    dataset_id: str,
    interval_ms: int = 1000,
    rotation_degrees: int = 0,
    annotation_path: Path | None = None,
    privacy_status: str = "unreviewed",
    consent_reference: str | None = None,
) -> dict[str, Any]:
    if not dataset_id.strip():
        raise ManifestImportError("dataset_id must not be blank")
    if rotation_degrees not in SUPPORTED_ROTATIONS:
        raise ManifestImportError(f"rotation must be one of {SUPPORTED_ROTATIONS}")
    if privacy_status not in {"unreviewed", "redacted", "approved"}:
        raise ManifestImportError("privacy_status must be unreviewed, redacted, or approved")
    if consent_reference is not None and not consent_reference.strip():
        raise ManifestImportError("consent_reference must not be blank")
    if not video_path.is_file() or video_path.stat().st_size == 0:
        raise ManifestImportError(f"video must be a non-empty file: {video_path}")
    if video_path.suffix.lower() != ".mp4":
        raise ManifestImportError("video must use the .mp4 extension")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    relative_video = _relative_dataset_path(video_path, output_path.parent)
    relative_telemetry = _relative_dataset_path(telemetry_path, output_path.parent)
    samples = read_telemetry(telemetry_path)
    annotations = _load_annotations(annotation_path)
    origin = samples[0].elapsed_realtime_ms
    relative_timestamps = [sample.elapsed_realtime_ms - origin for sample in samples]
    duration_ms = relative_timestamps[-1]
    gaps = [current - previous for previous, current in zip(relative_timestamps, relative_timestamps[1:])]
    max_gap_ms = max(gaps, default=0)

    frames: list[dict[str, Any]] = []
    offsets: list[int] = []
    for index, position_ms in enumerate(_sample_positions(duration_ms, interval_ms)):
        case_id = f"{re.sub(r'[^A-Za-z0-9._-]', '_', dataset_id)}-{index:06d}"
        sample = _nearest_sample(samples, relative_timestamps, position_ms)
        sample_position = sample.elapsed_realtime_ms - origin
        offset_ms = sample_position - position_ms
        offsets.append(offset_ms)
        frame: dict[str, Any] = {
            "case_id": case_id,
            "video_path": relative_video,
            "video_position_ms": position_ms,
            "timestamp_nanos": position_ms * 1_000_000,
            "rotation_degrees": rotation_degrees,
            "context": {
                "session_id": dataset_id,
                "tracking_quality": sample.tracking_quality,
                "depth_active": sample.depth_active,
                "route_aligned": sample.route_aligned,
                "tracking_loss_count": sample.tracking_loss_count,
                "last_recovery_ms": sample.last_recovery_ms,
                "ar_frame_time_ms": sample.frame_time_ms,
                "telemetry_offset_ms": offset_ms,
                "message": sample.message,
            },
            "annotations": [],
        }
        frame.update(annotations.get(case_id, {}))
        frames.append(frame)

    unused_annotations = sorted(set(annotations) - {frame["case_id"] for frame in frames})
    if unused_annotations:
        raise ManifestImportError(
            "annotation JSON contains unknown case_id values: " + ", ".join(unused_annotations)
        )

    return {
        "schema_version": 1,
        "dataset_id": dataset_id,
        "source_recording": {
            "video_path": relative_video,
            "telemetry_path": relative_telemetry,
            "video_sha256": sha256(video_path),
            "telemetry_sha256": sha256(telemetry_path),
            "telemetry_origin_elapsed_realtime_ms": origin,
            "duration_ms": duration_ms,
            "sample_interval_ms": interval_ms,
            "sync_strategy": "first_telemetry_sample_zero",
            "estimated_sync_error_ms": max(
                max((abs(offset) for offset in offsets), default=0), max_gap_ms
            ),
            "privacy_status": privacy_status,
            "consent_reference": consent_reference,
        },
        "frames": frames,
    }


def write_manifest(manifest: dict[str, Any], output_path: Path) -> None:
    output_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", required=True, type=Path)
    parser.add_argument("--telemetry", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--dataset-id", required=True)
    parser.add_argument("--interval-ms", type=int, default=1000)
    parser.add_argument("--rotation-degrees", type=int, default=0)
    parser.add_argument("--annotations", type=Path)
    parser.add_argument(
        "--privacy-status",
        choices=("unreviewed", "redacted", "approved"),
        default="unreviewed",
    )
    parser.add_argument("--consent-reference")
    return parser.parse_args(argv)


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        manifest = build_manifest(
            video_path=args.video.resolve(),
            telemetry_path=args.telemetry.resolve(),
            output_path=args.output.resolve(),
            dataset_id=args.dataset_id,
            interval_ms=args.interval_ms,
            rotation_degrees=args.rotation_degrees,
            annotation_path=args.annotations.resolve() if args.annotations else None,
            privacy_status=args.privacy_status,
            consent_reference=args.consent_reference,
        )
        write_manifest(manifest, args.output.resolve())
    except ManifestImportError as error:
        raise SystemExit(f"manifest import failed: {error}") from error
    print(
        f"Wrote {len(manifest['frames'])} replay frames to {args.output.resolve()} "
        f"(estimated sync error <= {manifest['source_recording']['estimated_sync_error_ms']} ms)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
