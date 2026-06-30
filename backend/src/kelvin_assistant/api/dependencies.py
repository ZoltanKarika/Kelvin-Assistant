"""FastAPI dependencies."""

from typing import cast

from fastapi import Request

from kelvin_assistant.application.agent import AgentService
from kelvin_assistant.application.chat import ChatService
from kelvin_assistant.application.memory import MemoryService
from kelvin_assistant.config.settings import Settings
from kelvin_assistant.ports.agent_runs import AgentRunStore
from kelvin_assistant.ports.database import DatabaseClient
from kelvin_assistant.ports.llm import LLMProvider
from kelvin_assistant.ports.workspaces import WorkspaceAuthorizer


def get_runtime_settings(request: Request) -> Settings:
    """Return the settings object attached to the app state."""

    settings = getattr(request.app.state, "settings", None)
    if not isinstance(settings, Settings):
        msg = "Application settings are not configured."
        raise RuntimeError(msg)
    return settings


def get_llm_provider(request: Request) -> LLMProvider:
    """Return the language model provider attached to the app state."""

    provider = getattr(request.app.state, "llm_provider", None)
    if provider is None:
        msg = "Language model provider is not configured."
        raise RuntimeError(msg)
    return cast(LLMProvider, provider)


def get_database_client(request: Request) -> DatabaseClient:
    """Return the database client attached to the app state."""

    client = getattr(request.app.state, "database_client", None)
    if client is None:
        msg = "Database client is not configured."
        raise RuntimeError(msg)
    return cast(DatabaseClient, client)


def get_chat_service(request: Request) -> ChatService:
    """Return the chat application service attached to the app state."""

    service = getattr(request.app.state, "chat_service", None)
    if not isinstance(service, ChatService):
        msg = "Chat service is not configured."
        raise RuntimeError(msg)
    return service


def get_memory_service(request: Request) -> MemoryService:
    """Return the memory application service attached to the app state."""

    service = getattr(request.app.state, "memory_service", None)
    if not isinstance(service, MemoryService):
        msg = "Memory service is not configured."
        raise RuntimeError(msg)
    return service


def get_agent_service(request: Request) -> AgentService:
    """Return the agent application service attached to the app state."""

    service = getattr(request.app.state, "agent_service", None)
    if not isinstance(service, AgentService):
        msg = "Agent service is not configured."
        raise RuntimeError(msg)
    return service


def get_agent_run_store(request: Request) -> AgentRunStore:
    """Return the agent run store attached to the app state."""

    store = getattr(request.app.state, "agent_run_store", None)
    if store is None:
        msg = "Agent run store is not configured."
        raise RuntimeError(msg)
    return cast(AgentRunStore, store)


def get_workspace_authorizer(request: Request) -> WorkspaceAuthorizer:
    """Return the configured workspace authorizer."""

    authorizer = getattr(request.app.state, "workspace_authorizer", None)
    if authorizer is None:
        msg = "Workspace authorizer is not configured."
        raise RuntimeError(msg)
    return cast(WorkspaceAuthorizer, authorizer)
