"use strict";

import { apiErrorMessage, authFetch, initAuthControls } from "./auth.js";

const approvalsList = document.querySelector("#approvals-list");
const approvalDetail = document.querySelector("#approval-detail");
const runtimeStatus = document.querySelector(".runtime-status");
const runtimeStatusText = document.querySelector("#runtime-status-text");

let pendingRuns = [];
let selectedRunId = null;
let pollInterval = null;

function setRuntimeStatus(state, label) {
  runtimeStatus.dataset.state = state;
  runtimeStatusText.textContent = label;
}

async function checkRuntime() {
  setRuntimeStatus("checking", "Kapcsolódás…");
  try {
    const [healthResponse, readyResponse] = await Promise.all([
      fetch("/health"),
      fetch("/ready")
    ]);
    if (!healthResponse.ok || !readyResponse.ok) {
      throw new Error("Runtime unavailable");
    }
    const readiness = await readyResponse.json();
    setRuntimeStatus("ready", `${readiness.model} · elérhető`);
  } catch {
    setRuntimeStatus("error", "A modell nem érhető el");
  }
}

function formatTime(isoString) {
  if (!isoString) return "-";
  try {
    const date = new Date(isoString);
    return date.toLocaleString("hu-HU", {
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit"
    });
  } catch {
    return isoString;
  }
}

async function fetchPendingApprovals() {
  try {
    const response = await authFetch("/api/v1/agent/runs");
    if (!response.ok) {
      throw new Error(apiErrorMessage(response, "Sikertelen betöltés"));
    }
    const allRuns = await response.json();
    pendingRuns = allRuns.filter(run => run.status === "awaiting_approval");
    renderApprovalsList();
    if (selectedRunId) {
      // If the selected run is no longer awaiting approval, clear detail view
      if (!pendingRuns.some(run => run.id === selectedRunId)) {
        selectedRunId = null;
        renderEmptyState();
      } else {
        await fetchApprovalDetails(selectedRunId, true);
      }
    }
  } catch (error) {
    approvalsList.innerHTML = `<div class="error-banner">Hiba: ${error.message}</div>`;
  }
}

function renderEmptyState() {
  approvalDetail.innerHTML = `
    <div class="empty-state">
      <span class="empty-icon">✓</span>
      <p>Nincs függőben lévő jóváhagyási kérés</p>
    </div>
  `;
}

function renderApprovalsList() {
  if (pendingRuns.length === 0) {
    approvalsList.innerHTML = `<div class="empty-state" style="padding-top: 2rem;">Nincs várakozó jóváhagyás.</div>`;
    return;
  }

  approvalsList.innerHTML = "";
  pendingRuns.forEach(run => {
    const card = document.createElement("div");
    card.className = `run-card approval-card ${run.id === selectedRunId ? "selected" : ""}`;
    card.dataset.id = run.id;

    const shortId = run.id.substring(0, 8);
    const timeLabel = formatTime(run.updated_at || run.created_at);

    card.innerHTML = `
      <div class="run-card-header">
        <span class="run-card-status status-${run.status}">Jóváhagyásra vár</span>
        <span class="run-card-time">${timeLabel}</span>
      </div>
      <p class="run-card-goal">${run.goal}</p>
      <div class="run-card-footer">
        <span>#${shortId}</span>
        <span>Lépés: ${run.step_count} / ${run.max_steps}</span>
      </div>
    `;

    card.addEventListener("click", () => {
      document.querySelectorAll(".run-card").forEach(c => c.classList.remove("selected"));
      card.classList.add("selected");
      void fetchApprovalDetails(run.id);
    });

    approvalsList.appendChild(card);
  });
}

async function fetchApprovalDetails(runId, silent = false) {
  selectedRunId = runId;
  if (!silent) {
    approvalDetail.innerHTML = `<div class="loading-state">Javaslat betöltése…</div>`;
  }

  try {
    const response = await authFetch(`/api/v1/agent/runs/${runId}/tools/active`);
    if (!response.ok) {
      throw new Error(
        apiErrorMessage(response, "Nem sikerült betölteni az aktív javaslatot"),
      );
    }
    const proposal = await response.json();
    
    if (selectedRunId !== runId) return;

    renderApprovalDetails(proposal);
  } catch (error) {
    approvalDetail.innerHTML = `<div class="error-banner">Hiba: ${error.message}</div>`;
  }
}

function renderApprovalDetails(proposal) {
  const run = proposal.run;
  const isHighRisk = proposal.risk === "destructive" || proposal.risk === "privileged";
  const timeCreated = formatTime(run.created_at);

  let warningBoxHtml = "";
  if (isHighRisk) {
    warningBoxHtml = `
      <div class="approval-warning-box">
        <p>⚠️ <strong>Figyelem:</strong> Ez egy kiemelt kockázatú művelet (${proposal.risk.toUpperCase()}). Kérlek, alaposan ellenőrizd az argumentumokat a végrehajtás engedélyezése előtt!</p>
        <label class="approval-confirm-label">
          <input type="checkbox" id="confirm-high-risk-checkbox">
          <span>Megértettem a kockázatot, engedélyezni akarom a végrehajtást</span>
        </label>
      </div>
    `;
  }

  approvalDetail.innerHTML = `
    <div class="detail-header">
      <div class="detail-title-row">
        <h2>${run.goal}</h2>
      </div>
      <div class="detail-metadata">
        <div class="metadata-item"><strong>Futás ID:</strong> ${run.id}</div>
        <div class="metadata-item"><strong>Lépés:</strong> ${run.step_count} / ${run.max_steps}</div>
        <div class="metadata-item"><strong>Kezdve:</strong> ${timeCreated}</div>
      </div>
    </div>

    <div class="detail-section-title">Függőben lévő eszközhívás javaslat</div>
    
    <div class="timeline-step">
      <div class="step-header">
        <span class="step-tool">${proposal.tool_name}</span>
        <div class="step-badges">
          <span class="badge badge-risk-${proposal.risk}">Kockázat: ${proposal.risk}</span>
          <span class="badge">${proposal.policy_decision}</span>
        </div>
      </div>
      <div class="step-body">
        <div class="step-desc"><strong>Cél / Indoklás:</strong> ${proposal.reason}</div>
        ${proposal.expected_effect ? `<div class="step-desc"><strong>Elvárt hatás:</strong> ${proposal.expected_effect}</div>` : ""}
        
        <div class="step-details-grid">
          <div class="step-details-item step-args" style="grid-column: 1 / -1;">
            <h4>Javasolt Argumentumok</h4>
            <pre><code>${JSON.stringify(proposal.arguments, null, 2)}</code></pre>
          </div>
        </div>

        <div class="step-details-grid" style="margin-top: 1rem;">
          <div class="step-details-item" style="grid-column: 1 / -1;">
            <h4>Szabályzati ellenőrzés részletei</h4>
            <p>${proposal.policy_reason}</p>
          </div>
        </div>

        ${warningBoxHtml}

        <div style="margin-top: 1.5rem; display: flex; gap: 1rem;">
          <button id="approve-btn" class="approve-button" ${isHighRisk ? "disabled" : ""}>
            Jóváhagyás (Engedélyezés)
          </button>
          <button id="reject-btn" class="cancel-button">
            Elutasítás (Megszakítás)
          </button>
        </div>
      </div>
    </div>
  `;

  const approveBtn = document.querySelector("#approve-btn");
  const rejectBtn = document.querySelector("#reject-btn");
  const confirmCheckbox = document.querySelector("#confirm-high-risk-checkbox");

  if (isHighRisk && confirmCheckbox && approveBtn) {
    confirmCheckbox.addEventListener("change", (e) => {
      approveBtn.disabled = !e.target.checked;
    });
  }

  if (approveBtn) {
    approveBtn.addEventListener("click", () => {
      void resolveApproval(run.id, proposal.tool_call_id, "approved");
    });
  }

  if (rejectBtn) {
    rejectBtn.addEventListener("click", () => {
      void resolveApproval(run.id, proposal.tool_call_id, "rejected");
    });
  }
}

async function resolveApproval(runId, toolCallId, decision) {
  const approveBtn = document.querySelector("#approve-btn");
  const rejectBtn = document.querySelector("#reject-btn");
  
  if (approveBtn) approveBtn.disabled = true;
  if (rejectBtn) rejectBtn.disabled = true;

  try {
    const response = await authFetch(`/api/v1/agent/runs/${runId}/approval`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        tool_call_id: toolCallId,
        decision: decision
      })
    });

    if (!response.ok) {
      throw new Error(
        apiErrorMessage(response, "Nem sikerült elküldeni a döntést az API-nak"),
      );
    }

    // Refresh list and clear detail
    await fetchPendingApprovals();
  } catch (error) {
    alert(error.message);
    if (approveBtn && !(decision === "approved" && document.querySelector("#confirm-high-risk-checkbox")?.checked === false)) {
      approveBtn.disabled = false;
    }
    if (rejectBtn) rejectBtn.disabled = false;
  }
}

// Initial load
initAuthControls();
void checkRuntime();
void fetchPendingApprovals();

// Poll pending list every 4 seconds
pollInterval = setInterval(fetchPendingApprovals, 4000);

window.addEventListener("unload", () => {
  if (pollInterval) clearInterval(pollInterval);
});
