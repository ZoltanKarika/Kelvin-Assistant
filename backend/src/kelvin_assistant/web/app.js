"use strict";

const form = document.querySelector("#chat-form");
const input = document.querySelector("#message-input");
const sendButton = document.querySelector("#send-button");
const newChatButton = document.querySelector("#new-chat-button");
const messages = document.querySelector("#messages");
const welcome = document.querySelector("#welcome");
const errorBanner = document.querySelector("#error-banner");
const runtimeStatus = document.querySelector(".runtime-status");
const runtimeStatusText = document.querySelector("#runtime-status-text");

let sessionId = null;
let requestInProgress = false;

function setRuntimeStatus(state, label) {
  runtimeStatus.dataset.state = state;
  runtimeStatusText.textContent = label;
}

function setBusy(isBusy) {
  requestInProgress = isBusy;
  input.disabled = isBusy;
  sendButton.disabled = isBusy;
  newChatButton.disabled = isBusy;
  sendButton.querySelector("span:first-child").textContent = isBusy
    ? "Gondolkodik"
    : "Küldés";
}

function showError(message) {
  errorBanner.textContent = message;
  errorBanner.hidden = false;
}

function clearError() {
  errorBanner.textContent = "";
  errorBanner.hidden = true;
}

function scrollToLatestMessage() {
  messages.scrollTo({ top: messages.scrollHeight, behavior: "smooth" });
}

function addMessage(role, text, options = {}) {
  welcome.hidden = true;

  const article = document.createElement("article");
  article.className = "message";
  article.dataset.role = role;
  if (options.pending) {
    article.classList.add("is-pending");
  }

  const avatar = document.createElement("div");
  avatar.className = "message-avatar";
  avatar.setAttribute("aria-hidden", "true");
  avatar.textContent = role === "assistant" ? "K" : "TE";

  const content = document.createElement("div");
  content.className = "message-content";

  const author = document.createElement("p");
  author.className = "message-author";
  author.textContent = role === "assistant" ? "KELVIN" : "TE";

  const body = document.createElement("p");
  body.className = "message-text";
  body.textContent = text;

  content.append(author, body);
  article.append(avatar, content);
  messages.append(article);
  scrollToLatestMessage();

  return article;
}

function resizeInput() {
  input.style.height = "auto";
  input.style.height = `${Math.min(input.scrollHeight, 176)}px`;
}

function describeApiError(status, detail) {
  const knownErrors = {
    404: "A beszélgetés már nem található. Indíts új beszélgetést.",
    409: "A beszélgetés közben megváltozott. Kérlek, próbáld újra.",
    422: "Az üzenet üres vagy nem megfelelő formátumú.",
    502: "A modell most nem adott feldolgozható választ.",
    503: "A helyi AI modell jelenleg nem érhető el.",
  };

  return knownErrors[status] ?? detail ?? "Váratlan hiba történt.";
}

async function readResponseBody(response) {
  try {
    return await response.json();
  } catch {
    return {};
  }
}

async function sendMessage(message) {
  addMessage("user", message);
  const pendingMessage = addMessage("assistant", "Gondolkodom", {
    pending: true,
  });

  setBusy(true);
  clearError();

  try {
    const response = await fetch("/api/v1/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message,
        ...(sessionId ? { session_id: sessionId } : {}),
      }),
    });
    const body = await readResponseBody(response);

    if (!response.ok) {
      throw new Error(describeApiError(response.status, body.detail));
    }

    sessionId = body.session_id;
    pendingMessage.querySelector(".message-text").textContent = body.message;
    pendingMessage.classList.remove("is-pending");
  } catch (error) {
    pendingMessage.remove();
    showError(
      error instanceof Error
        ? error.message
        : "Nem sikerült kapcsolódni a Kelvin API-hoz.",
    );
  } finally {
    setBusy(false);
    input.focus();
    scrollToLatestMessage();
  }
}

async function checkRuntime() {
  setRuntimeStatus("checking", "Kapcsolódás…");

  try {
    const [healthResponse, readyResponse] = await Promise.all([
      fetch("/health"),
      fetch("/ready"),
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

form.addEventListener("submit", (event) => {
  event.preventDefault();

  const message = input.value.trim();
  if (!message || requestInProgress) {
    return;
  }

  input.value = "";
  resizeInput();
  void sendMessage(message);
});

input.addEventListener("input", resizeInput);
input.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    form.requestSubmit();
  }
});

newChatButton.addEventListener("click", () => {
  sessionId = null;
  clearError();
  messages.querySelectorAll(".message").forEach((message) => message.remove());
  welcome.hidden = false;
  input.value = "";
  resizeInput();
  input.focus();
});

document.documentElement.dataset.kelvinUi = "ready";
resizeInput();
input.focus();
void checkRuntime();
