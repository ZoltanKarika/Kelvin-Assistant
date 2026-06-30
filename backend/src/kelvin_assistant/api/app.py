"""FastAPI application factory."""

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from kelvin_assistant.adapters.memory_agent_runs import InMemoryAgentRunStore
from kelvin_assistant.adapters.memory_sessions import InMemorySessionStore
from kelvin_assistant.adapters.ollama import OllamaEmbeddingProvider, OllamaProvider
from kelvin_assistant.adapters.postgres import PostgresDatabaseClient
from kelvin_assistant.adapters.postgres_knowledge import PostgresKnowledgeRepository
from kelvin_assistant.adapters.postgres_memory import PostgresMemoryRepository
from kelvin_assistant.api.agent_routes import router as agent_router
from kelvin_assistant.api.chat_routes import router as chat_router
from kelvin_assistant.api.frontend_routes import FRONTEND_DIR
from kelvin_assistant.api.frontend_routes import router as frontend_router
from kelvin_assistant.api.memory_routes import router as memory_router
from kelvin_assistant.api.routes import router
from kelvin_assistant.application.agent import AgentService
from kelvin_assistant.application.chat import ChatService
from kelvin_assistant.application.knowledge_search import KnowledgeSearchService
from kelvin_assistant.application.memory import (
    MemoryService,
    RecentMemoryContextProvider,
)
from kelvin_assistant.application.tool_policy import DefaultToolPolicy
from kelvin_assistant.config.settings import Settings, get_settings
from kelvin_assistant.observability.logging import configure_logging
from kelvin_assistant.ports.agent_runs import AgentRunStore
from kelvin_assistant.ports.database import DatabaseClient
from kelvin_assistant.ports.llm import LLMProvider
from kelvin_assistant.ports.sessions import SessionStore
from kelvin_assistant.ports.workspaces import WorkspaceAuthorizer
from kelvin_assistant.tools.registry import StaticToolRegistry
from kelvin_assistant.tools.workspaces import StaticWorkspaceAuthorizer


def create_app(
    settings: Settings | None = None,
    llm_provider: LLMProvider | None = None,
    session_store: SessionStore | None = None,
    database_client: DatabaseClient | None = None,
    memory_service: MemoryService | None = None,
    agent_service: AgentService | None = None,
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
    active_agent_service = (
        agent_service
        if agent_service is not None
        else AgentService(DefaultToolPolicy(StaticToolRegistry()))
    )
    active_agent_run_store = (
        agent_run_store if agent_run_store is not None else InMemoryAgentRunStore()
    )
    active_workspace_authorizer = (
        workspace_authorizer
        if workspace_authorizer is not None
        else StaticWorkspaceAuthorizer(active_settings.agent_workspace_ids)
    )
    active_chat_service = ChatService(
        llm_provider=active_llm_provider,
        session_store=active_session_store,
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
    app.state.agent_run_store = active_agent_run_store
    app.state.workspace_authorizer = active_workspace_authorizer
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
    return app
