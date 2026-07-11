"""Versioned API routes for querying and updating application settings."""

from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status

from kelvin_assistant.api.dependencies import (
    get_agent_run_store,
    get_runtime_settings,
    get_security_audit_logger,
    require_scope,
)
from kelvin_assistant.api.schemas import SettingsResponse, SettingsUpdateRequest
from kelvin_assistant.config.settings import Settings
from kelvin_assistant.domain.auth import ApiPrincipal, ApiScope
from kelvin_assistant.ports.agent_runs import AgentRunStore
from kelvin_assistant.ports.security_audit import SecurityAuditLogger

router = APIRouter(prefix="/api/v1/settings", tags=["settings"])

RuntimeSettings = Annotated[Settings, Depends(get_runtime_settings)]
RuntimeAgentRunStore = Annotated[AgentRunStore, Depends(get_agent_run_store)]
RuntimeSecurityAuditLogger = Annotated[
    SecurityAuditLogger, Depends(get_security_audit_logger)
]


DEFAULT_PRODUCTION_ENV_FILE = Path("/etc/kelvin-assistant/kelvin.env")


def settings_env_file_path(settings: Settings) -> Path:
    """Return the env file that should receive Settings UI updates."""

    if settings.settings_env_file is not None:
        return settings.settings_env_file
    if DEFAULT_PRODUCTION_ENV_FILE.exists():
        return DEFAULT_PRODUCTION_ENV_FILE
    return Path(".env")


def update_env_file(updates: dict[str, str], env_path: Path) -> None:
    """Read an env file, update matching keys, append new ones, write back."""
    lines = []
    if env_path.exists():
        lines = env_path.read_text(encoding="utf-8").splitlines()

    updated_keys = set()
    new_lines = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            new_lines.append(line)
            continue
        if "=" in stripped:
            key, val = stripped.split("=", 1)
            key = key.strip()
            if key in updates:
                new_lines.append(f"{key}={updates[key]}")
                updated_keys.add(key)
            else:
                new_lines.append(line)
        else:
            new_lines.append(line)

    for key, val in updates.items():
        if key not in updated_keys:
            new_lines.append(f"{key}={val}")

    env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


@router.get(
    "",
    response_model=SettingsResponse,
    status_code=status.HTTP_200_OK,
)
async def get_settings_endpoint(
    settings: RuntimeSettings,
    _principal: Annotated[ApiPrincipal, Depends(require_scope(ApiScope.SYSTEM_READ))],
) -> SettingsResponse:
    """Retrieve runtime settings and read-only policy summaries."""

    # Read-only summaries
    tool_policy_summary = (
        "Default local safety policy: read-only tools run automatically; "
        "write, destructive, or privileged tools require manual approval."
    )
    allowed_scopes = [scope.value for scope in ApiScope]
    workspace_ids = list(settings.agent_workspace_ids)

    return SettingsResponse(
        ollama_base_url=settings.ollama_base_url,
        ollama_model=settings.ollama_model,
        ollama_embedding_model=settings.ollama_embedding_model,
        system_prompt=settings.system_prompt,
        n8n_url=settings.n8n_url,
        n8n_token_configured=bool(settings.n8n_token),
        email_notifications_enabled=settings.email_notifications_enabled,
        email_smtp_host=settings.email_smtp_host,
        email_smtp_port=settings.email_smtp_port,
        email_smtp_username=settings.email_smtp_username,
        email_smtp_password_configured=bool(settings.email_smtp_password),
        email_smtp_use_tls=settings.email_smtp_use_tls,
        email_sender=settings.email_sender,
        email_recipient=settings.email_recipient,
        email_provider_mode=settings.email_provider_mode,
        email_daily_summary_time=settings.email_daily_summary_time,
        email_on_approval_required=settings.email_on_approval_required,
        email_on_run_completed=settings.email_on_run_completed,
        email_on_run_failed=settings.email_on_run_failed,
        email_on_daily_summary=settings.email_on_daily_summary,
        tool_policy_summary=tool_policy_summary,
        allowed_scopes=allowed_scopes,
        workspace_ids=workspace_ids,
    )


@router.put(
    "",
    response_model=SettingsResponse,
    status_code=status.HTTP_200_OK,
)
async def update_settings_endpoint(
    payload: SettingsUpdateRequest,
    settings: RuntimeSettings,
    _principal: Annotated[ApiPrincipal, Depends(require_scope(ApiScope.AGENT_APPROVE))],
) -> SettingsResponse:
    """Update runtime settings in-memory and write changes to .env file."""

    env_updates: dict[str, str] = {}
    in_memory_updates: dict[str, Any] = {}

    # Basic validations
    if payload.email_smtp_port is not None and not (
        1 <= payload.email_smtp_port <= 65535
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="SMTP Port must be between 1 and 65535",
        )

    # 1. Ollama Config
    if payload.ollama_base_url is not None:
        env_updates["KELVIN_OLLAMA_BASE_URL"] = payload.ollama_base_url
        in_memory_updates["ollama_base_url"] = payload.ollama_base_url

    if payload.ollama_model is not None:
        env_updates["KELVIN_OLLAMA_MODEL"] = payload.ollama_model
        in_memory_updates["ollama_model"] = payload.ollama_model

    if payload.ollama_embedding_model is not None:
        env_updates["KELVIN_OLLAMA_EMBEDDING_MODEL"] = payload.ollama_embedding_model
        in_memory_updates["ollama_embedding_model"] = payload.ollama_embedding_model

    # 2. System Prompt
    if payload.system_prompt is not None:
        if len(payload.system_prompt.strip()) == 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="System prompt cannot be empty",
            )
        env_updates["KELVIN_SYSTEM_PROMPT"] = payload.system_prompt
        in_memory_updates["system_prompt"] = payload.system_prompt

    # 3. n8n Integration
    if payload.n8n_url is not None:
        env_updates["KELVIN_N8N_URL"] = payload.n8n_url
        in_memory_updates["n8n_url"] = payload.n8n_url

    if payload.n8n_token is not None:
        # If payload.n8n_token is empty string, clear it.
        # If it is "keep" or "***", don't change.
        if payload.n8n_token.strip() == "":
            env_updates["KELVIN_N8N_TOKEN"] = ""
            in_memory_updates["n8n_token"] = None
        elif payload.n8n_token not in ("keep", "***"):
            env_updates["KELVIN_N8N_TOKEN"] = payload.n8n_token
            in_memory_updates["n8n_token"] = payload.n8n_token

    # 4. Email Notifications
    if payload.email_notifications_enabled is not None:
        env_updates["KELVIN_EMAIL_NOTIFICATIONS_ENABLED"] = str(
            payload.email_notifications_enabled
        )
        in_memory_updates["email_notifications_enabled"] = (
            payload.email_notifications_enabled
        )

    if payload.email_smtp_host is not None:
        env_updates["KELVIN_EMAIL_SMTP_HOST"] = payload.email_smtp_host
        in_memory_updates["email_smtp_host"] = payload.email_smtp_host

    if payload.email_smtp_port is not None:
        env_updates["KELVIN_EMAIL_SMTP_PORT"] = str(payload.email_smtp_port)
        in_memory_updates["email_smtp_port"] = payload.email_smtp_port

    if payload.email_smtp_username is not None:
        env_updates["KELVIN_EMAIL_SMTP_USERNAME"] = payload.email_smtp_username
        in_memory_updates["email_smtp_username"] = payload.email_smtp_username

    if payload.email_smtp_password is not None:
        if payload.email_smtp_password.strip() == "":
            env_updates["KELVIN_EMAIL_SMTP_PASSWORD"] = ""
            in_memory_updates["email_smtp_password"] = None
        elif payload.email_smtp_password not in ("keep", "***"):
            env_updates["KELVIN_EMAIL_SMTP_PASSWORD"] = payload.email_smtp_password
            in_memory_updates["email_smtp_password"] = payload.email_smtp_password

    if payload.email_smtp_use_tls is not None:
        env_updates["KELVIN_EMAIL_SMTP_USE_TLS"] = str(payload.email_smtp_use_tls)
        in_memory_updates["email_smtp_use_tls"] = payload.email_smtp_use_tls

    if payload.email_sender is not None:
        env_updates["KELVIN_EMAIL_SENDER"] = payload.email_sender
        in_memory_updates["email_sender"] = payload.email_sender

    if payload.email_recipient is not None:
        env_updates["KELVIN_EMAIL_RECIPIENT"] = payload.email_recipient
        in_memory_updates["email_recipient"] = payload.email_recipient

    if payload.email_provider_mode is not None:
        if payload.email_provider_mode not in ("smtp", "n8n"):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Provider mode must be 'smtp' or 'n8n'",
            )
        env_updates["KELVIN_EMAIL_PROVIDER_MODE"] = payload.email_provider_mode
        in_memory_updates["email_provider_mode"] = payload.email_provider_mode

    if payload.email_daily_summary_time is not None:
        env_updates["KELVIN_EMAIL_DAILY_SUMMARY_TIME"] = (
            payload.email_daily_summary_time
        )
        in_memory_updates["email_daily_summary_time"] = payload.email_daily_summary_time

    if payload.email_on_approval_required is not None:
        env_updates["KELVIN_EMAIL_ON_APPROVAL_REQUIRED"] = str(
            payload.email_on_approval_required
        )
        in_memory_updates["email_on_approval_required"] = (
            payload.email_on_approval_required
        )

    if payload.email_on_run_completed is not None:
        env_updates["KELVIN_EMAIL_ON_RUN_COMPLETED"] = str(
            payload.email_on_run_completed
        )
        in_memory_updates["email_on_run_completed"] = payload.email_on_run_completed

    if payload.email_on_run_failed is not None:
        env_updates["KELVIN_EMAIL_ON_RUN_FAILED"] = str(payload.email_on_run_failed)
        in_memory_updates["email_on_run_failed"] = payload.email_on_run_failed

    if payload.email_on_daily_summary is not None:
        env_updates["KELVIN_EMAIL_ON_DAILY_SUMMARY"] = str(
            payload.email_on_daily_summary
        )
        in_memory_updates["email_on_daily_summary"] = payload.email_on_daily_summary

    # Apply to .env file
    if env_updates:
        env_path = settings_env_file_path(settings)
        try:
            update_env_file(env_updates, env_path)
        except OSError as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to save settings file {env_path}: {exc}",
            ) from exc

    # Apply to in-memory active settings
    for key, val in in_memory_updates.items():
        setattr(settings, key, val)

    # Return refreshed settings
    tool_policy_summary = (
        "Default local safety policy: read-only tools run automatically; "
        "write, destructive, or privileged tools require manual approval."
    )
    allowed_scopes = [scope.value for scope in ApiScope]
    workspace_ids = list(settings.agent_workspace_ids)

    return SettingsResponse(
        ollama_base_url=settings.ollama_base_url,
        ollama_model=settings.ollama_model,
        ollama_embedding_model=settings.ollama_embedding_model,
        system_prompt=settings.system_prompt,
        n8n_url=settings.n8n_url,
        n8n_token_configured=bool(settings.n8n_token),
        email_notifications_enabled=settings.email_notifications_enabled,
        email_smtp_host=settings.email_smtp_host,
        email_smtp_port=settings.email_smtp_port,
        email_smtp_username=settings.email_smtp_username,
        email_smtp_password_configured=bool(settings.email_smtp_password),
        email_smtp_use_tls=settings.email_smtp_use_tls,
        email_sender=settings.email_sender,
        email_recipient=settings.email_recipient,
        email_provider_mode=settings.email_provider_mode,
        email_daily_summary_time=settings.email_daily_summary_time,
        email_on_approval_required=settings.email_on_approval_required,
        email_on_run_completed=settings.email_on_run_completed,
        email_on_run_failed=settings.email_on_run_failed,
        email_on_daily_summary=settings.email_on_daily_summary,
        tool_policy_summary=tool_policy_summary,
        allowed_scopes=allowed_scopes,
        workspace_ids=workspace_ids,
    )


@router.post(
    "/test-email",
    status_code=status.HTTP_200_OK,
)
async def send_test_email_endpoint(
    settings: RuntimeSettings,
    _principal: Annotated[ApiPrincipal, Depends(require_scope(ApiScope.AGENT_APPROVE))],
) -> dict[str, str]:
    """Send a minimal non-sensitive test message to verify SMTP connectivity."""

    if not settings.email_notifications_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email notifications are currently disabled in settings.",
        )

    recipient = settings.email_recipient
    if not recipient:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No email recipient configured.",
        )

    import asyncio
    import smtplib
    from email.mime.text import MIMEText

    def send_email() -> None:
        msg = MIMEText(
            "Ez egy automatikus tesztüzenet a Kelvin Assistant-től a hálózati "
            "SMTP kapcsolat ellenőrzésére. Kérjük, ne válaszoljon erre az e-mailre."
        )
        msg["Subject"] = "Kelvin Assistant SMTP Kapcsolat Teszt"
        msg["From"] = settings.email_sender
        msg["To"] = recipient

        with smtplib.SMTP(
            settings.email_smtp_host, settings.email_smtp_port, timeout=10
        ) as server:
            if settings.email_smtp_use_tls:
                server.starttls()
            if settings.email_smtp_username and settings.email_smtp_password:
                server.login(settings.email_smtp_username, settings.email_smtp_password)
            server.sendmail(
                settings.email_sender,
                [recipient],
                msg.as_string(),
            )

    try:
        await asyncio.to_thread(send_email)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to send email: {exc}",
        ) from exc

    return {"status": "success", "message": "Test email sent successfully."}


@router.post(
    "/send-summary",
    status_code=status.HTTP_200_OK,
)
async def send_summary_endpoint(
    store: RuntimeAgentRunStore,
    audit_logger: RuntimeSecurityAuditLogger,
    settings: RuntimeSettings,
    _principal: Annotated[ApiPrincipal, Depends(require_scope(ApiScope.AGENT_EXECUTE))],
) -> dict[str, str]:
    """Manually trigger and send the daily summary email now."""

    if not settings.email_notifications_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email notifications are currently disabled in settings.",
        )

    if not settings.email_recipient:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No email recipient configured.",
        )

    try:
        from kelvin_assistant.application.notifications import (
            trigger_daily_summary_notification,
        )

        # Force send (it ignores the email_on_daily_summary toggle for manual triggers)
        # We can temporarily override setting or construct a temporary setting
        force_settings = settings.model_copy(update={"email_on_daily_summary": True})
        await trigger_daily_summary_notification(store, audit_logger, force_settings)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to send daily summary: {exc}",
        ) from exc

    return {
        "status": "success",
        "message": "Daily summary email sent successfully.",
    }
