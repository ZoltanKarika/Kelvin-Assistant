"""FastAPI application factory."""

import ipaddress
import logging
import uuid
from collections.abc import Awaitable, Callable, Sequence
from pathlib import Path
from typing import TypedDict

from fastapi import FastAPI, Request
from fastapi.responses import Response, StreamingResponse
from fastapi.staticfiles import StaticFiles

from kelvin_assistant.adapters.file_api_tokens import FileApiTokenAuthenticator
from kelvin_assistant.adapters.llm_planner import StructuredLLMAgentPlanner
from kelvin_assistant.adapters.memory_agent_runs import InMemoryAgentRunStore
from kelvin_assistant.adapters.memory_security_audit import InMemorySecurityAuditLogger
from kelvin_assistant.adapters.memory_sessions import InMemorySessionStore
from kelvin_assistant.adapters.ollama import OllamaEmbeddingProvider, OllamaProvider
from kelvin_assistant.adapters.postgres import PostgresDatabaseClient
from kelvin_assistant.adapters.postgres_agent_runs import PostgresAgentRunStore
from kelvin_assistant.adapters.postgres_knowledge import PostgresKnowledgeRepository
from kelvin_assistant.adapters.postgres_memory import PostgresMemoryRepository
from kelvin_assistant.adapters.postgres_security_audit import (
    PostgresSecurityAuditLogger,
)
from kelvin_assistant.api.agent_routes import router as agent_router
from kelvin_assistant.api.chat_routes import router as chat_router
from kelvin_assistant.api.frontend_routes import FRONTEND_DIR
from kelvin_assistant.api.frontend_routes import router as frontend_router
from kelvin_assistant.api.memory_routes import router as memory_router
from kelvin_assistant.api.routes import router
from kelvin_assistant.application.agent import AgentService
from kelvin_assistant.application.agent_planning import AgentPlanningService
from kelvin_assistant.application.chat import ChatService
from kelvin_assistant.application.knowledge_search import KnowledgeSearchService
from kelvin_assistant.application.memory import (
    MemoryService,
    RecentMemoryContextProvider,
)
from kelvin_assistant.application.tool_policy import DefaultToolPolicy
from kelvin_assistant.config.settings import Settings, get_settings
from kelvin_assistant.domain.context_guard import ContextGuard
from kelvin_assistant.domain.input_guard import InputGuard
from kelvin_assistant.observability.logging import configure_logging
from kelvin_assistant.ports.agent_runs import AgentRunStore
from kelvin_assistant.ports.database import DatabaseClient
from kelvin_assistant.ports.llm import LLMProvider
from kelvin_assistant.ports.planner import AgentPlanner
from kelvin_assistant.ports.sessions import SessionStore
from kelvin_assistant.ports.workspaces import WorkspaceAuthorizer
from kelvin_assistant.tools.read_definitions import read_tool_definitions
from kelvin_assistant.tools.registry import StaticToolRegistry
from kelvin_assistant.tools.workspaces import StaticWorkspaceAuthorizer
from kelvin_assistant.tools.write_definitions import write_tool_definitions

LOGGER = logging.getLogger(__name__)

# Sentinel that distinguishes "caller passed no authenticator" (use settings)
# from "caller explicitly passed None" (disable auth for this app instance).
_NOT_PROVIDED: FileApiTokenAuthenticator | None = object()  # type: ignore[assignment]


class CachedResponse(TypedDict):
    content: bytes
    status_code: int
    media_type: str | None
    headers: dict[str, str]


def create_app(
    settings: Settings | None = None,
    llm_provider: LLMProvider | None = None,
    session_store: SessionStore | None = None,
    database_client: DatabaseClient | None = None,
    api_authenticator: FileApiTokenAuthenticator | None = _NOT_PROVIDED,
    memory_service: MemoryService | None = None,
    agent_service: AgentService | None = None,
    agent_planner: AgentPlanner | None = None,
    agent_run_store: AgentRunStore | None = None,
    workspace_authorizer: WorkspaceAuthorizer | None = None,
) -> FastAPI:
    """Create and configure the FastAPI application."""

    active_settings = settings or get_settings()
    active_llm_provider = (
        llm_provider if llm_provider is not None else OllamaProvider(active_settings)
    )
    active_session_store = (
        session_store if session_store is not None else InMemorySessionStore()
    )
    active_database_client = (
        database_client
        if database_client is not None
        else PostgresDatabaseClient(active_settings)
    )

    # Build the API token authenticator.
    # Priority: explicit constructor arg > settings file > disabled.
    # When auth is "required", the token file must be present and valid at
    # startup.  A missing or malformed file is a hard failure (fail-closed).
    # When auth is "disabled" (the development default), we store None and the
    # security dependency skips all checks.
    # If api_authenticator is explicitly provided (including None), use it
    # directly and skip the settings-based logic entirely — useful for tests.
    active_api_authenticator: FileApiTokenAuthenticator | None
    if api_authenticator is not _NOT_PROVIDED:
        active_api_authenticator = api_authenticator
        if api_authenticator is not None:
            LOGGER.info("API authentication enabled via injected authenticator")
        else:
            LOGGER.info("API authentication disabled (injected None)")
    elif active_settings.api_auth_mode == "required":
        if active_settings.api_token_file is None:
            raise RuntimeError(
                "KELVIN_API_TOKEN_FILE must be set when KELVIN_API_AUTH_MODE=required"
            )
        active_api_authenticator = FileApiTokenAuthenticator.from_file(
            Path(active_settings.api_token_file)
        )
        LOGGER.info(
            "API authentication enabled; token file: %s",
            active_settings.api_token_file,
        )
    else:
        active_api_authenticator = None
        LOGGER.info("API authentication disabled (development mode)")

    knowledge_context_provider = (
        KnowledgeSearchService(
            embedding_provider=OllamaEmbeddingProvider(active_settings),
            repository=PostgresKnowledgeRepository(active_settings),
            collection_name=active_settings.rag_collection,
            embedding_model=active_settings.ollama_embedding_model,
            result_limit=active_settings.rag_result_limit,
        )
        if active_settings.rag_enabled
        else None
    )
    active_memory_service = (
        memory_service
        if memory_service is not None
        else MemoryService(PostgresMemoryRepository(active_settings))
    )
    active_tool_registry = StaticToolRegistry(
        (*read_tool_definitions(), *write_tool_definitions())
    )
    active_agent_service = (
        agent_service
        if agent_service is not None
        else AgentService(DefaultToolPolicy(active_tool_registry))
    )
    active_agent_planner = (
        agent_planner
        if agent_planner is not None
        else StructuredLLMAgentPlanner(active_llm_provider)
    )
    active_input_guard = InputGuard()
    active_context_guard = ContextGuard(active_input_guard)
    active_security_audit_logger = (
        PostgresSecurityAuditLogger(active_settings)
        if active_settings.database_url is not None
        else InMemorySecurityAuditLogger()
    )
    active_agent_planning_service = AgentPlanningService(
        planner=active_agent_planner,
        registry=active_tool_registry,
        agent_service=active_agent_service,
        context_guard=active_context_guard,
    )
    active_agent_run_store = (
        agent_run_store
        if agent_run_store is not None
        else (
            PostgresAgentRunStore(active_settings)
            if active_settings.database_url is not None
            else InMemoryAgentRunStore()
        )
    )
    active_workspace_authorizer = (
        workspace_authorizer
        if workspace_authorizer is not None
        else StaticWorkspaceAuthorizer(active_settings.agent_workspace_ids)
    )
    active_chat_service = ChatService(
        llm_provider=active_llm_provider,
        session_store=active_session_store,
        context_guard=active_context_guard,
        system_prompt=active_settings.system_prompt,
        knowledge_context_provider=knowledge_context_provider,
        memory_context_provider=(
            RecentMemoryContextProvider(active_memory_service)
            if active_settings.database_url is not None
            else None
        ),
    )
    configure_logging(active_settings)

    app = FastAPI(
        title=active_settings.app_name,
        version=active_settings.app_version,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )
    app.state.settings = active_settings
    app.state.llm_provider = active_llm_provider
    app.state.database_client = active_database_client
    app.state.chat_service = active_chat_service
    app.state.memory_service = active_memory_service
    app.state.agent_service = active_agent_service
    app.state.agent_planning_service = active_agent_planning_service
    app.state.agent_run_store = active_agent_run_store
    app.state.workspace_authorizer = active_workspace_authorizer
    app.state.api_token_authenticator = active_api_authenticator
    app.state.input_guard = active_input_guard
    app.state.security_audit_logger = active_security_audit_logger
    app.mount(
        "/static",
        StaticFiles(directory=FRONTEND_DIR),
        name="static",
    )
    app.include_router(router)
    app.include_router(chat_router)
    app.include_router(memory_router)
    app.include_router(agent_router)
    app.include_router(frontend_router)

    idempotency_store: dict[str, CachedResponse] = {}

    @app.middleware("http")
    async def enforce_network_and_idempotency(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        # 1. Enforce Client IP Allowlist
        settings = request.app.state.settings
        client_host = None
        x_forwarded_for = request.headers.get("X-Forwarded-For")
        if x_forwarded_for:
            client_host = x_forwarded_for.split(",")[0].strip()
        else:
            client_host = request.headers.get("X-Real-IP")

        if not client_host:
            client_host = request.client.host if request.client else None

        if settings.allowed_clients:
            if not client_host or not _is_ip_allowed(
                client_host, settings.allowed_clients
            ):
                return Response(
                    content="Forbidden: client IP not allowed.",
                    status_code=403,
                )

        # 2. Enforce Idempotency for POST runs endpoints
        if request.method == "POST" and "/runs" in request.url.path:
            key = request.headers.get("X-Idempotency-Key")
            if key:
                if key in idempotency_store:
                    cached = idempotency_store[key]
                    return Response(
                        content=cached["content"],
                        status_code=cached["status_code"],
                        media_type=cached["media_type"],
                        headers=cached["headers"],
                    )

                response = await call_next(request)

                if response.status_code < 500:
                    response_body = b""
                    if hasattr(response, "body_iterator"):
                        async for chunk in getattr(response, "body_iterator"):
                            if isinstance(chunk, str):
                                response_body += chunk.encode("utf-8")
                            else:
                                response_body += bytes(chunk)
                    else:
                        response_body = bytes(response.body)

                    idempotency_store[key] = {
                        "content": response_body,
                        "status_code": response.status_code,
                        "media_type": response.media_type,
                        "headers": {
                            k: v
                            for k, v in response.headers.items()
                            if k.lower() != "content-length"
                        },
                    }
                    return Response(
                        content=response_body,
                        status_code=response.status_code,
                        media_type=response.media_type,
                        headers=idempotency_store[key]["headers"],
                    )
                return response

        return await call_next(request)

    @app.middleware("http")
    async def dispatch_correlation_id(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """
        Injects a correlation ID into the request state and response headers.
        """
        correlation_id = request.headers.get("X-Correlation-ID")
        if correlation_id is None:
            correlation_id = str(uuid.uuid4())

        request.state.correlation_id = correlation_id

        response = await call_next(request)
        response.headers["X-Correlation-ID"] = correlation_id

        return response

    return app


def _is_ip_allowed(client_ip_str: str, allowed_clients: Sequence[str]) -> bool:
    if not allowed_clients:
        return True
    try:
        client_ip = ipaddress.ip_address(client_ip_str)
    except ValueError:
        return False

    for pattern in allowed_clients:
        try:
            if "/" in pattern:
                network = ipaddress.ip_network(pattern, strict=False)
                if client_ip in network:
                    return True
            else:
                addr = ipaddress.ip_address(pattern)
                if client_ip == addr:
                    return True
        except ValueError:
            if client_ip_str == pattern:
                return True
    return False
