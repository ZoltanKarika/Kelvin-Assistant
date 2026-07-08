"""Tests for the bundled browser interface."""

from collections.abc import AsyncIterator, Sequence

from fastapi.testclient import TestClient

from kelvin_assistant.api.app import create_app
from kelvin_assistant.config.settings import Settings
from kelvin_assistant.domain.chat import ChatMessage


class StubLLMProvider:
    """Minimal provider used while testing static frontend delivery."""

    async def generate(self, prompt: str) -> str:
        """Return a deterministic generated response."""

        return prompt

    async def chat(self, messages: Sequence[ChatMessage]) -> str:
        """Return a deterministic chat response."""

        return str(len(messages))

    async def stream_chat(self, messages: Sequence[ChatMessage]) -> AsyncIterator[str]:
        """Return a deterministic streaming chat response."""

        yield str(len(messages))

    async def check_readiness(self) -> None:
        """Report the provider as ready."""


def create_test_client() -> TestClient:
    """Create an API client without connecting to Ollama."""

    settings = Settings(environment="test", log_format="console")
    return TestClient(create_app(settings, llm_provider=StubLLMProvider()))


def test_ui_returns_bundled_html() -> None:
    """The UI route returns its UTF-8 HTML entry page."""

    with create_test_client() as client:
        response = client.get("/ui")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert '<html lang="hu">' in response.text
    assert "Kelvin Assistant" in response.text
    assert 'href="/static/styles.css"' in response.text
    assert 'src="/static/app.js"' in response.text
    assert 'id="chat-form"' in response.text
    assert 'id="message-input"' in response.text
    assert 'id="new-chat-button"' in response.text
    assert 'href="/ui/runs"' in response.text


def test_runs_ui_returns_html() -> None:
    """The runs UI route returns its HTML page."""

    with create_test_client() as client:
        response = client.get("/ui/runs")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "<h1>Futások</h1>" in response.text


def test_approvals_ui_returns_html() -> None:
    """The approvals UI route returns its HTML page."""

    with create_test_client() as client:
        response = client.get("/ui/approvals")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "<h1>Jóváhagyások</h1>" in response.text


def test_audit_ui_returns_html() -> None:
    """The audit UI route returns its HTML page."""

    with create_test_client() as client:
        response = client.get("/ui/audit")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "<h1>Biztonsági napló (Audit)</h1>" in response.text


def test_settings_ui_returns_html() -> None:
    """The settings UI route returns its HTML page."""

    with create_test_client() as client:
        response = client.get("/ui/settings")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "<h1>Rendszerbeállítások</h1>" in response.text


def test_n8n_ui_returns_html() -> None:
    """The n8n UI route returns its HTML page."""

    with create_test_client() as client:
        response = client.get("/ui/n8n")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "<h1>n8n Automációs Állapot</h1>" in response.text


def test_static_assets_are_available() -> None:
    """The CSS and JavaScript assets are served below the static path."""

    with create_test_client() as client:
        css_response = client.get("/static/styles.css")
        script_response = client.get("/static/app.js")
        runs_script_response = client.get("/static/runs.js")
        approvals_script_response = client.get("/static/approvals.js")
        audit_script_response = client.get("/static/audit.js")
        settings_script_response = client.get("/static/settings.js")
        n8n_script_response = client.get("/static/n8n.js")

    assert css_response.status_code == 200
    assert css_response.headers["content-type"].startswith("text/css")
    assert script_response.status_code == 200
    assert "javascript" in script_response.headers["content-type"]
    assert 'fetch("/api/v1/chat/stream"' in script_response.text
    assert "readStreamingResponse" in script_response.text
    assert runs_script_response.status_code == 200
    assert "javascript" in runs_script_response.headers["content-type"]
    assert "fetchRuns" in runs_script_response.text
    assert approvals_script_response.status_code == 200
    assert "javascript" in approvals_script_response.headers["content-type"]
    assert "fetchPendingApprovals" in approvals_script_response.text
    assert audit_script_response.status_code == 200
    assert "javascript" in audit_script_response.headers["content-type"]
    assert "fetchAuditLogs" in audit_script_response.text
    assert settings_script_response.status_code == 200
    assert "javascript" in settings_script_response.headers["content-type"]
    assert "loadSettings" in settings_script_response.text
    assert n8n_script_response.status_code == 200
    assert "javascript" in n8n_script_response.headers["content-type"]
    assert "fetchN8NHealth" in n8n_script_response.text
