"use strict";

import { apiErrorMessage, authFetch, initAuthControls } from "./auth.js";

const settingsLoading = document.querySelector("#settings-loading");
const settingsForm = document.querySelector("#settings-form");
const runtimeStatus = document.querySelector(".runtime-status");
const runtimeStatusText = document.querySelector("#runtime-status-text");

// Fields
const ollamaBaseUrlInput = document.querySelector("#ollama-base-url");
const ollamaModelInput = document.querySelector("#ollama-model");
const ollamaEmbeddingModelInput = document.querySelector("#ollama-embedding-model");
const systemPromptInput = document.querySelector("#system-prompt");

const n8nUrlInput = document.querySelector("#n8n-url");
const n8nTokenInput = document.querySelector("#n8n-token");

const emailEnabledInput = document.querySelector("#email-enabled");
const emailSmtpFields = document.querySelector("#email-smtp-fields");
const emailSmtpHostInput = document.querySelector("#email-smtp-host");
const emailSmtpPortInput = document.querySelector("#email-smtp-port");
const emailSmtpUsernameInput = document.querySelector("#email-smtp-username");
const emailSmtpPasswordInput = document.querySelector("#email-smtp-password");
const emailUseTlsInput = document.querySelector("#email-use-tls");
const emailSenderInput = document.querySelector("#email-sender");
const emailRecipientInput = document.querySelector("#email-recipient");

// Advanced email fields
const emailProviderModeSelect = document.querySelector("#email-provider-mode");
const emailDailySummaryTimeInput = document.querySelector("#email-daily-summary-time");
const emailOnApprovalInput = document.querySelector("#email-on-approval");
const emailOnCompletedInput = document.querySelector("#email-on-completed");
const emailOnFailedInput = document.querySelector("#email-on-failed");
const emailOnDailyInput = document.querySelector("#email-on-daily");

const testEmailBtn = document.querySelector("#test-email-btn");
const sendSummaryBtn = document.querySelector("#send-summary-btn");

// Policy items
const policyToolSummary = document.querySelector("#policy-tool-summary");
const policyScopesList = document.querySelector("#policy-scopes-list");
const policyWorkspacesList = document.querySelector("#policy-workspaces-list");
const runtimeEnv = document.querySelector("#runtime-env");
const runtimeVer = document.querySelector("#runtime-ver");

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

function showToast(message, isError = false) {
  const toast = document.createElement("div");
  toast.className = "toast-notification" + (isError ? " error" : "");
  toast.textContent = message;
  document.body.appendChild(toast);
  setTimeout(() => {
    toast.remove();
  }, 4000);
}

function toggleSmtpFields() {
  if (emailEnabledInput.checked) {
    emailSmtpFields.style.display = "block";
  } else {
    emailSmtpFields.style.display = "none";
  }
}

emailEnabledInput.addEventListener("change", toggleSmtpFields);

async function loadSettings() {
  try {
    const response = await authFetch("/api/v1/settings");
    if (!response.ok) {
      throw new Error(apiErrorMessage(response, "Sikertelen betöltés"));
    }
    const settings = await response.json();

    // Populate Ollama fields
    ollamaBaseUrlInput.value = settings.ollama_base_url;
    ollamaModelInput.value = settings.ollama_model;
    ollamaEmbeddingModelInput.value = settings.ollama_embedding_model;
    systemPromptInput.value = settings.system_prompt;

    // Populate n8n fields
    n8nUrlInput.value = settings.n8n_url || "";
    if (settings.n8n_token_configured) {
      n8nTokenInput.placeholder = "Változatlan (már konfigurálva)";
      n8nTokenInput.value = "";
      n8nTokenInput.dataset.configured = "true";
    } else {
      n8nTokenInput.placeholder = "token";
      n8nTokenInput.value = "";
      n8nTokenInput.dataset.configured = "false";
    }

    // Populate Email fields
    emailEnabledInput.checked = settings.email_notifications_enabled;
    emailSmtpHostInput.value = settings.email_smtp_host || "";
    emailSmtpPortInput.value = settings.email_smtp_port || 1025;
    emailSmtpUsernameInput.value = settings.email_smtp_username || "";
    if (settings.email_smtp_password_configured) {
      emailSmtpPasswordInput.placeholder = "Változatlan (már konfigurálva)";
      emailSmtpPasswordInput.value = "";
      emailSmtpPasswordInput.dataset.configured = "true";
    } else {
      emailSmtpPasswordInput.placeholder = "jelszó";
      emailSmtpPasswordInput.value = "";
      emailSmtpPasswordInput.dataset.configured = "false";
    }
    emailUseTlsInput.checked = settings.email_smtp_use_tls;
    emailSenderInput.value = settings.email_sender || "";
    emailRecipientInput.value = settings.email_recipient || "";

    // Advanced email fields
    emailProviderModeSelect.value = settings.email_provider_mode || "smtp";
    emailDailySummaryTimeInput.value = settings.email_daily_summary_time || "18:00";
    emailOnApprovalInput.checked = settings.email_on_approval_required !== false;
    emailOnCompletedInput.checked = settings.email_on_run_completed !== false;
    emailOnFailedInput.checked = settings.email_on_run_failed !== false;
    emailOnDailyInput.checked = settings.email_on_daily_summary !== false;

    // Toggle SMTP subfields display
    toggleSmtpFields();

    // Safety & policy summaries
    policyToolSummary.textContent = settings.tool_policy_summary;

    policyScopesList.innerHTML = settings.allowed_scopes.map(
      scope => `<span class="scope-tag">${scope}</span>`
    ).join("");

    if (settings.workspace_ids.length > 0) {
      policyWorkspacesList.innerHTML = settings.workspace_ids.map(
        ws => `<span class="workspace-tag">${ws}</span>`
      ).join("");
    } else {
      policyWorkspacesList.innerHTML = `<span class="policy-desc" style="color: #70827c; font-style: italic;">Nincs engedélyezett munkaterület (üres)</span>`;
    }

    // Version/env summary
    runtimeVer.textContent = settings.app_version || "v1.0";
    
    // Fetch environment from root
    try {
      const rootRes = await fetch("/");
      if (rootRes.ok) {
        const rootData = await rootRes.json();
        runtimeEnv.textContent = rootData.environment || "development";
      }
    } catch {
      runtimeEnv.textContent = "development";
    }

    // Show form
    settingsLoading.style.display = "none";
    settingsForm.style.display = "grid";
  } catch (error) {
    settingsLoading.textContent = `Hiba a beállítások betöltésekor: ${error.message}`;
    settingsLoading.classList.add("error-banner");
  }
}

settingsForm.addEventListener("submit", async (e) => {
  e.preventDefault();

  const promptVal = systemPromptInput.value.trim();
  if (promptVal.length === 0) {
    showToast("A rendszer prompt nem lehet üres!", true);
    return;
  }

  const portVal = parseInt(emailSmtpPortInput.value, 10);
  if (isNaN(portVal) || portVal < 1 || portVal > 65535) {
    showToast("Az SMTP portnak 1 és 65535 között kell lennie!", true);
    return;
  }

  const dailyTimeVal = emailDailySummaryTimeInput.value.trim();
  if (!/^(0[0-9]|1[0-9]|2[0-3]):[0-5][0-9]$/.test(dailyTimeVal)) {
    showToast("A napi összefoglaló idejének HH:MM formátumban kell lennie (pl. 18:00)!", true);
    return;
  }

  // Construct request payload
  const payload = {
    ollama_base_url: ollamaBaseUrlInput.value.trim(),
    ollama_model: ollamaModelInput.value.trim(),
    ollama_embedding_model: ollamaEmbeddingModelInput.value.trim(),
    system_prompt: promptVal,
    n8n_url: n8nUrlInput.value.trim() || null,
    email_notifications_enabled: emailEnabledInput.checked,
    email_smtp_host: emailSmtpHostInput.value.trim() || "localhost",
    email_smtp_port: portVal,
    email_smtp_username: emailSmtpUsernameInput.value.trim() || null,
    email_smtp_use_tls: emailUseTlsInput.checked,
    email_sender: emailSenderInput.value.trim() || "kelvin@localhost",
    email_recipient: emailRecipientInput.value.trim() || null,
    email_provider_mode: emailProviderModeSelect.value,
    email_daily_summary_time: dailyTimeVal,
    email_on_approval_required: emailOnApprovalInput.checked,
    email_on_run_completed: emailOnCompletedInput.checked,
    email_on_run_failed: emailOnFailedInput.checked,
    email_on_daily_summary: emailOnDailyInput.checked
  };

  // Handle secrets
  const tokenVal = n8nTokenInput.value;
  if (tokenVal === "") {
    if (n8nTokenInput.dataset.configured === "true") {
      payload.n8n_token = "keep";
    } else {
      payload.n8n_token = ""; // empty
    }
  } else {
    payload.n8n_token = tokenVal;
  }

  const passVal = emailSmtpPasswordInput.value;
  if (passVal === "") {
    if (emailSmtpPasswordInput.dataset.configured === "true") {
      payload.email_smtp_password = "keep";
    } else {
      payload.email_smtp_password = ""; // empty
    }
  } else {
    payload.email_smtp_password = passVal;
  }

  const saveBtn = document.querySelector("#save-settings-btn");
  saveBtn.disabled = true;
  saveBtn.textContent = "Mentés…";

  try {
    const response = await authFetch("/api/v1/settings", {
      method: "PUT",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify(payload)
    });

    if (!response.ok) {
      const errData = await response.json();
      throw new Error(
        apiErrorMessage(response, errData.detail || "Sikertelen frissítés"),
      );
    }

    showToast("A beállítások sikeresen elmentve!");
    
    // Reload form to update placeholders/configured attributes
    await loadSettings();
  } catch (error) {
    showToast(`Hiba a mentés során: ${error.message}`, true);
  } finally {
    saveBtn.disabled = false;
    saveBtn.textContent = "Módosítások mentése";
  }
});

// Test Email button listener
testEmailBtn.addEventListener("click", async () => {
  if (!emailEnabledInput.checked) {
    showToast("Kérjük, előbb engedélyezze és mentse el a beállításokat a teszt küldéséhez!", true);
    return;
  }

  testEmailBtn.disabled = true;
  const originalText = testEmailBtn.textContent;
  testEmailBtn.textContent = "Küldés…";

  try {
    const response = await authFetch("/api/v1/settings/test-email", {
      method: "POST"
    });
    if (!response.ok) {
      const errData = await response.json();
      throw new Error(
        apiErrorMessage(response, errData.detail || "Sikertelen kapcsolódás"),
      );
    }
    showToast("Teszt e-mail sikeresen elküldve a megadott címzettnek!");
  } catch (error) {
    showToast(`Hiba a küldés során: ${error.message}`, true);
  } finally {
    testEmailBtn.disabled = false;
    testEmailBtn.textContent = originalText;
  }
});

// Daily Summary button listener
sendSummaryBtn.addEventListener("click", async () => {
  if (!emailEnabledInput.checked) {
    showToast("Kérjük, előbb engedélyezze és mentse el a beállításokat az összefoglaló küldéséhez!", true);
    return;
  }

  sendSummaryBtn.disabled = true;
  const originalText = sendSummaryBtn.textContent;
  sendSummaryBtn.textContent = "Küldés…";

  try {
    const response = await authFetch("/api/v1/settings/send-summary", {
      method: "POST"
    });
    if (!response.ok) {
      const errData = await response.json();
      throw new Error(
        apiErrorMessage(response, errData.detail || "Sikertelen küldés"),
      );
    }
    showToast("Napi összefoglaló sikeresen elküldve a megadott címzettnek!");
  } catch (error) {
    showToast(`Hiba a küldés során: ${error.message}`, true);
  } finally {
    sendSummaryBtn.disabled = false;
    sendSummaryBtn.textContent = originalText;
  }
});

// Initial load
initAuthControls();
void checkRuntime();
void loadSettings();
