"""Unit tests for network resilience origin allowlist and idempotency checks."""

from collections.abc import AsyncIterator, Sequence

import pytest
from fastapi.testclient import TestClient

from kelvin_assistant.api.app import create_app
from kelvin_assistant.config.settings import Settings
from kelvin_assistant.domain.chat import ChatMessage


class StubLLMProvider:
    """Minimal LLM provider stub that records nothing and raises nothing."""

    async def generate(self, prompt: str) -> str:
        return "ok"

    async def chat(self, messages: Sequence[ChatMessage]) -> str:
        return "ok"

    async def stream_chat(self, messages: Sequence[ChatMessage]) -> AsyncIterator[str]:
        yield "ok"

    async def check_readiness(self) -> None:
        pass


@pytest.fixture
def base_settings() -> Settings:
    """Return default Settings for network resilience testing."""
    return Settings(
        app_name="Kelvin Resilience Test",
        app_version="0.0.0-test",
        environment="test",
        log_format="console",
        ollama_model="stub:test",
    )


def test_ip_allowlist_default_allows_all(base_settings: Settings) -> None:
    """By default, allowed_clients is empty, permitting any client IP."""
    app = create_app(base_settings, llm_provider=StubLLMProvider())
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200


def test_ip_allowlist_blocks_non_allowed_ip(base_settings: Settings) -> None:
    """A client request from a non-allowlisted IP is blocked with a 403."""
    base_settings.allowed_clients = ("127.0.0.1", "192.168.1.0/24")
    app = create_app(base_settings, llm_provider=StubLLMProvider())

    with TestClient(app) as client:
        response = client.get("/health", headers={"X-Forwarded-For": "10.0.0.1"})

    assert response.status_code == 403
    assert "Forbidden" in response.text


def test_ip_allowlist_permits_allowlisted_ip_subnet(
    base_settings: Settings,
) -> None:
    """A client request from an IP inside the allowed subnet is permitted."""
    base_settings.allowed_clients = ("127.0.0.1", "192.168.1.0/24")
    app = create_app(base_settings, llm_provider=StubLLMProvider())

    with TestClient(app) as client:
        response = client.get("/health", headers={"X-Forwarded-For": "192.168.1.15"})

    assert response.status_code == 200


def test_idempotency_cached_response(base_settings: Settings) -> None:
    """Repeated runs requests with same X-Idempotency-Key return cached response."""
    app = create_app(base_settings, llm_provider=StubLLMProvider())

    with TestClient(app) as client:
        headers = {"X-Idempotency-Key": "idemp-key-123"}
        response1 = client.post(
            "/api/v1/agent/runs",
            json={"goal": "Calculate Fibonacci sequence"},
            headers=headers,
        )
        assert response1.status_code == 201
        body1 = response1.json()

        # Make a second request with same key but a different goal
        response2 = client.post(
            "/api/v1/agent/runs",
            json={"goal": "Different goal that should be ignored!"},
            headers=headers,
        )
        assert response2.status_code == 201
        body2 = response2.json()

        # Check that we received the identical response cached from the first call
        assert body1["id"] == body2["id"]
        assert body1["goal"] == body2["goal"]
