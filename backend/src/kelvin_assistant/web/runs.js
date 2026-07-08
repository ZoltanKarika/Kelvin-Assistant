"use strict";

const runsList = document.querySelector("#runs-list");
const runDetail = document.querySelector("#run-detail");
const filterButtons = document.querySelectorAll(".filter-btn");
const runtimeStatus = document.querySelector(".runtime-status");
const runtimeStatusText = document.querySelector("#runtime-status-text");

let allRuns = [];
let activeFilter = "all";
let selectedRunId = null;
let pollInterval = null;

const ACTIVE_STATUSES = [
  "received",
  "clarifying",
  "planning",
  "awaiting_approval",
  "executing",
  "observing"
];

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

function getStatusLabel(status) {
  const labels = {
    received: "Fogadva",
    clarifying: "Pontosítás",
    planning: "Tervezés",
    awaiting_approval: "Jóváhagyásra vár",
    executing: "Végrehajtás",
    observing: "Megfigyelés",
    completed: "Kész",
    cancelled: "Megszakítva",
    failed: "Hiba"
  };
  return labels[status] ?? status;
}

async function fetchRuns() {
  try {
    const response = await fetch("/api/v1/agent/runs");
    if (!response.ok) {
      throw new Error("Sikertelen betöltés");
    }
    allRuns = await response.json();
    renderRunsList();
    if (selectedRunId) {
      // Refresh details of selected run silently
      await fetchRunDetails(selectedRunId, true);
    }
  } catch (error) {
    runsList.innerHTML = `<div class="error-banner">Hiba a futások betöltésekor: ${error.message}</div>`;
  }
}

function renderRunsList() {
  const filtered = allRuns.filter(run => {
    if (activeFilter === "all") return true;
    if (activeFilter === "active") return ACTIVE_STATUSES.includes(run.status);
    return run.status === activeFilter;
  });

  if (filtered.length === 0) {
    runsList.innerHTML = `<div class="empty-state" style="padding-top: 2rem;">Nincsenek futások ebben a kategóriában.</div>`;
    return;
  }

  runsList.innerHTML = "";
  filtered.forEach(run => {
    const card = document.createElement("div");
    card.className = `run-card ${run.id === selectedRunId ? "selected" : ""}`;
    card.dataset.id = run.id;

    const shortId = run.id.substring(0, 8);
    const timeLabel = formatTime(run.updated_at || run.created_at);

    card.innerHTML = `
      <div class="run-card-header">
        <span class="run-card-status status-${run.status}">${getStatusLabel(run.status)}</span>
        <span class="run-card-time">${timeLabel}</span>
      </div>
      <p class="run-card-goal">${run.goal}</p>
      <div class="run-card-footer">
        <span>#${shortId}</span>
        <div class="run-card-steps">
          <span>Lépés: ${run.step_count} / ${run.max_steps}</span>
        </div>
      </div>
    `;

    card.addEventListener("click", () => {
      document.querySelectorAll(".run-card").forEach(c => c.classList.remove("selected"));
      card.classList.add("selected");
      void fetchRunDetails(run.id);
    });

    runsList.appendChild(card);
  });
}

async function fetchRunDetails(runId, silent = false) {
  selectedRunId = runId;
  if (!silent) {
    runDetail.innerHTML = `<div class="loading-state">Részletek betöltése…</div>`;
  }

  try {
    const response = await fetch(`/api/v1/agent/runs/${runId}`);
    if (!response.ok) {
      throw new Error("Nem sikerült lekérni a részleteket");
    }
    const run = await response.json();
    
    // Safety check to avoid rendering outdated fetch
    if (selectedRunId !== runId) return;

    renderRunDetails(run);
  } catch (error) {
    runDetail.innerHTML = `<div class="error-banner">Hiba: ${error.message}</div>`;
  }
}

function renderRunDetails(run) {
  const isCancelable = ACTIVE_STATUSES.includes(run.status);
  const timeCreated = formatTime(run.created_at);
  const timeUpdated = formatTime(run.updated_at);

  let stepsHtml = "";
  if (run.steps.length === 0) {
    stepsHtml = `<p class="empty-state" style="padding-top: 1rem;">Még nincsenek végrehajtott lépések.</p>`;
  } else {
    stepsHtml = `
      <div class="timeline">
        ${run.steps.map((step, index) => {
          const hasResult = step.succeeded !== null;
          const resultClass = step.succeeded ? "result-success" : "result-failure";
          const resultLabel = step.succeeded ? "Sikeres" : "Sikertelen";
          
          let resultSection = "";
          if (hasResult) {
            resultSection = `
              <div class="step-result">
                <div class="result-header ${resultClass}">
                  <span>${step.succeeded ? "✓" : "✗"}</span>
                  <span>${resultLabel} (${step.duration_ms} ms)</span>
                </div>
                ${step.output ? `<pre class="result-output">${step.output}</pre>` : ""}
                ${step.error ? `<pre class="result-error">${step.error}</pre>` : ""}
              </div>
            `;
          }

          return `
            <div class="timeline-step ${hasResult ? (step.succeeded ? "completed" : "failed") : ""}">
              <div class="step-header">
                <span class="step-tool">${step.tool_name}</span>
                <div class="step-badges">
                  <span class="badge badge-risk-${step.risk}">Risk: ${step.risk}</span>
                  <span class="badge">${step.policy_decision}</span>
                  ${step.approval_status ? `<span class="badge">${step.approval_status}</span>` : ""}
                </div>
              </div>
              <div class="step-body">
                <div class="step-desc"><strong>Cél/Indok:</strong> ${step.reason}</div>
                ${step.expected_effect ? `<div class="step-desc"><strong>Elvárt hatás:</strong> ${step.expected_effect}</div>` : ""}
                
                <div class="step-details-grid">
                  <div class="step-details-item step-args">
                    <h4>Argumentumok</h4>
                    <pre><code>${JSON.stringify(step.arguments, null, 2)}</code></pre>
                  </div>
                  <div class="step-details-item">
                    <h4>Szabályzat döntés</h4>
                    <p>${step.policy_reason}</p>
                  </div>
                </div>
                ${resultSection}
              </div>
            </div>
          `;
        }).join("")}
      </div>
    `;
  }

  runDetail.innerHTML = `
    <div class="detail-header">
      <div class="detail-title-row">
        <h2>${run.goal}</h2>
        <button id="cancel-btn" class="cancel-button" ${isCancelable ? "" : "disabled"}>
          Megszakítás
        </button>
      </div>
      <div class="detail-metadata">
        <div class="metadata-item"><strong>Azonosító:</strong> ${run.id}</div>
        <div class="metadata-item"><strong>Státusz:</strong> <span class="run-card-status status-${run.status}">${getStatusLabel(run.status)}</span></div>
        <div class="metadata-item"><strong>Lépések:</strong> ${run.step_count} / ${run.max_steps}</div>
        <div class="metadata-item"><strong>Létrehozva:</strong> ${timeCreated}</div>
        <div class="metadata-item"><strong>Módosítva:</strong> ${timeUpdated}</div>
        ${run.workspace_id ? `<div class="metadata-item"><strong>Munkakörnyezet:</strong> ${run.workspace_id}</div>` : ""}
      </div>
    </div>
    
    <div class="detail-section-title">Végrehajtási idővonal</div>
    ${stepsHtml}
  `;

  const cancelBtn = document.querySelector("#cancel-btn");
  if (cancelBtn && isCancelable) {
    cancelBtn.addEventListener("click", async () => {
      if (!confirm("Biztosan meg akarod szakítani ezt a futást?")) return;
      cancelBtn.disabled = true;
      cancelBtn.textContent = "Megszakítás folyamatban…";
      try {
        const response = await fetch(`/api/v1/agent/runs/${run.id}/cancel`, {
          method: "POST"
        });
        if (!response.ok) {
          throw new Error("Nem sikerült megszakítani a futást");
        }
        await fetchRuns();
      } catch (error) {
        alert(error.message);
        cancelBtn.disabled = false;
        cancelBtn.textContent = "Megszakítás";
      }
    });
  }
}

// Set up filter buttons
filterButtons.forEach(btn => {
  btn.addEventListener("click", () => {
    filterButtons.forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    activeFilter = btn.dataset.filter;
    renderRunsList();
  });
});

// Initial load
void checkRuntime();

const urlParams = new URLSearchParams(window.location.search);
const selectParam = urlParams.get("select");
if (selectParam) {
  selectedRunId = selectParam;
  void fetchRunDetails(selectParam);
}

void fetchRuns();

// Start polling to keep dashboard live
pollInterval = setInterval(fetchRuns, 4000);

// Cleanup poll on page unload
window.addEventListener("unload", () => {
  if (pollInterval) clearInterval(pollInterval);
});
