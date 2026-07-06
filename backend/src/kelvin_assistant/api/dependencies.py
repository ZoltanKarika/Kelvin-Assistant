"""FastAPI dependencies."""

from collections.abc import Callable
from typing import Annotated, cast

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from kelvin_assistant.adapters.file_api_tokens import FileApiTokenAuthenticator
from kelvin_assistant.application.agent import AgentService
from kelvin_assistant.application.agent_planning import AgentPlanningService
from kelvin_assistant.application.chat import ChatService
from kelvin_assistant.application.memory import MemoryService
from kelvin_assistant.config.settings import Settings
from kelvin_assistant.domain.auth import ApiPrincipal, ApiScope
from kelvin_assistant.domain.input_guard import InputGuard
from kelvin_assistant.ports.agent_runs import AgentRunStore
from kelvin_assistant.ports.database import DatabaseClient
from kelvin_assistant.ports.llm import LLMProvider
from kelvin_assistant.ports.workspaces import WorkspaceAuthorizer

# A sentinel principal used when auth is disabled (development mode).
# It has every scope so no route is inadvertently blocked.
_ANON_PRINCIPAL = ApiPrincipal(
    id="anonymous",
    scopes=frozenset(ApiScope),
)

# FastAPI's built-in Bearer extractor. auto_error=False means we get None
# instead of an automatic 403 when the header is absent — we produce our own
# 401 with the correct WWW-Authenticate header below.
_bearer_scheme = HTTPBearer(auto_error=False)


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


def get_api_token_authenticator(
    request: Request,
) -> FileApiTokenAuthenticator | None:
    """Return the API token authenticator, or None when auth is disabled."""

    return cast(
        FileApiTokenAuthenticator | None,
        getattr(request.app.state, "api_token_authenticator", None),
    )


def get_input_guard(request: Request) -> InputGuard:
    """Return the input guard attached to the app state."""

    service = getattr(request.app.state, "input_guard", None)
    if not isinstance(service, InputGuard):
        msg = "Input guard is not configured."
        raise RuntimeError(msg)
    return service


# Type alias for the inner dependency function produced by require_scope.
_ScopedDependency = Callable[
    [HTTPAuthorizationCredentials | None, FileApiTokenAuthenticator | None],
    ApiPrincipal,
]


def require_scope(scope: ApiScope) -> _ScopedDependency:
    """Return a FastAPI dependency that enforces one required API scope.

    Usage::

        @router.post("/chat")
        async def create_chat(
            principal: Annotated[
                ApiPrincipal, Depends(require_scope(ApiScope.CHAT_USE))
            ],
            ...
        ) -> ...: ...

    When ``KELVIN_API_AUTH_MODE=disabled`` (the development default) every
    request is treated as the anonymous all-scopes principal and no token is
    required.  When ``KELVIN_API_AUTH_MODE=required`` the caller **must**
    supply a valid Bearer token with the named scope or receive 401/403.
    """

    def _check(
        credentials: Annotated[
            HTTPAuthorizationCredentials | None,
            Depends(_bearer_scheme),
        ],
        authenticator: Annotated[
            FileApiTokenAuthenticator | None,
            Depends(get_api_token_authenticator),
        ],
    ) -> ApiPrincipal:
        # Auth is disabled: every caller is trusted with all scopes.
        if authenticator is None:
            return _ANON_PRINCIPAL

        # Auth is enabled but the header is missing.
        if credentials is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing Bearer token.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        principal = authenticator.authenticate(credentials.credentials)

        if principal is None:
            # Token was present but rejected (bad hash).
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired Bearer token.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if not principal.has_scope(scope):
            # Valid token but the principal lacks the required scope.
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing required scope: {scope.value}.",
            )

        return principal

    return _check
