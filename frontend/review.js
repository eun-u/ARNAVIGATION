"use strict";

const labels = {
  pending: "검수 대기",
  approved: "승인",
  rejected: "기각",
  needs_more_evidence: "추가 근거 필요",
  tactile_absent_candidate: "점자블록 부재 후보",
  construction_block_candidate: "공사 차단 후보",
};
const reviewState = { candidates: [], selected: null, busy: false };
const el = (id) => document.getElementById(id);

document.addEventListener("DOMContentLoaded", () => {
  el("status-filter").addEventListener("change", loadCandidates);
  el("review-form").addEventListener("submit", (event) => { event.preventDefault(); submitReview("approved"); });
  document.querySelectorAll("[data-decision]").forEach((button) => button.addEventListener("click", () => submitReview(button.dataset.decision)));
  const now = new Date(Date.now() - new Date().getTimezoneOffset() * 60000);
  el("observed-at").value = now.toISOString().slice(0, 16);
  loadCandidates().catch(showError);
});

async function api(path, options = {}) {
  const response = await fetch(path, { headers: { "Content-Type": "application/json" }, ...options });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.message || payload.detail?.[0]?.msg || "요청을 처리하지 못했습니다.");
  return payload;
}

async function loadCandidates() {
  const status = el("status-filter").value;
  reviewState.candidates = await api(`/observations/candidates${status ? `?status=${status}` : ""}`);
  el("candidate-count").textContent = `${reviewState.candidates.length}건`;
  renderList();
  setStatus(`${labels[status] || "전체"} 후보 ${reviewState.candidates.length}건을 불러왔습니다.`, "success");
  if (reviewState.candidates.length && !reviewState.selected) selectCandidate(reviewState.candidates[0].candidate_id);
}

function renderList() {
  el("candidate-list").innerHTML = reviewState.candidates.length ? reviewState.candidates.map((item) => `
    <button class="candidate-card${reviewState.selected?.candidate_id === item.candidate_id ? " is-selected" : ""}" type="button" data-id="${escapeHtml(item.candidate_id)}" role="listitem">
      <span><strong>${escapeHtml(item.approach_id || item.sample_id || item.candidate_id)}</strong><small>${escapeHtml(labels[item.type] || item.type)}</small></span>
      <span class="candidate-score">${item.confidence == null ? "현장" : `${Math.round(item.confidence * 100)}%`}</span>
      <span class="badge badge-${item.status === "approved" ? "success" : item.status === "rejected" ? "danger" : "neutral"}">${escapeHtml(labels[item.status] || item.status)}</span>
    </button>`).join("") : '<p class="review-empty">이 상태의 후보가 없습니다.</p>';
  document.querySelectorAll(".candidate-card").forEach((button) => button.addEventListener("click", () => selectCandidate(button.dataset.id)));
}

function selectCandidate(id) {
  reviewState.selected = reviewState.candidates.find((item) => item.candidate_id === id);
  if (!reviewState.selected) return;
  const item = reviewState.selected;
  renderList();
  el("candidate-empty").hidden = true;
  el("candidate-content").hidden = false;
  el("candidate-id").textContent = item.candidate_id;
  el("candidate-type").textContent = labels[item.type] || item.type;
  el("candidate-status").textContent = labels[item.status] || item.status;
  el("candidate-status").className = `badge badge-${item.status === "approved" ? "success" : item.status === "rejected" ? "danger" : "neutral"}`;
  el("candidate-approach").textContent = item.approach_id || "미지정";
  el("candidate-edge").textContent = item.edge_id;
  el("candidate-confidence").textContent = item.confidence == null ? "사용자 현장 제보 · AI 추정값 없음" : `${Math.round(item.confidence * 100)}% · AI 후보값`;
  el("candidate-date").textContent = item.evidence_date || "미기록";
  const evidenceDate = item.evidence_date ? new Date(item.evidence_date.replace(" ", "T") + "+09:00") : null;
  const ageDays = evidenceDate && !Number.isNaN(evidenceDate.valueOf()) ? Math.floor((Date.now() - evidenceDate.valueOf()) / 86400000) : null;
  el("candidate-age").textContent = ageDays === null ? "근거 시점을 확인할 수 없습니다." : `촬영 후 ${ageDays}일 경과 · 현재 상태 재확인 필요`;
  el("candidate-note").textContent = item.ai_note || "AI 메모 없음";
  el("candidate-evidence").href = item.evidence_url || "#";
}

async function submitReview(decision) {
  if (!reviewState.selected || reviewState.busy) return;
  el("review-result").required = decision === "approved";
  if (!el("review-form").reportValidity()) return;
  const measurements = {};
  [["measure-slope", "slope"], ["measure-width", "width"], ["measure-curb", "curb_height"]].forEach(([id, key]) => {
    if (el(id).value !== "") measurements[key] = Number(el(id).value);
  });
  reviewState.busy = true;
  setStatus("검수 기록을 저장하는 중입니다.");
  try {
    const payload = {
      decision,
      result: el("review-result").value || null,
      reviewer: el("reviewer").value.trim(),
      observed_at: new Date(el("observed-at").value).toISOString(),
      reason: el("review-reason").value.trim(),
      measurements,
    };
    const result = await api(`/observations/candidates/${encodeURIComponent(reviewState.selected.candidate_id)}/review`, { method: "POST", body: JSON.stringify(payload) });
    reviewState.selected = null;
    el("review-form").reset();
    const now = new Date(Date.now() - new Date().getTimezoneOffset() * 60000);
    el("observed-at").value = now.toISOString().slice(0, 16);
    await loadCandidates();
    setStatus(result.graph_updated ? `검수 승인과 그래프 갱신이 완료됐습니다. revision ${result.graph_revision}` : "검수 기록을 저장했습니다. 그래프는 변경하지 않았습니다.", "success");
  } catch (error) { showError(error); } finally { reviewState.busy = false; }
}

function setStatus(message, tone = "info") { el("review-status").textContent = message; el("review-status").dataset.tone = tone; }
function showError(error) { console.error(error); setStatus(error.message || "오류가 발생했습니다.", "error"); }
function escapeHtml(value) { return String(value).replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#039;"); }
