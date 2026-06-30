"""Versioned API routes for server-managed agent runs."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from kelvin_assistant.api.dependencies import (
    get_agent_run_store,
    get_agent_service,
)
from kelvin_assistant.api.schemas import AgentRunCreateRequest, AgentRunResponse
from kelvin_assistant.application.agent import AgentService, AgentServiceError
from kelvin_assistant.domain.agent import AgentDomainError, AgentRun
from kelvin_assistant.ports.agent_runs import (
    AgentRunConflictError,
    AgentRunNotFoundError,
    AgentRunStore,
)

router = APIRouter(prefix="/api/v1/agent", tags=["agent"])
RuntimeAgentService = Annotated[AgentService, Depends(get_agent_service)]
RuntimeAgentRunStore = Annotated[AgentRunStore, Depends(get_agent_run_store)]
UNPROCESSABLE_CONTENT = 422


@router.post(
    "/runs",
    response_model=AgentRunResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        UNPROCESSABLE_CONTENT: {"description": "Invalid agent goal."},
        status.HTTP_409_CONFLICT: {"description": "Agent run already exists."},
    },
)
async def create_agent_run(
    request: AgentRunCreateRequest,
    service: RuntimeAgentService,
    store: RuntimeAgentRunStore,
) -> AgentRunResponse:
    """Create and persist one received agent run."""

    try:
        run = service.start_run(request.goal, max_steps=request.max_steps)
        await store.add(run)
    except AgentDomainError as exc:
        raise HTTPException(
            status_code=UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    except AgentRunConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    return _agent_run_response(run)


@router.get(
    "/runs/{run_id}",
    response_model=AgentRunResponse,
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Agent run not found."},
    },
)
async def get_agent_run(
    run_id: UUID,
    store: RuntimeAgentRunStore,
) -> AgentRunResponse:
    """Return the current server-managed state of one agent run."""

    try:
        run = await store.get(run_id)
    except AgentRunNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    return _agent_run_response(run)


@router.post(
    "/runs/{run_id}/plan",
    response_model=AgentRunResponse,
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Agent run not found."},
        status.HTTP_409_CONFLICT: {
            "description": "Invalid or concurrent agent transition.",
        },
    },
)
async def begin_agent_planning(
    run_id: UUID,
    service: RuntimeAgentService,
    store: RuntimeAgentRunStore,
) -> AgentRunResponse:
    """Move one received or clarified run into planning."""

    try:
        current = await store.get(run_id)
        planned = service.begin_planning(current)
        await store.update(planned, expected_version=current.version)
    except AgentRunNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except (AgentServiceError, AgentRunConflictError) as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    return _agent_run_response(planned)


def _agent_run_response(run: AgentRun) -> AgentRunResponse:
    """Convert an agent domain object into the public API schema."""

    return AgentRunResponse(
        id=run.id,
        goal=run.goal,
        status=run.status,
        step_count=run.step_count,
        max_steps=run.max_steps,
        version=run.version,
    )
