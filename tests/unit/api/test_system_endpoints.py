"""Tests for the public system endpoints."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from kelvin_assistant.api.app import create_app
from kelvin_assistant.config.settings import Settings


@pytest.fixture
def client() -> Iterator[TestClient]:
    """Create an isolated API client with deterministic test settings."""

    settings = Settings(
        app_name="Kelvin Test",
        app_version="9.9.9",
        environment="test",
        log_format="console",
    )
    with TestClient(create_app(settings)) as test_client:
        yield test_client


def test_root_returns_application_metadata(client: TestClient) -> None:
    """The root endpoint exposes the configured application metadata."""

    response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {
        "name": "Kelvin Test",
        "version": "9.9.9",
        "environment": "test",
    }


def test_health_reports_ok(client: TestClient) -> None:
    """The health endpoint reports that the API process is available."""

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_version_returns_configured_version(client: TestClient) -> None:
    """The version endpoint exposes the configured application version."""

    response = client.get("/version")

    assert response.status_code == 200
    assert response.json() == {"version": "9.9.9"}
