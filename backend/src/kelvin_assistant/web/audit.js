"use strict";

const auditLogRows = document.querySelector("#audit-log-rows");
const filterEventType = document.querySelector("#filter-event-type");
const filterDecision = document.querySelector("#filter-decision");
const filterRunId = document.querySelector("#filter-run-id");
const filterCorrelationId = document.querySelector("#filter-correlation-id");
const resetFiltersBtn = document.querySelector("#reset-filters-btn");
const loadMoreBtn = document.querySelector("#load-more-btn");
const runtimeStatus = document.querySelector(".runtime-status");
const runtimeStatusText = document.querySelector("#runtime-status-text");

const LIMIT = 25;
let currentOffset = 0;
let debounceTimer = null;
let allEntries = [];

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

async function fetchAuditLogs(append = false) {
  if (!append) {
    currentOffset = 0;
    auditLogRows.innerHTML = `<tr><td colspan="7" class="loading-state">Napló betöltése…</td></tr>`;
  }

  // Construct query params
  const params = new URLSearchParams();
  params.append("limit", LIMIT.toString());
  params.append("offset", currentOffset.toString());

  if (filterEventType.value !== "all") {
    params.append("event_type", filterEventType.value);
  }
  if (filterDecision.value !== "all") {
    params.append("decision", filterDecision.value);
  }
  
  const runIdVal = filterRunId.value.trim();
  if (runIdVal) {
    params.append("run_id", runIdVal);
  }
  
  const corrIdVal = filterCorrelationId.value.trim();
  if (corrIdVal) {
    params.append("correlation_id", corrIdVal);
  }

  try {
    const response = await fetch(`/api/v1/security/audit?${params.toString()}`);
    if (!response.ok) {
      throw new Error("Sikertelen API lekérdezés");
    }
    const data = await response.json();

    if (append) {
      allEntries = allEntries.concat(data);
    } else {
      allEntries = data;
    }

    renderAuditTable(data, append);

    // Show/hide load more button
    if (data.length < LIMIT) {
      loadMoreBtn.style.display = "none";
    } else {
      loadMoreBtn.style.display = "block";
    }
  } catch (error) {
    auditLogRows.innerHTML = `<tr><td colspan="7" class="error-banner">Hiba a betöltéskor: ${error.message}</td></tr>`;
  }
}

function renderAuditTable(newEntries, append) {
  if (!append && allEntries.length === 0) {
    auditLogRows.innerHTML = `<tr><td colspan="7" class="empty-state" style="text-align: center; padding: 2rem;">Nincsenek naplóbejegyzések a megadott szűrőkkel.</td></tr>`;
    return;
  }

  if (!append) {
    auditLogRows.innerHTML = "";
  }

  newEntries.forEach(entry => {
    const row = document.createElement("tr");

    const timeLabel = formatTime(entry.created_at);
    
    // Status color classes
    const eventClass = entry.event_type === "input_guard" ? "status-received" : "status-observing";
    const eventLabel = entry.event_type === "input_guard" ? "Input Guard" : "Output Guard";
    
    const decisionClass = entry.decision === "allow" ? "status-completed" : "status-failed";
    const decisionLabel = entry.decision === "allow" ? "Engedélyezve" : "Blokkolva";

    const shortRunId = entry.run_id 
      ? `<a href="/ui/runs?select=${entry.run_id}" class="audit-run-link" title="${entry.run_id}">${entry.run_id.substring(0, 8)}…</a>` 
      : "-";
      
    const shortCorrId = entry.correlation_id 
      ? `<span title="${entry.correlation_id}">${entry.correlation_id.substring(0, 8)}…</span>` 
      : "-";

    const warningsHtml = entry.warnings.length > 0 
      ? entry.warnings.map(w => `<span class="warning-tag">${w}</span>`).join("")
      : '<span class="status-dot" style="background:#58d68d; display:inline-block; margin-left:0.5rem;" title="Nincs figyelmeztetés"></span>';

    row.innerHTML = `
      <td style="white-space: nowrap;">${timeLabel}</td>
      <td><span class="run-card-status ${eventClass}">${eventLabel}</span></td>
      <td><span class="run-card-status ${decisionClass}">${decisionLabel}</span></td>
      <td>${shortRunId}</td>
      <td>${shortCorrId}</td>
      <td>
        <pre class="audit-masked-content"><code>${entry.masked_content || "-"}</code></pre>
      </td>
      <td>${warningsHtml}</td>
    `;
    auditLogRows.appendChild(row);
  });
}

function handleFilterChange() {
  currentOffset = 0;
  void fetchAuditLogs(false);
}

function handleInputFilterChange() {
  if (debounceTimer) clearTimeout(debounceTimer);
  debounceTimer = setTimeout(() => {
    handleFilterChange();
  }, 400);
}

// Set up event listeners
filterEventType.addEventListener("change", handleFilterChange);
filterDecision.addEventListener("change", handleFilterChange);
filterRunId.addEventListener("input", handleInputFilterChange);
filterCorrelationId.addEventListener("input", handleInputFilterChange);

resetFiltersBtn.addEventListener("click", () => {
  filterEventType.value = "all";
  filterDecision.value = "all";
  filterRunId.value = "";
  filterCorrelationId.value = "";
  handleFilterChange();
});

loadMoreBtn.addEventListener("click", () => {
  currentOffset += LIMIT;
  void fetchAuditLogs(true);
});

// Initial load
void checkRuntime();
void fetchAuditLogs();
