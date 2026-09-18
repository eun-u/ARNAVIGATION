import pytest

from scripts.offline_report_tools import (
    OfflineReportError,
    build_retry_manifest,
    compare_reports,
)


def report(*frames, failures=(), overall=None):
    return {
        "datasetId": "fixture",
        "evaluation": {
            "frames": list(frames),
            "failedFrames": list(failures),
            "overall": overall
            or {"truePositives": 1, "falsePositives": 0, "falseNegatives": 0},
            "modelVersions": ["fixture-v1"],
        },
    }


def frame(case_id, predictions, latency=1):
    return {
        "caseId": case_id,
        "status": "success",
        "inferenceMillis": latency,
        "predictions": predictions,
    }


def test_comparison_ignores_latency_and_prediction_order() -> None:
    first = {"label": "car", "confidence": 0.8, "left": 0, "top": 0, "right": 1, "bottom": 1}
    second = {"label": "person", "confidence": 0.9, "left": 0, "top": 0, "right": 1, "bottom": 1}

    result = compare_reports(
        report(frame("one", [first, second], latency=3)),
        report(frame("one", [second, first], latency=99)),
    )

    assert result["identical_predictions"] is True
    assert result["changed_case_count"] == 0
    assert result["latency_excluded"] is True


def test_comparison_reports_changed_predictions_and_metric_delta() -> None:
    result = compare_reports(
        report(frame("one", [])),
        report(
            frame("one", [{"label": "car", "confidence": 0.5}]),
            overall={"truePositives": 1, "falsePositives": 1, "falseNegatives": 0},
        ),
    )
    assert result["identical_predictions"] is False
    assert result["overall_metric_delta"]["falsePositives"] == 1


def test_builds_failure_only_retry_manifest() -> None:
    manifest = {
        "schema_version": 1,
        "dataset_id": "fixture",
        "frames": [{"case_id": "one"}, {"case_id": "two"}],
    }
    retry = build_retry_manifest(
        manifest,
        report(failures=[{"caseId": "two", "reason": "decode"}]),
    )
    assert retry["dataset_id"] == "fixture-retry"
    assert retry["frames"] == [{"case_id": "two"}]
    assert len(manifest["frames"]) == 2


def test_retry_rejects_unknown_failed_case() -> None:
    with pytest.raises(OfflineReportError, match="absent from manifest"):
        build_retry_manifest(
            {"dataset_id": "fixture", "frames": [{"case_id": "one"}]},
            report(failures=[{"caseId": "missing"}]),
        )
