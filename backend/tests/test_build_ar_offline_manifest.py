import csv
import json
from pathlib import Path

import pytest

from scripts.build_ar_offline_manifest import ManifestImportError, build_manifest, write_manifest


HEADERS = [
    "elapsed_realtime_ms",
    "tracking_quality",
    "depth_active",
    "route_aligned",
    "tracking_loss_count",
    "last_recovery_ms",
    "frame_time_ms",
    "message",
]


def write_telemetry(path: Path, rows: list[list[object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(HEADERS)
        writer.writerows(rows)


def test_builds_deterministic_aligned_manifest_with_hashes(tmp_path: Path) -> None:
    video = tmp_path / "walk.mp4"
    video.write_bytes(b"fake-mp4-fixture")
    telemetry = tmp_path / "walk.csv"
    write_telemetry(
        telemetry,
        [
            [1000, "TRACKING", "true", "false", 0, "", 16.2, "start"],
            [1300, "TRACKING", "true", "true", 0, "", 17.0, ""],
            [1600, "PAUSED", "false", "false", 1, 1550, 40.0, "lost"],
        ],
    )
    output = tmp_path / "manifest.json"

    first = build_manifest(
        video_path=video,
        telemetry_path=telemetry,
        output_path=output,
        dataset_id="walk-fixture",
        interval_ms=250,
    )
    second = build_manifest(
        video_path=video,
        telemetry_path=telemetry,
        output_path=output,
        dataset_id="walk-fixture",
        interval_ms=250,
    )

    assert first == second
    assert [frame["video_position_ms"] for frame in first["frames"]] == [0, 250, 500, 600]
    assert first["frames"][1]["context"]["telemetry_offset_ms"] == 50
    assert first["frames"][2]["context"]["tracking_quality"] == "PAUSED"
    assert first["source_recording"]["estimated_sync_error_ms"] == 300
    assert len(first["source_recording"]["video_sha256"]) == 64
    write_manifest(first, output)
    assert json.loads(output.read_text(encoding="utf-8")) == first


@pytest.mark.parametrize(
    "rows,match",
    [
        ([], "at least one sample"),
        (
            [
                [1000, "TRACKING", "true", "false", 0, "", 16, ""],
                [1000, "TRACKING", "true", "false", 0, "", 16, ""],
            ],
            "strictly increasing",
        ),
        ([[1000, "TRACKING", "maybe", "false", 0, "", 16, ""]], "true or false"),
    ],
)
def test_rejects_malformed_telemetry(
    tmp_path: Path, rows: list[list[object]], match: str
) -> None:
    video = tmp_path / "walk.mp4"
    video.write_bytes(b"video")
    telemetry = tmp_path / "walk.csv"
    write_telemetry(telemetry, rows)

    with pytest.raises(ManifestImportError, match=match):
        build_manifest(
            video_path=video,
            telemetry_path=telemetry,
            output_path=tmp_path / "manifest.json",
            dataset_id="invalid",
        )


def test_rejects_inputs_outside_manifest_directory(tmp_path: Path) -> None:
    dataset = tmp_path / "dataset"
    dataset.mkdir()
    video = tmp_path / "walk.mp4"
    video.write_bytes(b"video")
    telemetry = dataset / "walk.csv"
    write_telemetry(
        telemetry,
        [[1000, "TRACKING", "true", "false", 0, "", 16, ""]],
    )

    with pytest.raises(ManifestImportError, match="inside the manifest directory"):
        build_manifest(
            video_path=video,
            telemetry_path=telemetry,
            output_path=dataset / "manifest.json",
            dataset_id="unsafe",
        )
