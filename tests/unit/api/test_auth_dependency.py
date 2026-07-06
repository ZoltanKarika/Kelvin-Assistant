"""Unit tests for the require_scope API authentication dependency."""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from kelvin_assistant.adapters.file_api_tokens import (
    FileApiTokenAuthenticator,
    hash_api_token,
)
from kelvin_assistant.api.app import create_app
from kelvin_assistant.config.settings import Settings
from kelvin_assistant.domain.chat import ChatMessage

# ---------------------------------------------------------------------------
# Shared test infrastructure
# ---------------------------------------------------------------------------


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


def _make_settings(auth_mode: str = "disabled") -> Settings:
    """Return minimal test settings with an optional auth mode override."""
    return Settings(
        app_name="Kelvin Auth Test",
        app_version="0.0.0-test",
        environment="test",
        log_format="console",
        ollama_model="stub:test",
        api_auth_mode=auth_mode,  # type: ignore[arg-type]
    )


def _make_authenticator(
    tmp_path: Path,
    token: str,
    scopes: list[str],
    principal_id: str = "test-client",
) -> FileApiTokenAuthenticator:
    """Write a minimal token file and return an authenticator for it."""
    token_file = tmp_path / "api-tokens.json"
    token_sha256 = hash_api_token(token)
    token_file.write_text(
        f"""{{
  "version": 1,
  "tokens": [
    {{
      "id": "{principal_id}",
      "token_sha256": "{token_sha256}",
      "scopes": {scopes}
    }}
  ]
}}""".replace("'", '"'),
        encoding="utf-8",
    )
    return FileApiTokenAuthenticator.from_file(token_file)


# ---------------------------------------------------------------------------
# DISABLED mode tests — existing tests should all still pass
# ---------------------------------------------------------------------------


def test_chat_endpoint_accessible_when_auth_disabled() -> None:
    """When auth is disabled all routes are accessible without a token."""
    # This mirrors the existing test pattern: no token header, auth=disabled
    # The anonymous principal (all scopes) is used automatically.
    settings = _make_settings(auth_mode="disabled")
    with TestClient(create_app(settings, llm_provider=StubLLMProvider())) as client:
        response = client.post("/api/v1/chat", json={"message": "Hello"})

    # 200 means auth did NOT block the request — the stub returned "ok"
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# REQUIRED mode tests — token enforcement
# ---------------------------------------------------------------------------


@pytest.fixture
def chat_token() -> str:
    """A secret token string used in required-mode tests."""
    return "super-secret-test-token-abc123"  # noqa: S105 (test secret)


@pytest.fixture
def required_client(tmp_path: Path, chat_token: str) -> TestClient:
    """A test client whose app runs with api_auth_mode=required."""
    authenticator = _make_authenticator(
        tmp_path,
        token=chat_token,
        scopes=["chat:use", "system:read"],
        principal_id="chat-client",
    )
    settings = _make_settings(auth_mode="disabled")  # base settings
    app = create_app(settings, llm_provider=StubLLMProvider())
    # Override the authenticator in app state after creation so we can test
    # required-mode logic without needing a real token file path in Settings.
    app.state.api_token_authenticator = authenticator
    return TestClient(app)


def test_chat_returns_401_without_token(required_client: TestClient) -> None:
    """A request without Authorization header returns 401."""
    response = required_client.post("/api/v1/chat", json={"message": "Hi"})

    assert response.status_code == 401
    assert response.json()["detail"] == "Missing Bearer token."
    # RFC 6750 requires WWW-Authenticate: Bearer on 401 responses
    assert "Bearer" in response.headers.get("www-authenticate", "")


def test_chat_returns_401_for_wrong_token(required_client: TestClient) -> None:
    """A request with an invalid Bearer token returns 401."""
    response = required_client.post(
        "/api/v1/chat",
        json={"message": "Hi"},
        headers={"Authorization": "Bearer totally-wrong-token"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid or expired Bearer token."


def test_chat_succeeds_with_valid_token(
    required_client: TestClient, chat_token: str
) -> None:
    """A request with the correct Bearer token returns 200."""
    response = required_client.post(
        "/api/v1/chat",
        json={"message": "Hi"},
        headers={"Authorization": f"Bearer {chat_token}"},
    )

    assert response.status_code == 200


def test_endpoint_returns_403_for_insufficient_scope(
    tmp_path: Path,
) -> None:
    """A valid token that lacks the required scope returns 403."""
    token = "read-only-token-xyz"  # noqa: S105
    # This token only has system:read — NOT chat:use
    authenticator = _make_authenticator(
        tmp_path,
        token=token,
        scopes=["system:read"],
        principal_id="monitoring-bot",
    )
    settings = _make_settings(auth_mode="disabled")
    app = create_app(settings, llm_provider=StubLLMProvider())
    app.state.api_token_authenticator = authenticator

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/chat",
            json={"message": "Hi"},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 403
    assert "chat:use" in response.json()["detail"]


def test_health_endpoint_requires_no_token(required_client: TestClient) -> None:
    """The /health endpoint is always public — no token, no auth check."""
    response = required_client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_root_endpoint_requires_no_token(required_client: TestClient) -> None:
    """The / root endpoint is always public."""
    response = required_client.get("/")

    assert response.status_code == 200


def test_require_scope_returns_matching_principal(
    required_client: TestClient, chat_token: str
) -> None:
    """A valid token response includes the correct API scopes for the principal."""
    # We verify this indirectly: if the right principal is resolved,
    # the endpoint succeeds and returns valid chat output.
    response = required_client.post(
        "/api/v1/chat",
        json={"message": "Scope check"},
        headers={"Authorization": f"Bearer {chat_token}"},
    )

    # 200 means: token validated → principal resolved → scope matched → handler ran
    assert response.status_code == 200
    body = response.json()
    assert "session_id" in body
    assert "message" in body


def test_returns_500_when_auth_required_but_not_configured() -> None:
    """If auth mode is required but no authenticator is set, returns 500."""
    settings = _make_settings(auth_mode="required")
    app = create_app(settings, llm_provider=StubLLMProvider(), api_authenticator=None)

    with TestClient(app) as client:
        response = client.post("/api/v1/chat", json={"message": "Hi"})

    assert response.status_code == 500
    assert "Authentication is required but not configured" in response.json()["detail"]
