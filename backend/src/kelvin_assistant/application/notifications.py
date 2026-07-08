"""Notification services for email and external automation adapters."""

import logging
from uuid import UUID

from kelvin_assistant.config.settings import Settings
from kelvin_assistant.domain.agent import AgentRun, ToolProposal

logger = logging.getLogger(__name__)

# Deduplication set for sent approval notifications
_NOTIFIED_APPROVALS: set[UUID] = set()


def clear_notified_approvals() -> None:
    """Clear the deduplication cache (useful for testing)."""
    _NOTIFIED_APPROVALS.clear()


async def trigger_approval_notification(
    proposal: ToolProposal, settings: Settings
) -> None:
    """Send an email or n8n notification when a run requires user approval."""

    if (
        not settings.email_notifications_enabled
        or not settings.email_on_approval_required
    ):
        return

    recipient = settings.email_recipient
    if not recipient:
        logger.warning("No email recipient configured.")
        return

    tool_call_id = proposal.call.id
    if tool_call_id in _NOTIFIED_APPROVALS:
        return
    _NOTIFIED_APPROVALS.add(tool_call_id)

    subject = (
        f"Kelvin Assistant - Jóváhagyás szükséges (Futás ID: {proposal.run.id})"
    )
    body = (
        "Kedves Felhasználó!\n\n"
        "A Kelvin Assistant helyi ágens futása jóváhagyásra vár.\n\n"
        f"Futás azonosító: {proposal.run.id}\n"
        f"Cél: {proposal.run.goal}\n"
        f"Kockázati szint: {proposal.call.risk.value}\n"
        f"Kért művelet: {proposal.call.name}\n"
        f"Indoklás: {proposal.call.reason}\n\n"
        "Kérjük, ellenőrizze és bírálja el a kért műveletet a "
        "Kelvin Assistant helyi felületén:\n"
        "http://localhost:1025/ui/approvals\n\n"
        "Biztonsági okokból a kért művelet részletes paramétereit vagy "
        "a kódmódosításokat (diff) ez az e-mail nem tartalmazza."
    )

    await _send_notification(
        subject, body, "approval_required", str(proposal.run.id), settings
    )


async def trigger_run_completed_notification(
    run: AgentRun, summary: str, settings: Settings
) -> None:
    """Send an email or n8n notification when a run completes successfully."""

    if (
        not settings.email_notifications_enabled
        or not settings.email_on_run_completed
    ):
        return

    recipient = settings.email_recipient
    if not recipient:
        logger.warning("No email recipient configured.")
        return

    subject = f"Kelvin Assistant - Futás sikeresen befejeződött (ID: {run.id})"
    body = (
        "Kedves Felhasználó!\n\n"
        "A Kelvin Assistant ágens futása sikeresen befejeződött.\n\n"
        f"Futás azonosító: {run.id}\n"
        f"Cél: {run.goal}\n"
        f"Lépések száma: {run.step_count}/{run.max_steps}\n\n"
        "Összefoglaló:\n"
        f"{summary}\n\n"
        "Részletek megtekintése a helyi felületen:\n"
        "http://localhost:1025/ui/runs\n\n"
        "Biztonsági okokból a levél nem tartalmazza a nyers model "
        "válaszokat vagy érzékeny promptokat."
    )

    await _send_notification(
        subject, body, "run_completed", str(run.id), settings
    )


async def trigger_run_failed_notification(
    run: AgentRun, error_msg: str, settings: Settings
) -> None:
    """Send an email or n8n notification when a run fails."""

    if (
        not settings.email_notifications_enabled
        or not settings.email_on_run_failed
    ):
        return

    recipient = settings.email_recipient
    if not recipient:
        logger.warning("No email recipient configured.")
        return

    subject = f"Kelvin Assistant - Futás sikertelen (ID: {run.id})"
    body = (
        "Kedves Felhasználó!\n\n"
        "A Kelvin Assistant ágens futása meghiúsult vagy megszakadt.\n\n"
        f"Futás azonosító: {run.id}\n"
        f"Cél: {run.goal}\n"
        f"Státusz: {run.status.value}\n"
        f"Lépések száma: {run.step_count}/{run.max_steps}\n\n"
        "Hiba kategória / leírás:\n"
        f"{error_msg}\n\n"
        "Javasolt teendő:\n"
        "Ellenőrizze a futási naplót a helyi felületen és "
        "indítsa újra a futást szükség esetén:\n"
        "http://localhost:1025/ui/runs\n\n"
        "Biztonsági okokból a levél nem tartalmazza a nyers "
        "hibaüzeneteket vagy a részletes futási naplót."
    )

    await _send_notification(subject, body, "run_failed", str(run.id), settings)


async def _send_notification(
    subject: str,
    body: str,
    event_type: str,
    run_id: str,
    settings: Settings,
) -> None:
    recipient = settings.email_recipient
    if not recipient:
        return

    if settings.email_provider_mode == "n8n":
        if not settings.n8n_url:
            logger.warning("n8n URL is not configured for email notifications.")
            return
        try:
            import httpx2

            headers = {}
            if settings.n8n_token:
                headers["X-N8N-API-KEY"] = settings.n8n_token
            async with httpx2.AsyncClient(timeout=5.0) as client:
                await client.post(
                    settings.n8n_url,
                    headers=headers,
                    json={
                        "type": event_type,
                        "run_id": run_id,
                        "recipient": recipient,
                        "subject": subject,
                        "body": body,
                    },
                )
        except Exception as exc:
            logger.error(
                "Failed to delegate email notification to n8n: %s", exc
            )
    else:
        # SMTP
        import asyncio
        import smtplib
        from email.mime.text import MIMEText

        def send_email() -> None:
            msg = MIMEText(body)
            msg["Subject"] = subject
            msg["From"] = settings.email_sender
            msg["To"] = recipient

            with smtplib.SMTP(
                settings.email_smtp_host, settings.email_smtp_port, timeout=10
            ) as server:
                if settings.email_smtp_use_tls:
                    server.starttls()
                if (
                    settings.email_smtp_username
                    and settings.email_smtp_password
                ):
                    server.login(
                        settings.email_smtp_username,
                        settings.email_smtp_password,
                    )
                server.sendmail(
                    settings.email_sender,
                    [recipient],
                    msg.as_string(),
                )

        try:
            await asyncio.to_thread(send_email)
        except Exception as exc:
            logger.error("Failed to send SMTP email: %s", exc)
