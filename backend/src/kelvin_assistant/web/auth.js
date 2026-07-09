"use strict";

const TOKEN_STORAGE_KEY = "kelvin.apiToken";

function getToken() {
  return window.sessionStorage.getItem(TOKEN_STORAGE_KEY) || "";
}

function setToken(token) {
  const trimmed = token.trim();
  if (trimmed) {
    window.sessionStorage.setItem(TOKEN_STORAGE_KEY, trimmed);
  } else {
    window.sessionStorage.removeItem(TOKEN_STORAGE_KEY);
  }
}

function hasToken() {
  return Boolean(getToken());
}

function updateAuthButton(button) {
  button.textContent = hasToken() ? "API token: set" : "API token";
  button.dataset.state = hasToken() ? "set" : "missing";
}

function promptForToken(button) {
  const current = hasToken() ? "configured" : "not configured";
  const token = window.prompt(
    `Kelvin operator API token (${current}). Leave empty to clear it.`,
    "",
  );
  if (token === null) {
    return;
  }
  setToken(token);
  updateAuthButton(button);
  window.dispatchEvent(new CustomEvent("kelvin-auth-changed"));
}

export function initAuthControls() {
  const headerActions = document.querySelector(".header-actions");
  if (!headerActions || document.querySelector("#api-token-button")) {
    return;
  }

  const button = document.createElement("button");
  button.id = "api-token-button";
  button.className = "secondary-button api-token-button";
  button.type = "button";
  button.title = "Set a session-only Kelvin API bearer token";
  button.addEventListener("click", () => promptForToken(button));
  updateAuthButton(button);
  headerActions.appendChild(button);
}

export function authFetch(input, options = {}) {
  const token = getToken();
  const headers = new Headers(options.headers || {});
  if (token && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  return fetch(input, {
    ...options,
    headers,
  });
}

export function apiErrorMessage(response, fallback) {
  if (response.status === 401) {
    return "API token is missing or invalid. Set it with the header API token button.";
  }
  if (response.status === 403) {
    return "The API token does not have the required scope for this action.";
  }
  return fallback;
}
