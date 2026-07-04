import uuid
from collections.abc import AsyncIterator, Sequence
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from kelvin_assistant.api.app import create_app
from kelvin_assistant.config.settings import Settings
from kelvin_assistant.domain.chat import ChatMessage
from kelvin_assistant.ports.llm import LLMProviderError


class StubLLMProvider:
    """Configurable language model provider for API contract tests."""

    def __init__(
        self,
        responses: list[str] | None = None,
        error: LLMProviderError | None = None,
    ) -> None:
        self._responses = list(responses or [])
        self._error = error
        self.chat_calls: list[tuple[ChatMessage, ...]] = []

    async def generate(self, prompt: str) -> str:
        """Return a deterministic generated response."""
        return f"generated: {prompt}"

    async def chat(self, messages: Sequence[ChatMessage]) -> str:
        """Record context and return the next configured response."""
        self.chat_calls.append(tuple(messages))
        if self._error is not None:
            raise self._error
        return self._responses.pop(0)

    async def stream_chat(self, messages: Sequence[ChatMessage]) -> AsyncIterator[str]:
        """Record context and stream the next configured response."""
        self.chat_calls.append(tuple(messages))
        if self._error is not None:
            raise self._error
        for chunk in self._responses.pop(0).split("|"):
            yield chunk

    async def check_readiness(self) -> None:
        """Report the stub provider as ready."""


@pytest.fixture
def settings() -> Settings:
    """Create deterministic API settings."""
    return Settings(
        app_name="Kelvin Test",
        app_version="0.3.0-test",
        environment="test",
        log_format="console",
        ollama_model="gemma4:test",
        api_auth_mode="disabled",
    )


def test_correlation_id_middleware_generates_id(settings: Settings) -> None:
    with TestClient(create_app(settings, llm_provider=StubLLMProvider())) as client:
        response = client.get("/")
    assert "X-Correlation-ID" in response.headers
    try:
        UUID(response.headers["X-Correlation-ID"])
    except ValueError:
        pytest.fail("X-Correlation-ID is not a valid UUID")


def test_correlation_id_middleware_uses_provided_id(settings: Settings) -> None:
    correlation_id = str(uuid.uuid4())
    with TestClient(create_app(settings, llm_provider=StubLLMProvider())) as client:
        response = client.get("/", headers={"X-Correlation-ID": correlation_id})
    assert response.headers["X-Correlation-ID"] == correlation_id


def test_create_chat_turn_includes_correlation_id(settings: Settings) -> None:
    provider = StubLLMProvider(responses=["Hello"])
    correlation_id = str(uuid.uuid4())
    with TestClient(create_app(settings, llm_provider=provider)) as client:
        response = client.post(
            "/api/v1/chat",
            json={"message": "Hi"},
            headers={"X-Correlation-ID": correlation_id},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["correlation_id"] == correlation_id


def test_stream_chat_turn_includes_correlation_id(settings: Settings) -> None:
    provider = StubLLMProvider(responses=["Hello"])
    correlation_id = str(uuid.uuid4())

    with TestClient(create_app(settings, llm_provider=provider)) as client:
        response = client.post(
            "/api/v1/chat/stream",
            json={"message": "Hi"},
            headers={"X-Correlation-ID": correlation_id},
        )

    assert response.status_code == 200
    body = response.text
    assert f'"correlation_id": "{correlation_id}"' in body
