"""Unit tests for the security audit logging system."""

import unittest
from uuid import uuid4

from kelvin_assistant.adapters.memory_security_audit import InMemorySecurityAuditLogger
from kelvin_assistant.adapters.postgres_security_audit import (
    PostgresSecurityAuditLogger,
)
from kelvin_assistant.config.settings import Settings
from kelvin_assistant.domain.output_guard import mask_secrets


class TestSecurityAuditLogging(unittest.IsolatedAsyncioTestCase):
    """Tests for in-memory and postgres security audit logging adapters."""

    async def test_in_memory_audit_logger(self) -> None:
        """Test that InMemorySecurityAuditLogger captures decisions correctly."""
        logger = InMemorySecurityAuditLogger()

        correlation_id = uuid4()
        run_id = uuid4()

        # Log an input guard allow decision
        await logger.log_decision(
            event_type="input_guard",
            decision="allow",
            masked_content="hello world",
            warnings=[],
            correlation_id=correlation_id,
            run_id=run_id,
        )

        # Log an output guard decision with a secret
        secret_content = (
            "Here is my token: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
            "eyJzdWIiOiIxMjM0NTY3ODkwIn0.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
        )
        masked_content = mask_secrets(secret_content)
        await logger.log_decision(
            event_type="output_guard",
            decision="allow",
            masked_content=masked_content,
            warnings=[],
            correlation_id=correlation_id,
            run_id=run_id,
        )

        self.assertEqual(len(logger.entries), 2)

        entry1 = logger.entries[0]
        self.assertEqual(entry1.event_type, "input_guard")
        self.assertEqual(entry1.decision, "allow")
        self.assertEqual(entry1.masked_content, "hello world")
        self.assertEqual(entry1.correlation_id, correlation_id)
        self.assertEqual(entry1.run_id, run_id)
        self.assertEqual(entry1.warnings, [])

        entry2 = logger.entries[1]
        self.assertEqual(entry2.event_type, "output_guard")
        self.assertEqual(entry2.decision, "allow")
        self.assertIsNotNone(entry2.masked_content)
        masked_text = entry2.masked_content
        assert masked_text is not None
        self.assertNotIn("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9", masked_text)
        self.assertIn("[BEARER_TOKEN_MASKED]", masked_text)
        self.assertEqual(entry2.correlation_id, correlation_id)
        self.assertEqual(entry2.run_id, run_id)

    async def test_postgres_audit_logger_no_db(self) -> None:
        """PostgresSecurityAuditLogger is a no-op if db URL is None."""
        settings = Settings(database_url=None)
        logger = PostgresSecurityAuditLogger(settings)

        # Should not raise any exception
        await logger.log_decision(
            event_type="input_guard",
            decision="allow",
            masked_content="hello world",
            warnings=[],
        )
