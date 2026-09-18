"""Compare deterministic M2 reports or build a failure-only retry manifest."""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any, Iterable


class OfflineReportError(ValueError):
    pass


def _read_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise OfflineReportError(f"could not read JSON object: {path}") from error
    if not isinstance(value, dict):
        raise OfflineReportError(f"JSON root must be an object: {path}")
    return value


def _prediction_signature(prediction: dict[str, Any]) -> tuple[Any, ...]:
    return (
        prediction.get("label"),
        prediction.get("confidence"),
        prediction.get("left"),
        prediction.get("top"),
        prediction.get("right"),
        prediction.get("bottom"),
        prediction.get("trackId"),
    )


def _frames_by_case(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    try:
        frames = report["evaluation"]["frames"]
    except (KeyError, TypeError) as error:
        raise OfflineReportError("report is missing evaluation.frames") from error
    if not isinstance(frames, list):
        raise OfflineReportError("evaluation.frames must be an array")
    result: dict[str, dict[str, Any]] = {}
    for frame in frames:
        if not isinstance(frame, dict) or not isinstance(frame.get("caseId"), str):
            raise OfflineReportError("each frame report must have a string caseId")
        if frame["caseId"] in result:
            raise OfflineReportError(f"duplicate report caseId: {frame['caseId']}")
        result[frame["caseId"]] = frame
    return result


def compare_reports(
    baseline: dict[str, Any], candidate: dict[str, Any]
) -> dict[str, Any]:
    baseline_frames = _frames_by_case(baseline)
    candidate_frames = _frames_by_case(candidate)
    case_ids = sorted(set(baseline_frames) | set(candidate_frames))
    changed: list[dict[str, Any]] = []
    for case_id in case_ids:
        before = baseline_frames.get(case_id)
        after = candidate_frames.get(case_id)
        before_predictions = (
            sorted(
                (_prediction_signature(item) for item in before.get("predictions", [])),
                key=repr,
            )
            if before
            else None
        )
        after_predictions = (
            sorted(
                (_prediction_signature(item) for item in after.get("predictions", [])),
                key=repr,
            )
            if after
            else None
        )
        before_status = before.get("status") if before else None
        after_status = after.get("status") if after else None
        if before_predictions != after_predictions or before_status != after_status:
            changed.append(
                {
                    "case_id": case_id,
                    "baseline_status": before_status,
                    "candidate_status": after_status,
                    "baseline_predictions": before_predictions,
                    "candidate_predictions": after_predictions,
                }
            )

    baseline_overall = baseline.get("evaluation", {}).get("overall", {})
    candidate_overall = candidate.get("evaluation", {}).get("overall", {})
    metric_delta = {
        key: candidate_overall.get(key, 0) - baseline_overall.get(key, 0)
        for key in ("truePositives", "falsePositives", "falseNegatives")
    }
    return {
        "baseline_dataset_id": baseline.get("datasetId"),
        "candidate_dataset_id": candidate.get("datasetId"),
        "identical_predictions": not changed,
        "compared_case_count": len(case_ids),
        "changed_case_count": len(changed),
        "changed_cases": changed,
        "overall_metric_delta": metric_delta,
        "baseline_model_versions": baseline.get("evaluation", {}).get("modelVersions", []),
        "candidate_model_versions": candidate.get("evaluation", {}).get("modelVersions", []),
        "latency_excluded": True,
    }


def build_retry_manifest(
    manifest: dict[str, Any], report: dict[str, Any]
) -> dict[str, Any]:
    try:
        failures = report["evaluation"]["failedFrames"]
        frames = manifest["frames"]
    except (KeyError, TypeError) as error:
        raise OfflineReportError("manifest or report is missing required frame data") from error
    failed_ids = {
        failure["caseId"]
        for failure in failures
        if isinstance(failure, dict) and isinstance(failure.get("caseId"), str)
    }
    if not failed_ids:
        raise OfflineReportError("report contains no failed frames")
    available_ids = {frame.get("case_id") for frame in frames if isinstance(frame, dict)}
    missing = sorted(failed_ids - available_ids)
    if missing:
        raise OfflineReportError("failed case IDs are absent from manifest: " + ", ".join(missing))
    retry = copy.deepcopy(manifest)
    retry["dataset_id"] = f"{manifest.get('dataset_id', 'dataset')}-retry"
    retry["frames"] = [frame for frame in frames if frame.get("case_id") in failed_ids]
    return retry


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    compare = commands.add_parser("compare")
    compare.add_argument("--baseline", required=True, type=Path)
    compare.add_argument("--candidate", required=True, type=Path)
    compare.add_argument("--output", required=True, type=Path)
    compare.add_argument("--allow-differences", action="store_true")
    retry = commands.add_parser("retry-manifest")
    retry.add_argument("--manifest", required=True, type=Path)
    retry.add_argument("--report", required=True, type=Path)
    retry.add_argument("--output", required=True, type=Path)
    return parser.parse_args(argv)


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        if args.command == "compare":
            result = compare_reports(_read_object(args.baseline), _read_object(args.candidate))
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
            print(
                f"Compared {result['compared_case_count']} cases; "
                f"changed={result['changed_case_count']}"
            )
            return 0 if result["identical_predictions"] or args.allow_differences else 2
        retry = build_retry_manifest(_read_object(args.manifest), _read_object(args.report))
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(retry, indent=2) + "\n", encoding="utf-8")
        print(f"Wrote failure-only manifest with {len(retry['frames'])} frames")
        return 0
    except OfflineReportError as error:
        raise SystemExit(f"offline report operation failed: {error}") from error


if __name__ == "__main__":
    raise SystemExit(main())
