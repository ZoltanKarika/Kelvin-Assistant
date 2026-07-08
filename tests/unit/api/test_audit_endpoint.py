"""Unit tests for security audit log API endpoints."""

from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from kelvin_assistant.adapters.memory_security_audit import InMemorySecurityAuditLogger
from kelvin_assistant.api.app import create_app
from kelvin_assistant.config.settings import Settings


def _app() -> FastAPI:
    """Create a test application using process memory adapters."""

    settings = Settings(environment="test", log_format="console")
    # Using InMemorySecurityAuditLogger by default
    return create_app(settings)


def test_list_security_audit_logs_empty() -> None:
    """GET /security/audit returns an empty list when no entries exist."""

    with TestClient(_app()) as client:
        response = client.get("/api/v1/security/audit")
        assert response.status_code == 200
        assert response.json() == []


def test_list_security_audit_logs_with_entries() -> None:
    """GET /security/audit returns and filters logged decisions."""

    app = _app()
    logger = app.state.security_audit_logger
    assert isinstance(logger, InMemorySecurityAuditLogger)

    # Log some dummy decisions directly to the adapter
    run_id_1 = uuid4()
    run_id_2 = uuid4()
    corr_id = uuid4()

    import asyncio

    async def log_dummy_data() -> None:
        await logger.log_decision(
            event_type="input_guard",
            decision="allow",
            masked_content="hello [REDACTED]",
            warnings=["warning 1"],
            correlation_id=corr_id,
            run_id=run_id_1,
        )
        await logger.log_decision(
            event_type="output_guard",
            decision="block",
            masked_content="secret leaked [MASKED]",
            warnings=["warning 2"],
            correlation_id=None,
            run_id=run_id_2,
        )

    asyncio.run(log_dummy_data())

    with TestClient(app) as client:
        # 1. Fetch all
        response = client.get("/api/v1/security/audit")
        assert response.status_code == 200
        entries = response.json()
        assert len(entries) == 2
        # Descending order by default
        assert entries[0]["event_type"] == "output_guard"
        assert entries[0]["decision"] == "block"
        assert entries[1]["event_type"] == "input_guard"
        assert entries[1]["decision"] == "allow"

        # 2. Filter by event_type
        response_filter_type = client.get(
            "/api/v1/security/audit?event_type=input_guard"
        )
        assert response_filter_type.status_code == 200
        assert len(response_filter_type.json()) == 1
        assert response_filter_type.json()[0]["event_type"] == "input_guard"

        # 3. Filter by decision
        response_filter_dec = client.get("/api/v1/security/audit?decision=block")
        assert response_filter_dec.status_code == 200
        assert len(response_filter_dec.json()) == 1
        assert response_filter_dec.json()[0]["decision"] == "block"

        # 4. Filter by run_id
        response_filter_run = client.get(f"/api/v1/security/audit?run_id={run_id_1}")
        assert response_filter_run.status_code == 200
        assert len(response_filter_run.json()) == 1
        assert response_filter_run.json()[0]["run_id"] == str(run_id_1)

        # 5. Filter by correlation_id
        response_filter_corr = client.get(
            f"/api/v1/security/audit?correlation_id={corr_id}"
        )
        assert response_filter_corr.status_code == 200
        assert len(response_filter_corr.json()) == 1
        assert response_filter_corr.json()[0]["correlation_id"] == str(corr_id)

        # 6. Pagination (limit/offset)
        response_limit = client.get("/api/v1/security/audit?limit=1")
        assert response_limit.status_code == 200
        assert len(response_limit.json()) == 1
        assert response_limit.json()[0]["event_type"] == "output_guard"
