"""Versioned API routes for querying and updating application settings."""

from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status

from kelvin_assistant.api.dependencies import (
    get_runtime_settings,
    require_scope,
)
from kelvin_assistant.api.schemas import SettingsResponse, SettingsUpdateRequest
from kelvin_assistant.config.settings import Settings
from kelvin_assistant.domain.auth import ApiPrincipal, ApiScope

router = APIRouter(prefix="/api/v1/settings", tags=["settings"])

RuntimeSettings = Annotated[Settings, Depends(get_runtime_settings)]


def update_env_file(updates: dict[str, str]) -> None:
    """Read existing .env file, update matching keys, append new ones, write back."""
    env_path = Path(".env")
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

    # Apply to .env file
    if env_updates:
        update_env_file(env_updates)

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
        tool_policy_summary=tool_policy_summary,
        allowed_scopes=allowed_scopes,
        workspace_ids=workspace_ids,
    )
