"""Unit tests for approval pending email/n8n notifications."""

import unittest
from unittest.mock import MagicMock, patch
from uuid import uuid4

from kelvin_assistant.application.notifications import (
    clear_notified_approvals,
    trigger_approval_notification,
)
from kelvin_assistant.config.settings import Settings
from kelvin_assistant.domain.agent import (
    AgentRun,
    AgentStatus,
    ToolApproval,
    ToolCall,
    ToolPolicyDecision,
    ToolPolicyResult,
    ToolProposal,
    ToolRisk,
)


def _create_proposal() -> ToolProposal:
    run = AgentRun(
        id=uuid4(),
        goal="Test running agent tasks securely",
        status=AgentStatus.AWAITING_APPROVAL,
        step_count=1,
        max_steps=10,
        version=1,
    )
    call = ToolCall(
        id=uuid4(),
        name="fs.delete",
        arguments={"path": "/important/dir"},
        reason="Clean up workspace",
        expected_effect="Files deleted",
        risk=ToolRisk.DESTRUCTIVE,
    )
    policy_result = ToolPolicyResult(
        decision=ToolPolicyDecision.REQUIRE_APPROVAL,
        reason="Destructive write action requires explicit user permission.",
    )
    return ToolProposal(
        run=run,
        call=call,
        policy_result=policy_result,
        approval=ToolApproval(tool_call_id=call.id),
    )


class TestNotifications(unittest.IsolatedAsyncioTestCase):
    """Test suite for approval pending notification trigger logic."""

    def setUp(self) -> None:
        """Clear cache before each test."""
        clear_notified_approvals()

    def tearDown(self) -> None:
        """Clear cache after each test."""
        clear_notified_approvals()

    @patch("smtplib.SMTP")
    async def test_trigger_approval_smtp_success(
        self, mock_smtp_class: MagicMock
    ) -> None:
        """SMTP email notification is sent with correct details and

        no sensitive diffs.
        """

        settings = Settings(
            email_notifications_enabled=True,
            email_on_approval_required=True,
            email_provider_mode="smtp",
            email_sender="kelvin@localhost",
            email_recipient="recipient@test.local",
            email_smtp_host="smtp.test",
            email_smtp_port=587,
            email_smtp_username="user",
            email_smtp_password="password",
            email_smtp_use_tls=True,
        )

        proposal = _create_proposal()

        # Setup mock SMTP server instance
        mock_server = MagicMock()
        mock_smtp_class.return_value.__enter__.return_value = mock_server

        await trigger_approval_notification(proposal, settings)

        # Verify SMTP server lifecycle
        mock_smtp_class.assert_called_once_with("smtp.test", 587, timeout=10)
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once_with("user", "password")
        mock_server.sendmail.assert_called_once()

        # Verify email payload
        sendmail_args = mock_server.sendmail.call_args[0]
        assert sendmail_args[0] == "kelvin@localhost"
        assert sendmail_args[1] == ["recipient@test.local"]

        import email

        msg = email.message_from_string(sendmail_args[2])
        payload = msg.get_payload(decode=True)
        assert isinstance(payload, bytes)
        body = payload.decode("utf-8")
        # Check that required identifiers are present
        assert str(proposal.run.id) in body
        assert "Test running agent tasks securely" in body
        assert "fs.delete" in body
        assert "Clean up workspace" in body
        assert "destructive" in body.lower()
        assert "/ui/approvals" in body

        # Check that sensitive details like raw tool arguments or diffs are redacted
        assert "/important/dir" not in body

    @patch("httpx2.AsyncClient.post")
    async def test_trigger_approval_n8n_success(self, mock_post: MagicMock) -> None:
        """n8n webhook notification is sent when n8n provider is configured."""

        settings = Settings(
            email_notifications_enabled=True,
            email_on_approval_required=True,
            email_provider_mode="n8n",
            email_recipient="recipient@test.local",
            n8n_url="http://mock-n8n:5678/webhook/notify",
            n8n_token="n8n-token",
        )

        proposal = _create_proposal()

        # Mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        await trigger_approval_notification(proposal, settings)

        # Verify n8n webhook post
        mock_post.assert_called_once()
        post_args = mock_post.call_args
        assert post_args[0][0] == "http://mock-n8n:5678/webhook/notify"
        assert post_args[1]["headers"] == {"X-N8N-API-KEY": "n8n-token"}

        payload = post_args[1]["json"]
        assert payload["type"] == "approval_required"
        assert payload["run_id"] == str(proposal.run.id)
        assert payload["recipient"] == "recipient@test.local"
        assert "fs.delete" in payload["body"]
        assert "/important/dir" not in payload["body"]

    @patch("smtplib.SMTP")
    async def test_trigger_approval_deduplication(
        self, mock_smtp_class: MagicMock
    ) -> None:
        """Duplicate notifications for the same tool call ID are ignored."""

        settings = Settings(
            email_notifications_enabled=True,
            email_on_approval_required=True,
            email_provider_mode="smtp",
            email_recipient="recipient@test.local",
        )

        proposal = _create_proposal()
        mock_server = MagicMock()
        mock_smtp_class.return_value.__enter__.return_value = mock_server

        # First call: triggers email
        await trigger_approval_notification(proposal, settings)
        assert mock_smtp_class.call_count == 1

        # Second call for the same proposal: ignored
        await trigger_approval_notification(proposal, settings)
        assert mock_smtp_class.call_count == 1

    @patch("smtplib.SMTP")
    async def test_trigger_approval_disabled(self, mock_smtp_class: MagicMock) -> None:
        """Notifications are ignored if toggled off."""

        # Disabled globally
        settings_disabled = Settings(
            email_notifications_enabled=False,
            email_on_approval_required=True,
            email_provider_mode="smtp",
            email_recipient="recipient@test.local",
        )

        proposal = _create_proposal()
        await trigger_approval_notification(proposal, settings_disabled)
        assert mock_smtp_class.call_count == 0

        # Disabled individually
        settings_toggled_off = Settings(
            email_notifications_enabled=True,
            email_on_approval_required=False,
            email_provider_mode="smtp",
            email_recipient="recipient@test.local",
        )
        await trigger_approval_notification(proposal, settings_toggled_off)
        assert mock_smtp_class.call_count == 0
