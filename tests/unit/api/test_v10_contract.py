"""Regression tests for the v1.0 public API and configuration contract."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from kelvin_assistant.api.app import create_app
from kelvin_assistant.config.settings import Settings
from kelvin_assistant.domain.auth import ApiScope

EXPECTED_OPERATIONS = {
    "/": {"get"},
    "/health": {"get"},
    "/status": {"get"},
    "/ready": {"get"},
    "/ready/database": {"get"},
    "/version": {"get"},
    "/api/v1/chat": {"post"},
    "/api/v1/chat/stream": {"post"},
    "/api/v1/memory": {"get", "post"},
    "/api/v1/memory/{memory_id}": {"delete"},
    "/api/v1/agent/runs": {"get", "post"},
    "/api/v1/agent/runs/{run_id}": {"get"},
    "/api/v1/agent/runs/{run_id}/plan": {"post"},
    "/api/v1/agent/runs/{run_id}/next": {"post"},
    "/api/v1/agent/runs/{run_id}/cancel": {"post"},
    "/api/v1/agent/runs/{run_id}/tools": {"post"},
    "/api/v1/agent/runs/{run_id}/tools/active": {"get"},
    "/api/v1/agent/runs/{run_id}/approval": {"post"},
    "/api/v1/agent/runs/{run_id}/result": {"post"},
    "/api/v1/security/audit": {"get"},
    "/api/v1/settings": {"get", "put"},
    "/api/v1/settings/test-email": {"post"},
    "/api/v1/settings/send-summary": {"post"},
    "/api/v1/n8n/health": {"get"},
}

EXPECTED_SCOPES = {
    "system:read",
    "chat:use",
    "knowledge:read",
    "memory:read",
    "memory:write",
    "agent:execute",
    "agent:write",
    "agent:approve",
}

EXPECTED_ENV_VARS = {
    "KELVIN_API_AUTH_MODE",
    "KELVIN_API_TOKEN_FILE",
    "KELVIN_LLM_PROVIDER",
    "KELVIN_OLLAMA_BASE_URL",
    "KELVIN_OLLAMA_MODEL",
    "KELVIN_OLLAMA_EMBEDDING_MODEL",
    "KELVIN_DATABASE_URL",
    "KELVIN_RAG_ENABLED",
    "KELVIN_N8N_URL",
    "KELVIN_N8N_TOKEN",
    "KELVIN_EMAIL_NOTIFICATIONS_ENABLED",
    "KELVIN_EMAIL_PROVIDER_MODE",
    "KELVIN_EMAIL_SMTP_HOST",
    "KELVIN_EMAIL_SMTP_PORT",
    "KELVIN_EMAIL_SMTP_PASSWORD",
    "KELVIN_EMAIL_RECIPIENT",
    "KELVIN_AGENT_WORKSPACE_IDS",
    "KELVIN_API_URL",
    "KELVIN_API_TIMEOUT_SECONDS",
    "KELVIN_WORKSPACE_ID",
    "KELVIN_WORKSPACE_PATH",
}


def test_v10_openapi_contains_stable_route_contract() -> None:
    """The frozen v1.0 route list remains present in OpenAPI."""

    settings = Settings(
        app_name="Kelvin Contract Test",
        app_version="1.0.0-test",
        environment="test",
        log_format="console",
    )

    with TestClient(create_app(settings)) as client:
        schema = client.get("/openapi.json").json()

    for path, methods in EXPECTED_OPERATIONS.items():
        assert path in schema["paths"]
        assert methods.issubset(schema["paths"][path])


def test_v10_token_scopes_match_contract_and_example() -> None:
    """The scope enum and example token file stay aligned with the v1.0 contract."""

    assert {scope.value for scope in ApiScope} == EXPECTED_SCOPES

    token_example = json.loads(Path("api-tokens.example.json").read_text())
    configured_scopes = {
        scope for token in token_example["tokens"] for scope in token["scopes"]
    }
    assert configured_scopes.issubset(EXPECTED_SCOPES)
    for token in token_example["tokens"]:
        assert "token" not in token
    assert "token_sha256" in json.dumps(token_example)


def test_v10_env_example_documents_stable_config_contract() -> None:
    """The checked-in env example documents the stable server/client variables."""

    env_example = Path(".env.example").read_text(encoding="utf-8")

    for variable in EXPECTED_ENV_VARS:
        assert variable in env_example
