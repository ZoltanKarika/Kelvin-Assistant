"""PostgreSQL adapter for security audit logs."""

import json
import logging
from collections.abc import Sequence
from uuid import UUID

import psycopg

from kelvin_assistant.config.settings import Settings, get_settings
from kelvin_assistant.ports.security_audit import (
    SecurityAuditEntry,
    SecurityAuditLogger,
)

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

    async def list_entries(
        self,
        *,
        event_type: str | None = None,
        decision: str | None = None,
        run_id: UUID | None = None,
        correlation_id: UUID | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Sequence[SecurityAuditEntry]:
        if self._settings.database_url is None:
            return []

        try:
            connection = await psycopg.AsyncConnection.connect(
                self._settings.database_url,
                connect_timeout=self._settings.database_connect_timeout,
            )
            async with connection:
                async with connection.cursor() as cursor:
                    query = """
                        select
                            id,
                            correlation_id,
                            run_id,
                            event_type,
                            decision,
                            masked_content,
                            warnings,
                            created_at
                        from security_audit_logs
                    """
                    conditions = []
                    params: list[object] = []

                    if event_type is not None:
                        conditions.append("event_type = %s")
                        params.append(event_type)
                    if decision is not None:
                        conditions.append("decision = %s")
                        params.append(decision)
                    if run_id is not None:
                        conditions.append("run_id = %s")
                        params.append(run_id)
                    if correlation_id is not None:
                        conditions.append("correlation_id = %s")
                        params.append(correlation_id)

                    if conditions:
                        query += " where " + " and ".join(conditions)

                    query += " order by created_at desc limit %s offset %s"
                    params.extend([limit, offset])

                    await cursor.execute(query, tuple(params))
                    rows = await cursor.fetchall()

                    entries = []
                    for row in rows:
                        entries.append(
                            SecurityAuditEntry(
                                id=UUID(str(row[0])),
                                correlation_id=UUID(str(row[1]))
                                if row[1] is not None
                                else None,
                                run_id=UUID(str(row[2]))
                                if row[2] is not None
                                else None,
                                event_type=str(row[3]),
                                decision=str(row[4]),
                                masked_content=str(row[5])
                                if row[5] is not None
                                else None,
                                warnings=row[6]
                                if isinstance(row[6], list)
                                else json.loads(row[6])
                                if isinstance(row[6], str)
                                else [],
                                created_at=row[7],
                            )
                        )
                    return entries
        except Exception as exc:
            LOGGER.error("Failed to query security audit logs: %s", exc)
            return []
