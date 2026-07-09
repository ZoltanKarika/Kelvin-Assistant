"use strict";

import { apiErrorMessage, authFetch, initAuthControls } from "./auth.js";

const n8nStatusBadge = document.querySelector("#n8n-status-badge");
const n8nBaseUrl = document.querySelector("#n8n-base-url");
const n8nLastChecked = document.querySelector("#n8n-last-checked");
const n8nErrorBox = document.querySelector("#n8n-error-box");
const n8nErrorMsg = document.querySelector("#n8n-error-msg");
const refreshN8NBtn = document.querySelector("#refresh-n8n-btn");
const runtimeStatus = document.querySelector(".runtime-status");
const runtimeStatusText = document.querySelector("#runtime-status-text");

// Workflows status elements
const wfApprovalStatus = document.querySelector("#wf-approval-status");
const wfRunStatus = document.querySelector("#wf-run-status");
const wfDailyStatus = document.querySelector("#wf-daily-status");

function setRuntimeStatus(state, label) {
  runtimeStatus.dataset.state = state;
  runtimeStatusText.textContent = label;
}

async function checkRuntime() {
  setRuntimeStatus("checking", "Kapcsolódás…");
  try {
    const [healthResponse, readyResponse] = await Promise.all([
      fetch("/health"),
      authFetch("/ready")
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
      year: "numeric",
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

async function fetchN8NHealth() {
  n8nStatusBadge.className = "run-card-status status-observing";
  n8nStatusBadge.textContent = "Ellenőrzés…";
  n8nErrorBox.style.display = "none";

  try {
    const response = await authFetch("/api/v1/n8n/health");
    if (!response.ok) {
      throw new Error(apiErrorMessage(response, "Sikertelen API lekérdezés"));
    }
    const data = await response.json();

    // Render Last Checked
    n8nLastChecked.textContent = formatTime(data.last_checked);
    n8nBaseUrl.textContent = data.base_url || "Nincs megadva";

    // Set badges and workflows status
    if (data.status === "healthy") {
      n8nStatusBadge.className = "run-card-status status-completed";
      n8nStatusBadge.textContent = "Kapcsolódva";
      
      updateWorkflowsStatus("Elérhető", "active");
    } else if (data.status === "degraded") {
      n8nStatusBadge.className = "run-card-status status-observing";
      n8nStatusBadge.textContent = "Degradált";
      
      updateWorkflowsStatus("Degradált", "inactive");
      showError(data.error_message);
    } else if (data.status === "unreachable") {
      n8nStatusBadge.className = "run-card-status status-failed";
      n8nStatusBadge.textContent = "Nem elérhető";
      
      updateWorkflowsStatus("Inaktív", "inactive");
      showError(data.error_message);
    } else if (data.status === "unconfigured") {
      n8nStatusBadge.className = "run-card-status status-cancelled";
      n8nStatusBadge.textContent = "Nincs konfigurálva";
      
      updateWorkflowsStatus("Nincs konfigurálva", "inactive");
    }
  } catch (error) {
    n8nStatusBadge.className = "run-card-status status-failed";
    n8nStatusBadge.textContent = "Hiba";
    showError(error.message);
    updateWorkflowsStatus("Hiba", "inactive");
  }
}

function updateWorkflowsStatus(text, statusClass) {
  [wfApprovalStatus, wfRunStatus, wfDailyStatus].forEach(el => {
    el.textContent = text;
    el.className = `wf-status ${statusClass}`;
  });
}

function showError(msg) {
  n8nErrorMsg.textContent = msg || "Ismeretlen hálózati vagy kiszolgáló oldali hiba.";
  n8nErrorBox.style.display = "block";
}

refreshN8NBtn.addEventListener("click", () => {
  void fetchN8NHealth();
});

// Initial load
initAuthControls();
void checkRuntime();
void fetchN8NHealth();
