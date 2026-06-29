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


def test_static_assets_are_available() -> None:
    """The CSS and JavaScript assets are served below the static path."""

    with create_test_client() as client:
        css_response = client.get("/static/styles.css")
        script_response = client.get("/static/app.js")

    assert css_response.status_code == 200
    assert css_response.headers["content-type"].startswith("text/css")
    assert script_response.status_code == 200
    assert "javascript" in script_response.headers["content-type"]
    assert 'fetch("/api/v1/chat/stream"' in script_response.text
    assert "readStreamingResponse" in script_response.text
