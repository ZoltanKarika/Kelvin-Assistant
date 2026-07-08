"""Notification services for email and external automation adapters."""

import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID

from kelvin_assistant.config.settings import Settings
from kelvin_assistant.domain.agent import AgentRun, AgentStatus, ToolProposal
from kelvin_assistant.domain.output_guard import mask_secrets
from kelvin_assistant.ports.agent_runs import AgentRunStore
from kelvin_assistant.ports.security_audit import SecurityAuditLogger

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

    subject = f"Kelvin Assistant - Jóváhagyás szükséges (Futás ID: {proposal.run.id})"
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

    if not settings.email_notifications_enabled or not settings.email_on_run_completed:
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

    await _send_notification(subject, body, "run_completed", str(run.id), settings)


async def trigger_run_failed_notification(
    run: AgentRun, error_msg: str, settings: Settings
) -> None:
    """Send an email or n8n notification when a run fails."""

    if not settings.email_notifications_enabled or not settings.email_on_run_failed:
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


async def generate_daily_summary_text(
    store: AgentRunStore,
    audit_logger: SecurityAuditLogger,
    n8n_url: str | None,
    n8n_token: str | None,
) -> str:
    """Generate a clean, safe, and localized plain text daily summary."""
    now = datetime.now(UTC)
    day_ago = now - timedelta(days=1)

    # 1. Fetch runs
    all_runs = await store.list_runs()
    daily_runs = [
        r for r in all_runs if r.created_at is not None and r.created_at >= day_ago
    ]

    total_count = len(daily_runs)
    completed_runs = [r for r in daily_runs if r.status == AgentStatus.COMPLETED]
    failed_runs = [r for r in daily_runs if r.status == AgentStatus.FAILED]
    pending_approvals = [
        r for r in daily_runs if r.status == AgentStatus.AWAITING_APPROVAL
    ]

    # 2. Fetch notable audit events
    all_audit = await audit_logger.list_entries(limit=500)
    daily_audit = [
        e for e in all_audit if e.created_at is not None and e.created_at >= day_ago
    ]
    blocked_count = sum(1 for e in daily_audit if e.decision == "block")

    # 3. Check n8n status
    n8n_status = "Nincs konfigurálva"
    if n8n_url:
        try:
            import httpx2

            headers = {}
            if n8n_token:
                headers["X-N8N-API-KEY"] = n8n_token
            async with httpx2.AsyncClient(timeout=3.0) as client:
                res = await client.get(n8n_url, headers=headers)
                if res.status_code >= 500:
                    n8n_status = f"Degradált (HTTP {res.status_code})"
                else:
                    n8n_status = "Elérhető / Egészséges"
        except Exception:
            n8n_status = "Nem elérhető (Kapcsolódási hiba)"

    # 4. Format localized text
    lines = [
        "==================================================",
        "          KELVIN ASSISTANT NAPI ÖSSZEGFOGLALÓ     ",
        "==================================================",
        f"Készült: {now.strftime('%Y-%m-%d %H:%M:%S')} (UTC)",
        (
            f"Időszak: {day_ago.strftime('%Y-%m-%d %H:%M:%S')} - "
            f"{now.strftime('%Y-%m-%d %H:%M:%S')}"
        ),
        "",
        "--- 1. Futási statisztikák ---",
        f"Összes indított futás: {total_count}",
        f"Sikeresen befejeződött: {len(completed_runs)}",
        f"Meghiúsult / elakadt: {len(failed_runs)}",
        f"Jóváhagyásra vár: {len(pending_approvals)}",
        "",
    ]

    if failed_runs:
        lines.append("Meghiúsult futások részletei:")
        for r in failed_runs:
            lines.append(f"  - Futás ID: {r.id}")
            lines.append(f"    Cél: {r.goal}")
        lines.append("")

    if pending_approvals:
        lines.append("Jóváhagyásra váró futások részletei:")
        for r in pending_approvals:
            lines.append(f"  - Futás ID: {r.id}")
            lines.append(f"    Cél: {r.goal}")
        lines.append("")

    lines.extend(
        [
            "--- 2. Biztonsági audit ---",
            f"Blokkolt ágens műveletek száma: {blocked_count}",
            f"Összes biztonsági ellenőrzés: {len(daily_audit)}",
            "",
            "--- 3. Rendszerállapot ---",
            f"n8n Integrációs Réteg: {n8n_status}",
            "==================================================",
            "Biztonsági okokból ez az összefoglaló nem tartalmazza a nyers model",
            "válaszokat, érzékeny promptokat vagy kódmódosítási diffeket.",
        ]
    )

    return "\n".join(lines)


async def trigger_daily_summary_notification(
    store: AgentRunStore,
    audit_logger: SecurityAuditLogger,
    settings: Settings,
) -> None:
    """Generate and send the daily operational summary notification."""

    if not settings.email_notifications_enabled or not settings.email_on_daily_summary:
        return

    recipient = settings.email_recipient
    if not recipient:
        logger.warning("No email recipient configured.")
        return

    subject = (
        f"Kelvin Assistant - Napi Rendszerösszefoglaló "
        f"({datetime.now(UTC).strftime('%Y-%m-%d')})"
    )
    body = await generate_daily_summary_text(
        store, audit_logger, settings.n8n_url, settings.n8n_token
    )

    await _send_notification(subject, body, "daily_summary", "system", settings)


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

    safe_body = mask_secrets(body) or ""

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
                        "body": safe_body,
                    },
                )
        except Exception as exc:
            logger.error("Failed to delegate email notification to n8n: %s", exc)
    else:
        # SMTP
        import asyncio
        import smtplib
        from email.mime.text import MIMEText

        def send_email() -> None:
            msg = MIMEText(safe_body)
            msg["Subject"] = subject
            msg["From"] = settings.email_sender
            msg["To"] = recipient

            with smtplib.SMTP(
                settings.email_smtp_host, settings.email_smtp_port, timeout=10
            ) as server:
                if settings.email_smtp_use_tls:
                    server.starttls()
                if settings.email_smtp_username and settings.email_smtp_password:
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
