"""Versioned API routes for server-managed agent runs."""

from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from kelvin_assistant.api.dependencies import (
    get_agent_planning_service,
    get_agent_run_store,
    get_agent_service,
    get_workspace_authorizer,
)
from kelvin_assistant.api.schemas import (
    AgentNextClarificationResponse,
    AgentNextCompletionResponse,
    AgentNextRequest,
    AgentNextResponse,
    AgentNextToolResponse,
    AgentRunCreateRequest,
    AgentRunResponse,
    AgentToolApprovalRequest,
    AgentToolCallRequest,
    AgentToolProposalResponse,
    AgentToolResultRequest,
    AgentToolResultResponse,
)
from kelvin_assistant.application.agent import AgentService, AgentServiceError
from kelvin_assistant.application.agent_planning import (
    AgentPlanningError,
    AgentPlanningService,
    ClarificationOutcome,
    CompletionOutcome,
    ToolOutcome,
)
from kelvin_assistant.application.tool_policy import ToolPolicyContext
from kelvin_assistant.domain.agent import (
    AgentDomainError,
    AgentRun,
    AgentStatus,
    ApprovalDecision,
    ToolCall,
    ToolExecutionResult,
    ToolPolicyDecision,
    ToolProposal,
)
from kelvin_assistant.domain.planner import ClarificationTurn, PlannerDomainError
from kelvin_assistant.ports.agent_runs import (
    AgentProposalNotFoundError,
    AgentRunConflictError,
    AgentRunNotFoundError,
    AgentRunStore,
    AgentRunStoreError,
)
from kelvin_assistant.ports.planner import (
    AgentPlannerResponseError,
    AgentPlannerUnavailableError,
)
from kelvin_assistant.ports.workspaces import WorkspaceAuthorizer

router = APIRouter(prefix="/api/v1/agent", tags=["agent"])
RuntimeAgentService = Annotated[AgentService, Depends(get_agent_service)]
RuntimeAgentPlanningService = Annotated[
    AgentPlanningService,
    Depends(get_agent_planning_service),
]
RuntimeAgentRunStore = Annotated[AgentRunStore, Depends(get_agent_run_store)]
RuntimeWorkspaceAuthorizer = Annotated[
    WorkspaceAuthorizer,
    Depends(get_workspace_authorizer),
]
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
        run = service.start_run(
            request.goal,
            max_steps=request.max_steps,
            workspace_id=request.workspace_id,
        )
        await store.add(run)
    except (AgentDomainError, PlannerDomainError) as exc:
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
    "/runs/{run_id}/cancel",
    response_model=AgentRunResponse,
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Agent run not found."},
        status.HTTP_409_CONFLICT: {
            "description": "Run is terminal or changed concurrently.",
        },
    },
)
async def cancel_agent_run(
    run_id: UUID,
    service: RuntimeAgentService,
    store: RuntimeAgentRunStore,
) -> AgentRunResponse:
    """Cancel one active run and close its pending tool proposal."""

    try:
        current = await store.get(run_id)
        cancelled = service.cancel_run(current)
        await store.cancel_run(cancelled, expected_version=current.version)
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
    return _agent_run_response(cancelled)


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


@router.post(
    "/runs/{run_id}/next",
    response_model=AgentNextResponse,
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Agent run not found."},
        status.HTTP_409_CONFLICT: {
            "description": "Invalid or concurrent agent transition.",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Invalid planner context.",
        },
        status.HTTP_502_BAD_GATEWAY: {
            "description": "Planner returned unusable output.",
        },
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "description": "Planner provider is unavailable.",
        },
    },
)
async def plan_next_agent_step(
    run_id: UUID,
    request: AgentNextRequest,
    planning_service: RuntimeAgentPlanningService,
    store: RuntimeAgentRunStore,
    workspace_authorizer: RuntimeWorkspaceAuthorizer,
) -> AgentNextResponse:
    """Plan, validate, policy-check, and persist one next agent decision."""

    planned: AgentRun | None = None
    try:
        current = await store.get(run_id)
        planned = planning_service.prepare_run(current)
        if planned.version != current.version:
            await store.update(planned, expected_version=current.version)
        outcome = await planning_service.plan_next(
            planned,
            clarifications=tuple(
                ClarificationTurn(
                    question=turn.question,
                    answer=turn.answer,
                )
                for turn in request.clarifications
            ),
            observation=request.observation,
            policy_context=ToolPolicyContext(
                workspace_authorized=workspace_authorizer.is_authorized(
                    planned.workspace_id
                ),
                workspace_id=planned.workspace_id,
            ),
        )
    except AgentRunNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except AgentPlannerUnavailableError as exc:
        await _fail_planning_run(planning_service, store, planned)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except AgentPlannerResponseError as exc:
        await _fail_planning_run(planning_service, store, planned)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
    except AgentDomainError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    except AgentPlanningError as exc:
        await _fail_planning_run(planning_service, store, planned)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
    except (AgentServiceError, AgentRunConflictError) as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    try:
        if isinstance(outcome, ClarificationOutcome):
            await store.update(
                outcome.clarification.run,
                expected_version=planned.version,
            )
            return AgentNextClarificationResponse(
                run=_agent_run_response(outcome.clarification.run),
                question=outcome.decision.question,
                reason=outcome.decision.reason,
            )
        if isinstance(outcome, CompletionOutcome):
            await store.update(outcome.run, expected_version=planned.version)
            return AgentNextCompletionResponse(
                run=_agent_run_response(outcome.run),
                summary=outcome.decision.summary,
            )
        if isinstance(outcome, ToolOutcome):
            if outcome.proposal.policy_result.decision is ToolPolicyDecision.DENY:
                failed = planning_service.fail_run(planned)
                await store.update(failed, expected_version=planned.version)
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=outcome.proposal.policy_result.reason,
                )
            await store.update_proposal(
                outcome.proposal,
                expected_version=planned.version,
            )
            return AgentNextToolResponse(
                proposal=_tool_proposal_response(outcome.proposal)
            )
    except AgentRunConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    raise RuntimeError("Unsupported planning outcome")


@router.post(
    "/runs/{run_id}/tools",
    response_model=AgentToolProposalResponse,
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Agent run not found."},
        status.HTTP_409_CONFLICT: {
            "description": "Invalid or concurrent agent transition.",
        },
        UNPROCESSABLE_CONTENT: {"description": "Invalid tool call."},
    },
)
async def propose_agent_tool(
    run_id: UUID,
    request: AgentToolCallRequest,
    service: RuntimeAgentService,
    store: RuntimeAgentRunStore,
    workspace_authorizer: RuntimeWorkspaceAuthorizer,
) -> AgentToolProposalResponse:
    """Evaluate and persist one structured tool proposal."""

    try:
        current = await store.get(run_id)
        call = ToolCall(
            name=request.name,
            arguments=request.arguments,
            reason=request.reason,
            expected_effect=request.expected_effect,
            risk=request.risk,
        )
        proposal = service.propose_tool(
            current,
            call,
            context=ToolPolicyContext(
                workspace_authorized=workspace_authorizer.is_authorized(
                    current.workspace_id
                ),
                workspace_id=current.workspace_id,
            ),
        )
        if proposal.policy_result.decision is not ToolPolicyDecision.DENY:
            await store.update_proposal(
                proposal,
                expected_version=current.version,
            )
    except AgentRunNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except AgentDomainError as exc:
        raise HTTPException(
            status_code=UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    except (AgentServiceError, AgentRunConflictError) as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    return _tool_proposal_response(proposal)


@router.post(
    "/runs/{run_id}/approval",
    response_model=AgentToolProposalResponse,
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_404_NOT_FOUND: {
            "description": "Agent run or proposal not found.",
        },
        status.HTTP_409_CONFLICT: {
            "description": "Invalid approval or concurrent transition.",
        },
    },
)
async def resolve_agent_tool_approval(
    run_id: UUID,
    request: AgentToolApprovalRequest,
    service: RuntimeAgentService,
    store: RuntimeAgentRunStore,
) -> AgentToolProposalResponse:
    """Approve or reject the active server-managed tool proposal."""

    try:
        proposal = await store.get_proposal(run_id)
        if proposal.call.id != request.tool_call_id:
            raise AgentServiceError("Approval does not match the active tool call")
        resolved = service.resolve_approval(
            proposal,
            decision=ApprovalDecision(request.decision),
            decided_by="local-client",
            decided_at=datetime.now(UTC),
        )
        await store.update_proposal(
            resolved,
            expected_version=proposal.run.version,
        )
    except (AgentRunNotFoundError, AgentProposalNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except (AgentServiceError, AgentRunConflictError) as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    return _tool_proposal_response(resolved)


@router.get(
    "/runs/{run_id}/tools/active",
    response_model=AgentToolProposalResponse,
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_404_NOT_FOUND: {
            "description": "Agent run or active proposal not found.",
        },
    },
)
async def get_active_agent_tool(
    run_id: UUID,
    store: RuntimeAgentRunStore,
) -> AgentToolProposalResponse:
    """Return the active server-managed tool proposal for a client."""

    try:
        proposal = await store.get_proposal(run_id)
    except (AgentRunNotFoundError, AgentProposalNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    return _tool_proposal_response(proposal)


@router.post(
    "/runs/{run_id}/result",
    response_model=AgentToolResultResponse,
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_404_NOT_FOUND: {
            "description": "Agent run or active proposal not found.",
        },
        status.HTTP_409_CONFLICT: {
            "description": "Result does not match active execution.",
        },
        UNPROCESSABLE_CONTENT: {"description": "Invalid tool result."},
    },
)
async def submit_agent_tool_result(
    run_id: UUID,
    request: AgentToolResultRequest,
    service: RuntimeAgentService,
    store: RuntimeAgentRunStore,
) -> AgentToolResultResponse:
    """Store one matching local tool result and advance the agent run."""

    try:
        proposal = await store.get_proposal(run_id)
        if proposal.call.id != request.tool_call_id:
            raise AgentServiceError("Result does not match the active tool call")
        result = ToolExecutionResult(
            tool_call_id=request.tool_call_id,
            tool_name=proposal.call.name,
            succeeded=request.succeeded,
            output=request.output,
            error=request.error,
            truncated=request.truncated,
            duration_ms=request.duration_ms,
        )
        updated_run = service.record_execution_result(
            proposal.run,
            succeeded=result.succeeded,
        )
        await store.complete_proposal(
            updated_run,
            result,
            expected_version=proposal.run.version,
        )
    except (AgentRunNotFoundError, AgentProposalNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except AgentDomainError as exc:
        raise HTTPException(
            status_code=UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    except (AgentServiceError, AgentRunConflictError) as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    return _tool_result_response(updated_run, result)


def _agent_run_response(run: AgentRun) -> AgentRunResponse:
    """Convert an agent domain object into the public API schema."""

    return AgentRunResponse(
        id=run.id,
        goal=run.goal,
        status=run.status,
        step_count=run.step_count,
        max_steps=run.max_steps,
        version=run.version,
        workspace_id=run.workspace_id,
    )


async def _fail_planning_run(
    planning_service: AgentPlanningService,
    store: AgentRunStore,
    planned: AgentRun | None,
) -> None:
    """Best-effort persist a failed state without hiding planner errors."""

    if planned is None or planned.status is not AgentStatus.PLANNING:
        return
    try:
        failed = planning_service.fail_run(planned)
        await store.update(failed, expected_version=planned.version)
    except AgentRunStoreError:
        return


def _tool_proposal_response(
    proposal: ToolProposal,
) -> AgentToolProposalResponse:
    """Convert a server-managed proposal into the public API schema."""

    return AgentToolProposalResponse(
        run=_agent_run_response(proposal.run),
        tool_call_id=proposal.call.id,
        tool_name=proposal.call.name,
        arguments=dict(proposal.call.arguments),
        reason=proposal.call.reason,
        expected_effect=proposal.call.expected_effect,
        risk=proposal.call.risk,
        policy_decision=proposal.policy_result.decision,
        policy_reason=proposal.policy_result.reason,
        approval_status=(
            proposal.approval.decision if proposal.approval is not None else None
        ),
    )


def _tool_result_response(
    run: AgentRun,
    result: ToolExecutionResult,
) -> AgentToolResultResponse:
    """Convert a stored execution result into the public API schema."""

    return AgentToolResultResponse(
        run=_agent_run_response(run),
        tool_call_id=result.tool_call_id,
        tool_name=result.tool_name,
        succeeded=result.succeeded,
        output=result.output,
        error=result.error,
        truncated=result.truncated,
        duration_ms=result.duration_ms,
    )
