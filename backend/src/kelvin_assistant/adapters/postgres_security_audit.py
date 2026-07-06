"""PostgreSQL adapter for security audit logs."""

import json
import logging
from uuid import UUID

import psycopg

from kelvin_assistant.config.settings import Settings, get_settings
from kelvin_assistant.ports.security_audit import SecurityAuditLogger

LOGGER = logging.getLogger(__name__)


class PostgresSecurityAuditLogger(SecurityAuditLogger):
    """PostgreSQL adapter for security audit logs."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    async def log_decision(
        self,
        *,
        event_type: str,
        decision: str,
        masked_content: str | None,
        warnings: list[str],
        correlation_id: UUID | None = None,
        run_id: UUID | None = None,
    ) -> None:
        if self._settings.database_url is None:
            return

        try:
            connection = await psycopg.AsyncConnection.connect(
                self._settings.database_url,
                connect_timeout=self._settings.database_connect_timeout,
            )
            async with connection:
                async with connection.cursor() as cursor:
                    await cursor.execute(
                        """
                        insert into security_audit_logs (
                            correlation_id,
                            run_id,
                            event_type,
                            decision,
                            masked_content,
                            warnings
                        )
                        values (%s, %s, %s, %s, %s, %s)
                        """,
                        (
                            correlation_id,
                            run_id,
                            event_type,
                            decision,
                            masked_content,
                            json.dumps(warnings),
                        ),
                    )
                    await connection.commit()
        except Exception as exc:
            LOGGER.error("Failed to write security audit log: %s", exc)
