"""FastAPI dependencies."""

from collections.abc import Callable, Coroutine
from typing import Any, Annotated, cast

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from kelvin_assistant.adapters.file_api_tokens import FileApiTokenAuthenticator
from kelvin_assistant.application.agent import AgentService
from kelvin_assistant.application.agent_planning import AgentPlanningService
from kelvin_assistant.application.chat import ChatService
from kelvin_assistant.application.memory import MemoryService
from kelvin_assistant.config.settings import Settings
from kelvin_assistant.domain.auth import ApiPrincipal, ApiScope
from kelvin_assistant.ports.agent_runs import AgentRunStore
from kelvin_assistant.ports.database import DatabaseClient
from kelvin_assistant.ports.llm import LLMProvider
from kelvin_assistant.ports.workspaces import WorkspaceAuthorizer

bearer_scheme = HTTPBearer(
    scheme_name="Kelvin API Token",
    description="A scope-limited API token for machine-to-machine authentication.",
)


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


def get_agent_planning_service(request: Request) -> AgentPlanningService:
    """Return the structured agent planning service."""

    service = getattr(request.app.state, "agent_planning_service", None)
    if not isinstance(service, AgentPlanningService):
        msg = "Agent planning service is not configured."
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


def get_api_authenticator(request: Request) -> FileApiTokenAuthenticator:
    """Return the API authenticator attached to the app state."""

    authenticator = getattr(request.app.state, "api_authenticator", None)
    if not isinstance(authenticator, FileApiTokenAuthenticator):
        msg = "API authenticator is not configured."
        raise RuntimeError(msg)
    return authenticator


async def get_current_principal(
    token: Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)],
    authenticator: Annotated[FileApiTokenAuthenticator, Depends(get_api_authenticator)],
) -> ApiPrincipal:
    """Authenticate a bearer token and return the resolved principal."""
    principal = authenticator.authenticate(token.credentials)
    if not principal:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return principal


class RequireScope:
    """Dependency that requires a specific API scope."""

    def __init__(self, scope: ApiScope) -> None:
        self.scope = scope

    async def __call__(
        self,
        principal: Annotated[ApiPrincipal, Depends(get_current_principal)],
    ) -> ApiPrincipal:
        """Return the principal if it has the required scope."""
        if not principal.has_scope(self.scope):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing required scope: {self.scope.value}",
            )
        return principal
