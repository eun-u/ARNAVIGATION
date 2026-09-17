from __future__ import annotations

import csv
import json
import statistics
from collections import Counter
from pathlib import Path

import build_onway_corridor as corridor


ROOT = Path("/workspace/scratch/0ad8d7d5b1e3")
DATA_DIR = ROOT / "onway_corridor_mvp"
META_PATH = DATA_DIR / "roadview_evidence" / "approaches" / "approach_view_metadata.csv"
QUEUE_PATH = DATA_DIR / "approaches_80_review_queue.csv"
RESULT_PATH = DATA_DIR / "ai_precheck_80.csv"
SCENARIO_PATH = DATA_DIR / "route_comparison_ai_candidate_scenario.csv"
AS_OF = "2026-09-15"


# AI 사전판독 1차. pass는 보도턱 낮춤/무단차, 점자블록, 통행공간이 모두
# 선명할 때만 부여한다. block은 물리적 차단 또는 점자블록 부재가 선명한 경우만 부여한다.
PASS1 = {
    "CW01-A": ("있음", "없음", "없음", "block", "횡단 지점은 보이지만 점자블록이 보이지 않음"),
    "CW04-A": ("판독불가", "판독불가", "공사", "block", "횡단 진행 방향이 공사 가림막으로 막힌 후보"),
    "CW04-B": ("있음", "있음", "없음", "pass", "경사로와 점자블록이 보이고 통행공간이 열려 있음"),
    "CW05-A": ("있음", "있음", "없음", "pass", "경사로와 점자블록이 보이고 통행공간이 열려 있음"),
    "CW10-B": ("있음", "없음", "없음", "block", "횡단 지점은 보이지만 점자블록이 보이지 않음"),
    "CW13-B": ("있음", "없음", "없음", "block", "경사로는 보이나 점자블록이 보이지 않음"),
    "CW14-A": ("있음", "있음", "없음", "pass", "경사로와 점자블록이 보이고 통행공간이 열려 있음"),
    "CW14-B": ("있음", "있음", "없음", "pass", "경사로와 점자블록이 보이고 통행공간이 열려 있음"),
    "CW16-A": ("있음", "있음", "없음", "pass", "경사로와 점자블록이 보이고 통행공간이 열려 있음"),
    "CW16-B": ("있음", "있음", "없음", "pass", "경사로와 점자블록이 보이고 통행공간이 열려 있음"),
    "CW18-A": ("있음", "없음", "없음", "block", "시장 진입 횡단 지점에 점자블록이 보이지 않음"),
    "CW19-B": ("있음", "있음", "없음", "pass", "경사로와 점자블록이 보이고 통행공간이 열려 있음"),
    "CW21-A": ("있음", "있음", "없음", "pass", "경사로와 점자블록이 보이고 통행공간이 열려 있음"),
    "CW22-A": ("있음", "있음", "없음", "pass", "경사로와 점자블록이 보이고 통행공간이 열려 있음"),
    "CW24-A": ("있음", "있음", "없음", "pass", "경사로와 점자블록이 보이고 통행공간이 열려 있음"),
    "CW25-A": ("있음", "있음", "없음", "pass", "경사로와 점자블록이 보이고 통행공간이 열려 있음"),
    "CW25-B": ("있음", "있음", "없음", "pass", "경사로와 점자블록이 보이고 통행공간이 열려 있음"),
    "CW26-A": ("있음", "있음", "없음", "pass", "경사로와 점자블록이 보이고 통행공간이 열려 있음"),
    "CW27-A": ("있음", "있음", "없음", "pass", "경사로와 점자블록이 보이고 통행공간이 열려 있음"),
    "CW28-B": ("있음", "있음", "없음", "pass", "경사로와 점자블록이 보이고 통행공간이 열려 있음"),
    "CW29-A": ("있음", "있음", "없음", "pass", "경사로와 점자블록이 보이고 통행공간이 열려 있음"),
    "CW29-B": ("있음", "있음", "없음", "pass", "경사로와 점자블록이 보이고 통행공간이 열려 있음"),
    "CW30-B": ("있음", "있음", "없음", "pass", "경사로와 점자블록이 보이고 통행공간이 열려 있음"),
    "CW31-B": ("있음", "있음", "없음", "pass", "경사로와 점자블록이 보이고 통행공간이 열려 있음"),
    "CW32-B": ("있음", "있음", "없음", "pass", "경사로와 점자블록이 보이고 통행공간이 열려 있음"),
    "CW34-A": ("있음", "있음", "없음", "pass", "경사로와 점자블록이 보이고 통행공간이 열려 있음"),
    "CW35-A": ("있음", "있음", "없음", "pass", "경사로와 점자블록이 보이고 통행공간이 열려 있음"),
    "CW36-A": ("있음", "있음", "없음", "pass", "원거리 착지부에 경사로와 점자블록이 있는 것으로 1차 판독"),
    "CW38-A": ("있음", "있음", "없음", "pass", "경사로와 점자블록이 보이고 통행공간이 열려 있음"),
    "CW38-B": ("있음", "있음", "없음", "pass", "경사로와 점자블록이 보이고 통행공간이 열려 있음"),
    "CW40-A": ("있음", "있음", "없음", "pass", "착지부 가장자리에서 점자블록과 낮춤부가 보임"),
}


GEOMETRY_UNKNOWN = {
    "CW02-A", "CW02-B", "CW03-B", "CW07-A", "CW07-B", "CW09-A", "CW09-B",
    "CW11-A", "CW11-B", "CW12-A", "CW12-B", "CW13-A", "CW15-A", "CW15-B",
    "CW20-A", "CW20-B", "CW23-A", "CW23-B", "CW26-B", "CW33-A", "CW33-B",
    "CW35-B", "CW36-B", "CW39-A", "CW39-B", "CW40-B",
}

OCCLUDED_UNKNOWN = {
    "CW03-A", "CW06-A", "CW06-B", "CW08-A", "CW10-A", "CW17-A", "CW18-B",
    "CW27-B", "CW37-A",
}


# 지정 40개를 역순으로 다시 본 AI 반복 판독. 이것은 사람 2인의 독립 검수가 아니다.
PASS2_PASS = {
    "CW05-A", "CW14-A", "CW14-B", "CW16-A", "CW16-B", "CW21-A", "CW25-A",
    "CW25-B", "CW27-A", "CW29-A", "CW29-B", "CW32-B", "CW34-A", "CW34-B",
    "CW38-A", "CW38-B",
}
PASS2_BLOCK = {"CW01-A", "CW18-A"}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        raise ValueError(f"no rows for {path}")
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def unknown_pass(approach_id: str) -> tuple[str, str, str, str, str]:
    if approach_id in GEOMETRY_UNKNOWN:
        return ("판독불가", "판독불가", "지오메트리불일치", "unknown", "접근부 추정점과 영상의 실제 횡단 착지부가 정합하지 않음")
    if approach_id in OCCLUDED_UNKNOWN:
        return ("판독불가", "판독불가", "차량/적치물가림", "unknown", "차량·적치물 또는 공사물로 핵심 시설이 가려짐")
    return ("판독불가", "판독불가", "시야불충분", "unknown", "착지부가 카메라 직하부·화면 밖에 있어 핵심 시설을 확인할 수 없음")


def result_confidence(result: str, note: str) -> float:
    if result == "pass":
        return 0.82
    if result == "block":
        return 0.82 if "공사" in note else 0.76
    return 0.58 if "정합" in note else 0.52


def candidate_label(result: str, obstacle: str, note: str) -> str:
    if result == "pass":
        return "likely_accessible_candidate"
    if result == "block":
        return "construction_block_candidate" if obstacle == "공사" else "tactile_absent_candidate"
    if obstacle == "지오메트리불일치":
        return "geometry_mismatch_candidate"
    if "가림" in obstacle:
        return "occlusion_review_needed"
    return "visibility_review_needed"


def kappa(labels1: list[str], labels2: list[str]) -> tuple[float, float]:
    if len(labels1) != len(labels2) or not labels1:
        raise ValueError("label arrays must have equal non-zero length")
    n = len(labels1)
    observed = sum(a == b for a, b in zip(labels1, labels2)) / n
    c1, c2 = Counter(labels1), Counter(labels2)
    expected = sum((c1[k] / n) * (c2[k] / n) for k in {"pass", "block", "unknown"})
    return observed, (observed - expected) / (1 - expected) if expected < 1 else 1.0


def build_results() -> tuple[list[dict], dict]:
    queue = read_csv(QUEUE_PATH)
    meta = {r["approach_id"]: r for r in read_csv(META_PATH)}
    if len(queue) != 80 or len(meta) != 80:
        raise RuntimeError(f"expected 80 queue/meta rows, got {len(queue)}/{len(meta)}")

    rows = []
    repeat_1, repeat_2 = [], []
    for q in queue:
        aid = q["approach_id"]
        p1 = PASS1.get(aid, unknown_pass(aid))
        p2 = None
        if q["double_review_required"].lower() == "true":
            if aid in PASS2_PASS:
                p2 = ("있음", "있음", "없음", "pass", "역순·착지부 중심 재판독에서 경사로와 점자블록을 확인")
            elif aid in PASS2_BLOCK:
                p2 = ("있음", "없음", "없음", "block", "역순·착지부 중심 재판독에서도 점자블록 부재 후보")
            else:
                p2 = unknown_pass(aid)
            repeat_1.append(p1[3])
            repeat_2.append(p2[3])

        if p2 and p1[3] != p2[3]:
            final_result = "unknown"
            final_note = f"AI 반복판독 불일치({p1[3]}↔{p2[3]}); 사람 조정 필요"
            final_curb = final_tactile = "판독불가"
            final_obstacle = "판독불일치"
        else:
            final_curb, final_tactile, final_obstacle, final_result, final_note = p1

        m = meta[aid]
        rows.append({
            "approach_id": aid,
            "sample_id": q["sample_id"],
            "side_label": q["side_label"],
            "double_review_required": q["double_review_required"],
            "evidence_shot_date": m["shot_date"],
            "pano_distance_m": m["pano_distance_m"],
            "roadview_link": m["roadview_link"],
            "resolved_roadview_url": m["resolved_url"],
            "pass1_reviewer": "Codex_AI_precheck_1",
            "pass1_date": AS_OF,
            "pass1_curb": p1[0],
            "pass1_tactile": p1[1],
            "pass1_obstacle": p1[2],
            "pass1_result": p1[3],
            "pass1_note": p1[4],
            "pass2_reviewer": "Codex_AI_precheck_2" if p2 else "",
            "pass2_date": AS_OF if p2 else "",
            "pass2_curb": p2[0] if p2 else "",
            "pass2_tactile": p2[1] if p2 else "",
            "pass2_obstacle": p2[2] if p2 else "",
            "pass2_result": p2[3] if p2 else "",
            "pass2_note": p2[4] if p2 else "",
            "final_ai_precheck_curb": final_curb,
            "final_ai_precheck_tactile": final_tactile,
            "final_ai_precheck_obstacle": final_obstacle,
            "final_ai_precheck_result": final_result,
            "final_ai_precheck_note": final_note,
            "ai_candidate_label": candidate_label(final_result, final_obstacle, final_note),
            "ai_confidence": result_confidence(final_result, final_note),
            "human_review_required": "Y",
            "ai_human_approved": "",
            "official_c_effect": "미반영(사람 승인 전)",
        })

    observed, kap = kappa(repeat_1, repeat_2)
    summary = {
        "pass1_counts": dict(Counter(r["pass1_result"] for r in rows)),
        "pass2_counts_40": dict(Counter(r["pass2_result"] for r in rows if r["pass2_result"])),
        "final_counts": dict(Counter(r["final_ai_precheck_result"] for r in rows)),
        "repeatability_n": len(repeat_1),
        "repeatability_agreement": round(observed, 4),
        "repeatability_kappa": round(kap, 4),
        "human_review_completed": 0,
        "human_approved_ai_candidates": 0,
    }
    return rows, summary


def update_queue(results: list[dict]) -> None:
    by_id = {r["approach_id"]: r for r in results}
    rows = read_csv(QUEUE_PATH)
    for row in rows:
        ai = by_id[row["approach_id"]]
        row["review_status"] = "ai_precheck_complete_pending_human_review"
        row["ai_candidate_label"] = ai["ai_candidate_label"]
        row["ai_confidence"] = ai["ai_confidence"]
        row["ai_human_approved"] = ""
        row["evidence_date"] = ai["evidence_shot_date"]
        row["evidence_url"] = ai["roadview_link"]
        row["ai_precheck_result"] = ai["final_ai_precheck_result"]
        row["ai_precheck_note"] = ai["final_ai_precheck_note"]
        row["ai_precheck_pass2_status"] = "완료" if ai["pass2_result"] else "비대상"
    write_csv(QUEUE_PATH, rows)


def build_candidate_scenario(results: list[dict]) -> tuple[list[dict], dict]:
    blocked_samples = sorted({r["sample_id"] for r in results if r["final_ai_precheck_result"] == "block"})
    selected = corridor.select_sample(corridor.read_crosswalks())
    nodes, segments, _ = corridor.parse_osm()
    corridor.make_approaches(selected, segments)
    adjacency, edge_lookup = corridor.build_graph(nodes, segments)
    graph_nodes = set(adjacency)
    public_blocked = {r["osm_proxy_edge_id"] for r in selected if r["public_risk"]}
    unknown_edges = {r["osm_proxy_edge_id"] for r in selected if not r["explicit"]} - public_blocked
    ai_candidate_edges = {r["osm_proxy_edge_id"] for r in selected if r["sample_id"] in blocked_samples}
    pois = corridor.make_pois(selected, graph_nodes, nodes)
    od_pairs = corridor.select_od_pairs(pois, adjacency, edge_lookup, public_blocked, unknown_edges)

    scenario_rows = []
    for idx, pair in enumerate(od_pairs, 1):
        b = pair["B"]
        cstar = corridor.dijkstra(
            adjacency, edge_lookup, pair["origin"]["node_id"], pair["destination"]["node_id"],
            "C", public_blocked, unknown_edges, ai_candidate_edges,
        )
        row = {
            "od_id": f"OD{idx:02d}",
            "origin": pair["origin"]["name"],
            "destination": pair["destination"]["name"],
            "scenario": "C* 미승인 AI후보 5개 전부 승인 가정",
            "official_status": "비공식 스트레스테스트; 실제 C 아님",
            "candidate_block_samples": ";".join(blocked_samples),
            "candidate_block_proxy_edges": ";".join(sorted(ai_candidate_edges)),
            "b_route_distance_m": round(b["distance_m"], 1),
            "cstar_route_available": "Y" if cstar else "N",
            "cstar_route_distance_m": round(cstar["distance_m"], 1) if cstar else "",
            "distance_delta_vs_b_m": round(cstar["distance_m"] - b["distance_m"], 1) if cstar else "",
            "distance_delta_vs_b_pct": round((cstar["distance_m"] / b["distance_m"] - 1) * 100, 2) if cstar and b["distance_m"] else "",
            "route_changed_vs_b": "Y" if cstar and cstar["nodes"] != b["nodes"] else ("N" if cstar else "경로없음"),
            "candidate_edges_used_by_b": len(set(b["edges"]) & ai_candidate_edges),
            "interpretation": "사람 승인 전 의사결정용 민감도 분석이며 경로 안내에 사용 금지",
        }
        scenario_rows.append(row)
    deltas = [float(r["distance_delta_vs_b_pct"]) for r in scenario_rows if r["distance_delta_vs_b_pct"] != ""]
    summary = {
        "candidate_block_samples": blocked_samples,
        "candidate_block_proxy_edges": sorted(ai_candidate_edges),
        "routes_changed_vs_b": sum(r["route_changed_vs_b"] == "Y" for r in scenario_rows),
        "routes_unavailable": sum(r["cstar_route_available"] == "N" for r in scenario_rows),
        "median_distance_delta_vs_b_pct": round(statistics.median(deltas), 2) if deltas else None,
        "max_distance_delta_vs_b_pct": round(max(deltas), 2) if deltas else None,
    }
    return scenario_rows, summary


def update_manifest(precheck: dict, scenario: dict) -> None:
    path = DATA_DIR / "run_manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8-sig"))
    manifest.update({
        "roadview_approach_evidence_downloaded": 80,
        "ai_precheck_first_pass_completed": 80,
        "ai_precheck_second_pass_completed": 40,
        "ai_precheck_pass_count": precheck["final_counts"].get("pass", 0),
        "ai_precheck_block_candidate_count": precheck["final_counts"].get("block", 0),
        "ai_precheck_unknown_count": precheck["final_counts"].get("unknown", 0),
        "ai_repeatability_agreement": precheck["repeatability_agreement"],
        "ai_repeatability_kappa": precheck["repeatability_kappa"],
        "completed_human_reviews": 0,
        "approved_ai_candidates": 0,
        "candidate_scenario": scenario,
        "c_equals_b_reason": "AI 사전판독 후보 5건이 있으나 사람 승인 0건이므로 공식 C는 B와 동일.",
    })
    manifest["limitations"] = [
        "접근부 좌표는 공공 횡단보도 길이와 인접 OSM 자동차도로 방향에서 추정한 미검수 지오메트리다.",
        "공공 접근성 값은 자산 단위이며 양단 접근부의 확인값이 아니다.",
        "OSM 중심선은 실제 보도 그래프가 아닌 기술 대체망이다.",
        "로드뷰 80건은 AI 사전판독에 사용했지만 사람 1차/2차 검수는 0건이다.",
        "카카오 로드뷰 이미지는 수동 판독 참고용이며 패키지에 재배포하지 않는다.",
        "AI 후보는 사람이 승인하기 전 공식 C 경로를 변경하지 않는다.",
    ]
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


def update_readme(precheck: dict, scenario: dict) -> None:
    text = f"""# ON:WAY 안양 대표 회랑 MVP 데이터 패키지

기준일: {AS_OF}  
대상: 안양역–안양청년1번가–안양1동 남부 생활권(분석 중심선 약 1.38km)

## 현재 완성된 범위

- 안양1동 횡단보도 40건, 양단 접근부 80개 생성
- 접근부별 최근 카카오 로드뷰 촬영점 80/80개 확보(이미지는 판독 참고용, 패키지 미포함)
- AI 사전판독 1차 80개 및 지정 접근부 반복판독 40개 완료
- 최종 AI 사전판독: pass {precheck['final_counts'].get('pass', 0)} / block 후보 {precheck['final_counts'].get('block', 0)} / unknown {precheck['final_counts'].get('unknown', 0)}
- AI 반복판독 단순일치율 {precheck['repeatability_agreement'] * 100:.1f}%, Cohen's κ {precheck['repeatability_kappa']:.2f}
- 사람 검수 및 사람 승인: 0건. 따라서 공식 C 경로는 B와 동일
- 동일 출발·도착 10쌍 A/B/C 30개 경로행 유지; A 대비 B 5개 경로 변경, 최대 물리거리 증분 0.60%
- C* 스트레스테스트: block 후보 5개를 모두 승인했다고 가정했을 때 B 대비 {scenario['routes_changed_vs_b']}/10 경로 변경(공식 C 아님)

## 판독 규칙

- `pass`: 낮춤/무단차, 점자블록, 통행공간이 모두 영상에서 선명하게 확인됨
- `block`: 물리적 차단 또는 점자블록 부재가 선명하게 보이는 후보
- `unknown`: 착지부 가림, 카메라 직하부, 또는 추정 지오메트리와 실제 횡단부 불일치
- AI 두 번째 판독과 불일치하면 최종 AI 결과를 자동으로 `unknown`으로 내림
- AI 사전판독은 사람 2인의 독립 검수를 대체하지 않으며 `ai_human_approved`는 비워 둠

## A/B/C 정의

- A: OSM 중심선 대체망에서 거리만 최소화
- B: 공공데이터 명시 위험 엣지 차단 + 공란 횡단보도 연결 대체엣지 1.15배 가중
- C: B + 사람 승인 AI 후보 차단. 현재 승인 0건이므로 B와 동일
- C*: AI block 후보 5건을 모두 승인했다고 가정한 비공식 민감도 분석. 실제 경로안내 사용 금지

## 핵심 파일

- `ai_precheck_80.csv`: 80개 AI 1차, 지정 40개 AI 반복판독, 보수적 최종 AI 사전판독
- `approaches_80_review_queue.csv`: 사람 검수 입력란을 비워 둔 공식 검수 대장
- `route_comparison_10od_abc.csv`: 공식 A/B/C 기준선
- `route_comparison_ai_candidate_scenario.csv`: 미승인 후보 전부 승인 가정 C* 스트레스테스트
- `roadview_evidence/approaches/approach_view_metadata.csv`: 접근부별 촬영일·촬영점 거리·링크 메타데이터
- `selected_crosswalks_40.csv`, `edge_mapping_40.csv`, `onway_anyang_corridor_mvp.geojson`, `run_manifest.json`

## 다음 실행 순서

1. 팀원 1이 `ai_precheck_80.csv`와 로드뷰 링크를 참고해 80개를 사람 1차 판독한다.
2. 다른 팀원이 지정된 40개를 AI 결과와 1차 사람 결과를 보지 않고 독립 판독한다.
3. 불일치를 조정하고 AI 후보의 사람 승인 여부를 기록한다.
4. 승인 후보만 공식 C 경로에 반영한다.

## 출처·한계

- 안양시 횡단보도 공공데이터: https://www.data.go.kr/data/15042415/fileData.do
- OpenStreetMap: https://www.openstreetmap.org/copyright (© OpenStreetMap contributors, ODbL)
- 접근부 좌표는 추정값이고 OSM 도로 중심선은 실제 보도 그래프가 아니다.
- 로드뷰 이미지는 수동 판독 참고용이며 저장·학습·재배포 권리는 별도 검토가 필요하다.
"""
    (DATA_DIR / "README.md").write_text(text, encoding="utf-8")


def main() -> None:
    results, precheck = build_results()
    write_csv(RESULT_PATH, results)
    update_queue(results)
    scenario_rows, scenario = build_candidate_scenario(results)
    write_csv(SCENARIO_PATH, scenario_rows)
    update_manifest(precheck, scenario)
    update_readme(precheck, scenario)
    print(json.dumps({"precheck": precheck, "scenario": scenario}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
