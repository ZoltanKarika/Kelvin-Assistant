"""Unit tests for settings and safety controls API endpoints."""

from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from kelvin_assistant.api.app import create_app
from kelvin_assistant.config.settings import Settings


def _app() -> FastAPI:
    """Create a test application using process memory configurations."""

    settings = Settings(
        environment="test",
        log_format="console",
        ollama_base_url="http://mock-ollama:11434",
        ollama_model="mock-gemma",
        n8n_url="http://mock-n8n:5678",
        n8n_token="mock-n8n-secret-token",
        email_notifications_enabled=True,
        email_smtp_host="mock-smtp",
        email_smtp_port=587,
        email_smtp_username="mock-user",
        email_smtp_password="mock-smtp-password",
        email_smtp_use_tls=True,
        email_sender="mock-sender@test.local",
        email_recipient="mock-recipient@test.local",
        agent_workspace_ids=("test-workspace-1", "test-workspace-2"),
    )
    return create_app(settings)


def test_get_settings() -> None:
    """GET /api/v1/settings returns current configuration with secret masking."""

    app = _app()
    with TestClient(app) as client:
        response = client.get("/api/v1/settings")
        assert response.status_code == 200
        data = response.json()

        # Check basic fields
        assert data["ollama_base_url"] == "http://mock-ollama:11434"
        assert data["ollama_model"] == "mock-gemma"
        assert data["n8n_url"] == "http://mock-n8n:5678"

        # Check secret masking: secrets should NOT be returned as raw strings
        assert "mock-n8n-secret-token" not in data.values()
        assert "mock-smtp-password" not in data.values()
        assert data["n8n_token_configured"] is True
        assert data["email_smtp_password_configured"] is True

        # Check safety summaries
        assert "Default local safety policy" in data["tool_policy_summary"]
        assert "test-workspace-1" in data["workspace_ids"]
        assert "test-workspace-2" in data["workspace_ids"]
        assert "system:read" in data["allowed_scopes"]


@patch("kelvin_assistant.api.settings_routes.update_env_file")
def test_update_settings_success(mock_update_env: MagicMock) -> None:
    """PUT /api/v1/settings updates settings in-memory and triggers env save."""

    app = _app()
    with TestClient(app) as client:
        # Update settings
        update_data = {
            "ollama_base_url": "http://new-ollama:11434",
            "ollama_model": "new-gemma",
            "system_prompt": "You are a new helpful assistant",
            "n8n_url": "http://new-n8n:5678",
            "n8n_token": "new-n8n-token",
            "email_notifications_enabled": False,
            "email_smtp_port": 1025,
            "email_smtp_password": "new-smtp-password",
        }
        response = client.put("/api/v1/settings", json=update_data)
        assert response.status_code == 200
        data = response.json()

        # Check response details
        assert data["ollama_base_url"] == "http://new-ollama:11434"
        assert data["ollama_model"] == "new-gemma"
        assert data["system_prompt"] == "You are a new helpful assistant"
        assert data["n8n_url"] == "http://new-n8n:5678"
        assert data["email_notifications_enabled"] is False
        assert data["email_smtp_port"] == 1025
        assert data["n8n_token_configured"] is True
        assert data["email_smtp_password_configured"] is True

        # Verify in-memory values changed
        settings = app.state.settings
        assert settings.ollama_base_url == "http://new-ollama:11434"
        assert settings.ollama_model == "new-gemma"
        assert settings.system_prompt == "You are a new helpful assistant"
        assert settings.n8n_token == "new-n8n-token"
        assert settings.email_smtp_password == "new-smtp-password"

        # Verify env file update was called
        mock_update_env.assert_called_once()
        called_args = mock_update_env.call_args[0][0]
        assert called_args["KELVIN_OLLAMA_BASE_URL"] == "http://new-ollama:11434"
        assert called_args["KELVIN_SYSTEM_PROMPT"] == "You are a new helpful assistant"
        assert called_args["KELVIN_N8N_TOKEN"] == "new-n8n-token"
        assert called_args["KELVIN_EMAIL_SMTP_PASSWORD"] == "new-smtp-password"


def test_update_settings_validation_errors() -> None:
    """PUT /api/v1/settings validates incorrect port and empty system prompt."""

    app = _app()
    with TestClient(app) as client:
        # Invalid SMTP port
        response = client.put("/api/v1/settings", json={"email_smtp_port": 999999})
        assert response.status_code == 422

        # Empty system prompt
        response = client.put("/api/v1/settings", json={"system_prompt": "   "})
        assert response.status_code == 422


@patch("kelvin_assistant.api.settings_routes.update_env_file")
def test_update_settings_save_failure_returns_json(mock_update_env: MagicMock) -> None:
    """PUT /api/v1/settings returns a structured error when .env save fails."""

    mock_update_env.side_effect = OSError("permission denied")
    app = _app()

    with TestClient(app) as client:
        response = client.put("/api/v1/settings", json={"email_smtp_port": 1025})

    assert response.status_code == 500
    assert response.headers["content-type"].startswith("application/json")
    assert response.json()["detail"].startswith("Failed to save settings file:")
    assert app.state.settings.email_smtp_port == 587


def test_send_test_email_disabled() -> None:
    """POST /api/v1/settings/test-email fails if email notifications are disabled."""

    app = _app()
    # Disable email
    app.state.settings.email_notifications_enabled = False

    with TestClient(app) as client:
        response = client.post("/api/v1/settings/test-email")
        assert response.status_code == 400
        assert "disabled" in response.json()["detail"].lower()


@patch("smtplib.SMTP")
def test_send_test_email_success(mock_smtp_class: MagicMock) -> None:
    """POST /api/v1/settings/test-email sends email using smtplib when enabled."""

    app = _app()
    app.state.settings.email_notifications_enabled = True

    # Setup mock SMTP server instance
    mock_server = MagicMock()
    mock_smtp_class.return_value.__enter__.return_value = mock_server

    with TestClient(app) as client:
        response = client.post("/api/v1/settings/test-email")
        assert response.status_code == 200
        assert response.json()["status"] == "success"

        # Verify SMTP server lifecycle was called correctly
        mock_smtp_class.assert_called_once_with("mock-smtp", 587, timeout=10)
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once_with("mock-user", "mock-smtp-password")
        mock_server.sendmail.assert_called_once()


def test_send_summary_disabled() -> None:
    """POST /api/v1/settings/send-summary fails if email notifications are disabled."""

    app = _app()
    app.state.settings.email_notifications_enabled = False

    with TestClient(app) as client:
        response = client.post("/api/v1/settings/send-summary")
        assert response.status_code == 400
        assert "disabled" in response.json()["detail"].lower()


@patch("smtplib.SMTP")
def test_send_summary_success(mock_smtp_class: MagicMock) -> None:
    """POST /api/v1/settings/send-summary sends daily summary email when enabled."""

    app = _app()
    app.state.settings.email_notifications_enabled = True

    # Setup mock SMTP server instance
    mock_server = MagicMock()
    mock_smtp_class.return_value.__enter__.return_value = mock_server

    with TestClient(app) as client:
        response = client.post("/api/v1/settings/send-summary")
        assert response.status_code == 200
        assert response.json()["status"] == "success"

        # Verify SMTP server lifecycle was called correctly
        mock_smtp_class.assert_called_once_with("mock-smtp", 587, timeout=10)
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once_with("mock-user", "mock-smtp-password")
        mock_server.sendmail.assert_called_once()
