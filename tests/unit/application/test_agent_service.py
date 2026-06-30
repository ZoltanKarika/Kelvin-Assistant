"""Unit tests for the safe agent application workflow."""

from datetime import UTC, datetime

import pytest

from kelvin_assistant.application.agent import AgentService, AgentServiceError
from kelvin_assistant.application.tool_policy import (
    DefaultToolPolicy,
    ToolPolicyContext,
    ToolPolicyDecision,
)
from kelvin_assistant.domain.agent import (
    AgentStatus,
    ApprovalDecision,
    ClarificationRequest,
    ToolCall,
    ToolDefinition,
    ToolExecutionTarget,
    ToolRisk,
)
from kelvin_assistant.tools.registry import StaticToolRegistry


def _definition(name: str, risk: ToolRisk) -> ToolDefinition:
    return ToolDefinition(
        name=name,
        description=f"Execute {name}.",
        input_schema={"type": "object"},
        risk=risk,
        execution_target=ToolExecutionTarget.WINDOWS_CLIENT,
    )


def _call(name: str, risk: ToolRisk) -> ToolCall:
    return ToolCall(
        name=name,
        arguments={"workspace": "C:\\project"},
        reason="Complete the requested task.",
        expected_effect="Apply the registered operation.",
        risk=risk,
    )


def _service(*definitions: ToolDefinition) -> AgentService:
    registry = StaticToolRegistry(definitions)
    return AgentService(DefaultToolPolicy(registry))


def test_service_starts_run_without_side_effects() -> None:
    """Starting a run only validates and records the user goal."""

    run = _service().start_run("  Inspect the project.  ", max_steps=3)

    assert run.goal == "Inspect the project."
    assert run.status is AgentStatus.RECEIVED
    assert run.step_count == 0
    assert run.max_steps == 3


def test_service_handles_clarification_before_planning() -> None:
    """A missing detail pauses the run before planning tools."""

    service = _service()
    run = service.start_run("Inspect a project")
    clarification = service.request_clarification(
        run,
        ClarificationRequest(
            question="Which project should I inspect?",
            reason="No workspace was provided.",
        ),
    )

    assert clarification.run.status is AgentStatus.CLARIFYING
    assert clarification.request.question == "Which project should I inspect?"
    assert service.begin_planning(clarification.run).status is AgentStatus.PLANNING


def test_service_allows_read_tool_without_approval() -> None:
    """An allowed read call moves directly into execution."""

    service = _service(_definition("git.status", ToolRisk.READ))
    run = service.begin_planning(service.start_run("Show Git status"))
    proposal = service.propose_tool(
        run,
        _call("git.status", ToolRisk.READ),
        context=ToolPolicyContext(workspace_authorized=True),
    )

    assert proposal.policy_result.decision is ToolPolicyDecision.ALLOW
    assert proposal.run.status is AgentStatus.EXECUTING
    assert proposal.run.step_count == 1
    assert proposal.approval is None


def test_service_waits_for_write_approval() -> None:
    """A write call pauses with a pending approval and no execution step."""

    service = _service(_definition("file.patch", ToolRisk.WRITE))
    run = service.begin_planning(service.start_run("Update a file"))
    proposal = service.propose_tool(
        run,
        _call("file.patch", ToolRisk.WRITE),
        context=ToolPolicyContext(workspace_authorized=True),
    )

    assert proposal.policy_result.decision is ToolPolicyDecision.REQUIRE_APPROVAL
    assert proposal.run.status is AgentStatus.AWAITING_APPROVAL
    assert proposal.run.step_count == 0
    assert proposal.approval is not None
    assert proposal.approval.decision is ApprovalDecision.PENDING


def test_service_executes_approved_write() -> None:
    """An approved write enters execution and records the decision."""

    service = _service(_definition("file.patch", ToolRisk.WRITE))
    run = service.begin_planning(service.start_run("Update a file"))
    proposal = service.propose_tool(
        run,
        _call("file.patch", ToolRisk.WRITE),
        context=ToolPolicyContext(workspace_authorized=True),
    )

    resolved = service.resolve_approval(
        proposal,
        decision=ApprovalDecision.APPROVED,
        decided_by="zoltan",
        decided_at=datetime.now(UTC),
    )

    assert resolved.run.status is AgentStatus.EXECUTING
    assert resolved.run.step_count == 1
    assert resolved.approval is not None
    assert resolved.approval.decision is ApprovalDecision.APPROVED


def test_service_cancels_rejected_write() -> None:
    """Rejecting a write cancels the run without executing a step."""

    service = _service(_definition("file.patch", ToolRisk.WRITE))
    run = service.begin_planning(service.start_run("Update a file"))
    proposal = service.propose_tool(
        run,
        _call("file.patch", ToolRisk.WRITE),
        context=ToolPolicyContext(workspace_authorized=True),
    )

    resolved = service.resolve_approval(
        proposal,
        decision=ApprovalDecision.REJECTED,
        decided_by="zoltan",
        decided_at=datetime.now(UTC),
    )

    assert resolved.run.status is AgentStatus.CANCELLED
    assert resolved.run.step_count == 0
    assert resolved.approval is not None
    assert resolved.approval.decision is ApprovalDecision.REJECTED


def test_service_keeps_denied_tool_in_planning() -> None:
    """A denied proposal can be replaced by a safer plan."""

    service = _service()
    run = service.begin_planning(service.start_run("Run an unknown tool"))
    proposal = service.propose_tool(
        run,
        _call("system.unknown", ToolRisk.READ),
        context=ToolPolicyContext(workspace_authorized=True),
    )

    assert proposal.policy_result.decision is ToolPolicyDecision.DENY
    assert proposal.run.status is AgentStatus.PLANNING
    assert proposal.run.step_count == 0
    assert proposal.approval is None


def test_service_records_success_and_continues_or_completes() -> None:
    """A successful execution can lead to another plan or completion."""

    service = _service(_definition("git.status", ToolRisk.READ))
    run = service.begin_planning(service.start_run("Inspect the project"))
    proposal = service.propose_tool(
        run,
        _call("git.status", ToolRisk.READ),
        context=ToolPolicyContext(workspace_authorized=True),
    )
    observed = service.record_execution_result(proposal.run, succeeded=True)

    assert observed.status is AgentStatus.OBSERVING
    assert service.continue_planning(observed).status is AgentStatus.PLANNING
    assert service.complete_run(observed).status is AgentStatus.COMPLETED


def test_service_records_failed_execution() -> None:
    """A failed executor result moves the run into a terminal failure."""

    service = _service(_definition("git.status", ToolRisk.READ))
    run = service.begin_planning(service.start_run("Inspect the project"))
    proposal = service.propose_tool(
        run,
        _call("git.status", ToolRisk.READ),
        context=ToolPolicyContext(workspace_authorized=True),
    )

    failed = service.record_execution_result(proposal.run, succeeded=False)

    assert failed.status is AgentStatus.FAILED
    assert failed.status.is_terminal is True


def test_service_rejects_invalid_approval_resolution() -> None:
    """A read proposal has no approval that can be resolved."""

    service = _service(_definition("git.status", ToolRisk.READ))
    run = service.begin_planning(service.start_run("Inspect the project"))
    proposal = service.propose_tool(
        run,
        _call("git.status", ToolRisk.READ),
        context=ToolPolicyContext(workspace_authorized=True),
    )

    with pytest.raises(AgentServiceError, match="awaiting_approval"):
        service.resolve_approval(
            proposal,
            decision=ApprovalDecision.APPROVED,
            decided_by="zoltan",
            decided_at=datetime.now(UTC),
        )


def test_service_rejects_tool_proposal_before_planning() -> None:
    """Tools cannot bypass the received and planning lifecycle states."""

    service = _service(_definition("git.status", ToolRisk.READ))
    run = service.start_run("Inspect the project")

    with pytest.raises(AgentServiceError, match="planning"):
        service.propose_tool(
            run,
            _call("git.status", ToolRisk.READ),
            context=ToolPolicyContext(workspace_authorized=True),
        )
