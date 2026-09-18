"""Run the complete provenance-safe NaVi spatial evaluation batch."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

from shapely.geometry import shape

try:
    from scripts.build_graph_enrichment_candidates import (
        run_graph_enrichment_candidates,
    )
    from scripts.evaluate_cross_sources import run_cross_source_evaluation
    from scripts.evaluate_dem import run_dem_evaluation
    from scripts.evaluate_orthophoto import run_orthophoto_evaluation
    from scripts.evaluate_topographic_map import run_topographic_evaluation
    from scripts.spatial_evaluation_common import (
        PROVENANCE_FLAGS,
        feature_collection,
        file_sha256,
        geometry_feature,
        load_graph_edges,
        load_json,
        now_iso,
        write_csv,
        write_json,
    )
    from scripts.validate_spatial_sources import run_validation
except ModuleNotFoundError:  # Direct execution from scripts/
    from build_graph_enrichment_candidates import (  # type: ignore[no-redef]
        run_graph_enrichment_candidates,
    )
    from evaluate_cross_sources import run_cross_source_evaluation  # type: ignore[no-redef]
    from evaluate_dem import run_dem_evaluation  # type: ignore[no-redef]
    from evaluate_orthophoto import run_orthophoto_evaluation  # type: ignore[no-redef]
    from evaluate_topographic_map import run_topographic_evaluation  # type: ignore[no-redef]
    from spatial_evaluation_common import (  # type: ignore[no-redef]
        PROVENANCE_FLAGS,
        feature_collection,
        file_sha256,
        geometry_feature,
        load_graph_edges,
        load_json,
        now_iso,
        write_csv,
        write_json,
    )
    from validate_spatial_sources import run_validation  # type: ignore[no-redef]


OUTPUT_ROOT = Path("data/processed/evaluation")
REPORT_PATH = Path("docs/spatial_data_evaluation_report.md")
REVIEW_FIELDS = (
    "review_queue_id",
    "review_source",
    "review_role",
    "review_status",
    "candidate_type",
    "source_feature_id",
    "graph_edge_id",
    "mapping_status",
    "longitude",
    "latitude",
    "derived",
    "verified",
    "graph_update_allowed",
)


def _stable_sample(features: Iterable[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    ranked = sorted(
        features,
        key=lambda feature: hashlib.sha256(
            json.dumps(feature, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest(),
    )
    return ranked[:limit]


def _queue_feature(
    feature: dict[str, Any], source: str, role: str, ordinal: int
) -> dict[str, Any]:
    result = json.loads(json.dumps(feature, ensure_ascii=False))
    properties = result.setdefault("properties", {})
    source_identifier = (
        properties.get("review_id")
        or properties.get("source_feature_id")
        or properties.get("public_crosswalk_id")
        or properties.get("edge_id")
        or str(ordinal)
    )
    queue_id = hashlib.sha256(
        f"{source}|{role}|{source_identifier}".encode("utf-8")
    ).hexdigest()[:20]
    properties.update(
        {
            "review_queue_id": f"RQ-{queue_id}",
            "review_source": source,
            "review_role": role,
            "review_status": "pending",
            **PROVENANCE_FLAGS,
        }
    )
    return result


def _sample_geojson(
    path: Path,
    source: str,
    role_key: str,
    *,
    per_group: int = 30,
) -> list[dict[str, Any]]:
    data = load_json(path)
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for feature in data.get("features") or []:
        properties = feature.get("properties") or {}
        role = str(properties.get(role_key) or properties.get("candidate_type") or "general")
        groups[role].append(feature)
    selected: list[dict[str, Any]] = []
    for role, values in sorted(groups.items()):
        for index, feature in enumerate(_stable_sample(values, per_group)):
            selected.append(_queue_feature(feature, source, role, index))
    return selected


def _sample_dem(
    project_root: Path,
    edges_by_id: dict[str, Any],
    *,
    per_group: int = 30,
) -> list[dict[str, Any]]:
    csv_path = project_root / OUTPUT_ROOT / "dem" / "edge_slope_candidates.csv"
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[str(row.get("quality_flag") or "unknown")].append(row)
    selected: list[dict[str, Any]] = []
    for quality, values in sorted(groups.items()):
        ranked = sorted(
            values,
            key=lambda row: hashlib.sha256(str(row.get("edge_id")).encode("utf-8")).hexdigest(),
        )[:per_group]
        for index, row in enumerate(ranked):
            edge_id = str(row.get("edge_id") or "")
            edge = edges_by_id.get(edge_id)
            if edge is None:
                continue
            feature = geometry_feature(
                edge.geometry_wgs84,
                {
                    "edge_id": edge_id,
                    "candidate_type": "dem_edge_slope_review",
                    "quality_flag": quality,
                    "slope_pct_abs_candidate": _number(row.get("slope_pct_abs_candidate")),
                    "dem_resolution_m": _number(row.get("dem_resolution_m")),
                    "hard_constraint_eligible": False,
                },
            )
            selected.append(_queue_feature(feature, "dem", quality, index))
    return selected


def _number(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _write_review_csv(path: Path, features: list[dict[str, Any]]) -> None:
    rows: list[dict[str, Any]] = []
    for feature in features:
        properties = feature.get("properties") or {}
        centroid = shape(feature["geometry"]).centroid
        rows.append(
            {
                "review_queue_id": properties.get("review_queue_id"),
                "review_source": properties.get("review_source"),
                "review_role": properties.get("review_role"),
                "review_status": properties.get("review_status"),
                "candidate_type": properties.get("candidate_type"),
                "source_feature_id": properties.get("source_feature_id")
                or properties.get("public_crosswalk_id")
                or properties.get("crosswalk_id")
                or properties.get("edge_id"),
                "graph_edge_id": properties.get("graph_edge_id")
                or properties.get("best_edge_id")
                or properties.get("edge_id"),
                "mapping_status": properties.get("graph_mapping_status")
                or properties.get("match_status")
                or properties.get("quality_flag"),
                "longitude": round(float(centroid.x), 8),
                "latitude": round(float(centroid.y), 8),
                "derived": True,
                "verified": False,
                "graph_update_allowed": False,
            }
        )
    write_csv(path, rows, REVIEW_FIELDS)


def _markdown_report(summary: dict[str, Any]) -> str:
    topographic = summary["results"]["topographic_map"]
    dem = summary["results"]["dem"]
    orthophoto = summary["results"]["orthophoto"]
    cross = summary["results"]["cross_sources"]
    validation = summary["results"]["common_validation"]
    topo_metrics = topographic["metrics"]
    dem_metrics = dem["metrics"]
    ortho_metrics = orthophoto["metrics"]
    cross_metrics = cross["metrics"]
    return f"""# NaVi 공간데이터 평가 결과

생성 시각: `{summary['created_at']}`

## 결론

이번 배치는 원본 데이터와 기존 Accessibility Graph를 변경하지 않았다. 모든 후보는 `derived=true`, `verified=false`, `graph_update_allowed=false`이며, Human Review 승인 전에는 공유 Graph에 반영할 수 없다.

| 데이터 | 판정 | 현재 허용 용도 | 금지/보류 |
|---|---|---|---|
| 수치지형도 | 조건부 채택 | 보도·횡단보도·계단 등 공간 검수 후보 | 자동 Graph 편입 |
| 공개 DEM 90m | 부분 채택 | 거시 지형 맥락·승인 불가 경로 민감도 진단 | Edge 경사 hard constraint·verified 값 승격 |
| 정사영상 25cm | 부분 채택 | 시각 QA | 기준점 RMSE 전 자동 좌표 보정 |
| 정밀도로지도 | 부분 채택 | 보도·횡단보도·연석 geometry QA | 연석 높이·통과 가능성 추론 |
| 안양시 횡단보도 | 부분 채택 | 위치 교차검증 | 빈 접근성 값을 false로 간주 |

## 공통 검증

- 상태: `{validation['summary']['status']}`
- 검증 대상: {validation['summary']['validation_target_count']}개
- pass/warning/fail/hold: {validation['summary']['pass']}/{validation['summary']['warning']}/{validation['summary']['fail']}/{validation['summary']['hold']}
- 기준 Graph: {summary['graph']['edge_count']} edges, SHA-256 `{summary['graph']['before_sha256']}`
- 실행 후 Graph SHA-256: `{summary['graph']['after_sha256']}` (변경 없음: `{str(summary['graph']['unchanged']).lower()}`)

## 수치지형도

- 대표 회랑 평가 객체: {topographic['inventory']['mapping_enabled_feature_count_in_context']}개
- 코드별 객체: `{json.dumps(topo_metrics['feature_counts_by_code_in_context'], ensure_ascii=False, sort_keys=True)}`
- unique / ambiguous / unmatched: {topo_metrics['unique_match_count']} / {topo_metrics['ambiguous_match_count']} / {topo_metrics['unmatched_count']}
- unique match rate: {topo_metrics['unique_match_rate_pct']}%
- 신규 객체 검수 후보: {topo_metrics['new_object_candidate_count']}개
- 판정: 80% 자동 매핑 gate 미달이므로 Human Review 필요

## DEM

- 해상도: {dem['source']['resolution_m']}m
- Edge coverage: {dem_metrics['valid_edge_length_pct']}%
- 3개 미만 DEM cell을 사용하는 Edge: {dem_metrics['fewer_than_three_cells_edge_count']} / {dem_metrics['evaluated_edge_count']}
- hard constraint 적용 가능 Edge: {dem_metrics['hard_constraint_eligible_edge_count']}개
- 판정: 지형 맥락과 `approval_eligible=false` 경로 민감도 진단에는 사용 가능하나 보도 Edge 경사 판정에는 부적합

## 정사영상

- 대표 회랑 타일: {ortho_metrics['corridor_tile_count']}개
- 복원 픽셀 크기: {ortho_metrics['pixel_size_m_min']}~{ortho_metrics['pixel_size_m_max']}m
- Graph 길이 coverage: {ortho_metrics['graph_coverage']['covered_edge_length_pct']}%
- 시각 검수 후보: {ortho_metrics['visual_review_candidate_count']}개
- 기준점 RMSE: 미측정(`null`), 따라서 geometry correction 보류

## 정밀도로지도 및 횡단보도 교차검증

- 회랑 문맥 내 HD 객체: `{json.dumps(cross_metrics['hd_context_feature_counts'], ensure_ascii=False, sort_keys=True)}`
- 공공 횡단보도 검수점: {cross_metrics['public_crosswalk_context_count']}개
- HD 횡단보도 대응 결과: `{json.dumps(cross_metrics['public_to_hd_correspondence_counts'], ensure_ascii=False, sort_keys=True)}`
- 접근성 값이 하나 이상 빈 행: {cross_metrics['rows_with_unknown_accessibility_count']}개
- 판정: 정밀도로지도는 필요하지만 부분 coverage의 보조 QA 자료이며 OSM 대체재가 아님

## Human Review 패키지

- 표본 후보: {summary['review_queue']['feature_count']}개
- GeoJSON: `data/processed/evaluation/review_queue.geojson`
- CSV: `data/processed/evaluation/review_queue.csv`
- 초기 상태: 전부 `pending`

## 채택 Gate

1. 수치지형도: 역할별 30개 표본의 위치·의미 정확도를 사람이 확인한다.
2. DEM: 더 정밀한 고도원 또는 현장 측정 전에는 slope hard constraint를 활성화하지 않는다.
3. 정사영상: 독립 기준점으로 RMSE를 산출하기 전에는 Graph geometry를 이동하지 않는다.
4. 정밀도로지도/횡단보도: coverage 밖의 부재를 객체 부재로 해석하지 않는다.
5. 승인된 관측만 별도 verified observation으로 변환한 뒤 Graph 갱신 절차에 전달한다.
"""


def run_all(
    project_root: Path,
    output_root: Path = OUTPUT_ROOT,
    *,
    created_at: str | None = None,
) -> dict[str, Any]:
    project_root = project_root.resolve()
    output_root = output_root if output_root.is_absolute() else project_root / output_root
    timestamp = created_at or now_iso()
    edges, graph = load_graph_edges(project_root)
    graph_path = project_root / Path(str(graph["graph_path"]))
    graph_sha_before = file_sha256(graph_path)

    validation = run_validation(project_root, output_root, created_at=timestamp)
    topographic = run_topographic_evaluation(
        project_root, output_root / "topographic_map", created_at=timestamp
    )
    dem = run_dem_evaluation(project_root, output_root / "dem", created_at=timestamp)
    orthophoto = run_orthophoto_evaluation(
        project_root, output_root / "orthophoto", created_at=timestamp
    )
    cross_sources = run_cross_source_evaluation(
        project_root, output_root / "cross_sources", created_at=timestamp
    )

    queue: list[dict[str, Any]] = []
    queue.extend(
        _sample_geojson(
            output_root / "topographic_map" / "matches.geojson",
            "topographic_map",
            "evaluation_role",
        )
    )
    queue.extend(
        _sample_geojson(
            output_root / "topographic_map" / "new_object_candidates.geojson",
            "topographic_map_unmatched",
            "evaluation_role",
        )
    )
    queue.extend(
        _sample_geojson(
            output_root / "orthophoto" / "geometry_review_candidates.geojson",
            "orthophoto",
            "candidate_type",
        )
    )
    queue.extend(
        _sample_geojson(
            output_root / "cross_sources" / "hdmap_graph_candidates.geojson",
            "hdmap",
            "evaluation_role",
        )
    )
    queue.extend(
        _sample_geojson(
            output_root / "cross_sources" / "crosswalk_correspondence.geojson",
            "public_crosswalk",
            "hd_match_status",
        )
    )
    queue.extend(_sample_dem(project_root, {edge.edge_id: edge for edge in edges}))
    queue.sort(key=lambda feature: feature["properties"]["review_queue_id"])
    queue_ids = [feature["properties"]["review_queue_id"] for feature in queue]
    if len(queue_ids) != len(set(queue_ids)):
        raise RuntimeError("review queue IDs are not unique")
    write_json(
        output_root / "review_queue.geojson",
        feature_collection(
            queue,
            created_at=timestamp,
            source_graph_sha256=graph_sha_before,
            metadata={"purpose": "deterministic_human_review_sample", "status": "pending"},
        ),
    )
    _write_review_csv(output_root / "review_queue.csv", queue)

    graph_sha_after = file_sha256(graph_path)
    if graph_sha_before != graph_sha_after:
        raise RuntimeError("baseline routing graph changed during read-only evaluation")
    summary = {
        "schema_version": "1.0",
        "created_at": timestamp,
        "status": "fail"
        if validation["common_validation"]["summary"]["fail"]
        else "warning",
        "graph": {
            "path": graph["graph_path"],
            "edge_count": graph["edge_count"],
            "before_sha256": graph_sha_before,
            "after_sha256": graph_sha_after,
            "unchanged": graph_sha_before == graph_sha_after,
        },
        "results": {
            "common_validation": validation["common_validation"],
            "topographic_map": topographic,
            "dem": dem,
            "orthophoto": orthophoto,
            "cross_sources": cross_sources,
        },
        "review_queue": {
            "feature_count": len(queue),
            "status": "pending",
            "geojson": "data/processed/evaluation/review_queue.geojson",
            "csv": "data/processed/evaluation/review_queue.csv",
        },
        "decision": {
            "shared_graph_update": "reject_until_human_approval",
            "topographic_map": "hold_for_sample_review",
            "dem_terrain_context": "partial_accept",
            "dem_edge_hard_constraint": "reject",
            "orthophoto_visual_qa": "partial_accept",
            "orthophoto_geometry_correction": "hold_for_control_point_rmse",
            "hdmap_geometry_qa": "partial_accept",
            "crosswalk_accessibility_unknowns": "preserve_null",
        },
        "policy": {**PROVENANCE_FLAGS, "routing_graph_mutated": False},
    }
    write_json(output_root / "evaluation_summary.json", summary)
    graph_enrichment = run_graph_enrichment_candidates(
        project_root,
        output_root / "graph_enrichment",
        created_at=timestamp,
    )
    summary["results"]["graph_enrichment_candidates"] = graph_enrichment
    write_json(output_root / "evaluation_summary.json", summary)
    report_path = project_root / REPORT_PATH
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(_markdown_report(summary), encoding="utf-8")
    return summary


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run all NaVi spatial evaluations.")
    parser.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output-root", type=Path, default=OUTPUT_ROOT)
    parser.add_argument("--created-at")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = run_all(args.project_root, args.output_root, created_at=args.created_at)
    except Exception as exc:  # noqa: BLE001
        print(f"Spatial evaluation batch failed: {exc}", file=sys.stderr)
        return 2
    print(
        "Spatial evaluation batch: "
        f"status={result['status']} review={result['review_queue']['feature_count']} "
        f"graph_unchanged={result['graph']['unchanged']}"
    )
    return 1 if result["status"] == "fail" else 0


if __name__ == "__main__":
    raise SystemExit(main())
