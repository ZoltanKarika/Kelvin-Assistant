"""Unit tests for n8n health check API endpoints."""

from unittest.mock import MagicMock, patch

import httpx2
from fastapi import FastAPI
from fastapi.testclient import TestClient

from kelvin_assistant.api.app import create_app
from kelvin_assistant.config.settings import Settings


def _app(n8n_url: str | None = None) -> FastAPI:
    """Create a test application with custom n8n configurations."""

    settings = Settings(
        environment="test",
        log_format="console",
        n8n_url=n8n_url,
        n8n_token="test-n8n-token" if n8n_url else None,
    )
    return create_app(settings)


def test_n8n_health_unconfigured() -> None:
    """GET /api/v1/n8n/health returns unconfigured when URL is empty."""

    app = _app(n8n_url=None)
    with TestClient(app) as client:
        response = client.get("/api/v1/n8n/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "unconfigured"
        assert data["configured"] is False
        assert data["base_url"] is None


@patch("httpx2.AsyncClient.get")
def test_n8n_health_healthy(mock_get: MagicMock) -> None:
    """GET /api/v1/n8n/health returns healthy when n8n responds successfully."""

    # Mock success response
    mock_response = MagicMock(spec=httpx2.Response)
    mock_response.status_code = 200
    mock_get.return_value = mock_response

    app = _app(n8n_url="http://mock-n8n:5678")
    with TestClient(app) as client:
        response = client.get("/api/v1/n8n/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["configured"] is True
        assert data["base_url"] == "http://mock-n8n:5678"
        assert data["error_message"] is None

        # Verify headers passed correctly
        mock_get.assert_called_once_with(
            "http://mock-n8n:5678",
            headers={"X-N8N-API-KEY": "test-n8n-token"},
        )


@patch("httpx2.AsyncClient.get")
def test_n8n_health_degraded(mock_get: MagicMock) -> None:
    """GET /api/v1/n8n/health returns degraded when n8n returns server error."""

    # Mock server error response
    mock_response = MagicMock(spec=httpx2.Response)
    mock_response.status_code = 500
    mock_get.return_value = mock_response

    app = _app(n8n_url="http://mock-n8n:5678")
    with TestClient(app) as client:
        response = client.get("/api/v1/n8n/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "degraded"
        assert "server error" in data["error_message"].lower()


@patch("httpx2.AsyncClient.get")
def test_n8n_health_unreachable(mock_get: MagicMock) -> None:
    """GET /api/v1/n8n/health returns unreachable when connection fails."""

    # Mock request failure
    mock_get.side_effect = httpx2.RequestError("Connection refused")

    app = _app(n8n_url="http://mock-n8n:5678")
    with TestClient(app) as client:
        response = client.get("/api/v1/n8n/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "unreachable"
        assert "connection failed" in data["error_message"].lower()
