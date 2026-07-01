"""Application service coordinating one safe agent run."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from kelvin_assistant.application.tool_policy import (
    ToolPolicy,
    ToolPolicyContext,
)
from kelvin_assistant.domain.agent import (
    DEFAULT_MAX_AGENT_STEPS,
    AgentRun,
    AgentStatus,
    ApprovalDecision,
    ClarificationRequest,
    ToolApproval,
    ToolCall,
    ToolPolicyDecision,
    ToolProposal,
)


class AgentServiceError(RuntimeError):
    """Raised when an agent application operation is inconsistent."""


@dataclass(frozen=True, slots=True)
class AgentClarification:
    """An agent run paused for one focused user question."""

    run: AgentRun
    request: ClarificationRequest


class AgentService:
    """Coordinate lifecycle transitions without executing external tools."""

    def __init__(self, policy: ToolPolicy) -> None:
        """Create the service with an injected deterministic policy."""

        self._policy = policy

    def start_run(
        self,
        goal: str,
        *,
        max_steps: int = DEFAULT_MAX_AGENT_STEPS,
        workspace_id: str | None = None,
    ) -> AgentRun:
        """Create a new agent run without starting side effects."""

        return AgentRun.create(
            goal,
            max_steps=max_steps,
            workspace_id=workspace_id,
        )

    def request_clarification(
        self,
        run: AgentRun,
        request: ClarificationRequest,
    ) -> AgentClarification:
        """Pause a received or planning run for required information."""

        if run.status not in {AgentStatus.RECEIVED, AgentStatus.PLANNING}:
            raise AgentServiceError(
                f"Cannot request clarification from agent status {run.status}"
            )
        return AgentClarification(
            run=run.transition_to(AgentStatus.CLARIFYING),
            request=request,
        )

    def begin_planning(self, run: AgentRun) -> AgentRun:
        """Move a received or clarified run into planning."""

        if run.status not in {AgentStatus.RECEIVED, AgentStatus.CLARIFYING}:
            raise AgentServiceError(
                f"Cannot begin planning from agent status {run.status}"
            )
        return run.transition_to(AgentStatus.PLANNING)

    def propose_tool(
        self,
        run: AgentRun,
        call: ToolCall,
        *,
        context: ToolPolicyContext,
    ) -> ToolProposal:
        """Evaluate one planned tool and select its next lifecycle state."""

        self._require_status(run, AgentStatus.PLANNING)
        result = self._policy.evaluate(call, context=context)

        if result.decision is ToolPolicyDecision.ALLOW:
            return ToolProposal(
                run=run.transition_to(AgentStatus.EXECUTING),
                call=call,
                policy_result=result,
            )

        if result.decision is ToolPolicyDecision.REQUIRE_APPROVAL:
            return ToolProposal(
                run=run.transition_to(AgentStatus.AWAITING_APPROVAL),
                call=call,
                policy_result=result,
                approval=ToolApproval(tool_call_id=call.id),
            )

        return ToolProposal(
            run=run,
            call=call,
            policy_result=result,
        )

    def resolve_approval(
        self,
        proposal: ToolProposal,
        *,
        decision: ApprovalDecision,
        decided_by: str,
        decided_at: datetime,
    ) -> ToolProposal:
        """Apply a final user decision to a pending tool proposal."""

        self._require_status(proposal.run, AgentStatus.AWAITING_APPROVAL)
        if (
            proposal.policy_result.decision is not ToolPolicyDecision.REQUIRE_APPROVAL
            or proposal.approval is None
            or proposal.approval.decision is not ApprovalDecision.PENDING
            or proposal.approval.tool_call_id != proposal.call.id
        ):
            raise AgentServiceError("Tool proposal has no valid pending approval")
        if decision is ApprovalDecision.PENDING:
            raise AgentServiceError("Approval resolution requires a final decision")

        approval = ToolApproval(
            tool_call_id=proposal.call.id,
            decision=decision,
            decided_by=decided_by,
            decided_at=decided_at,
        )
        next_status = (
            AgentStatus.EXECUTING
            if decision is ApprovalDecision.APPROVED
            else AgentStatus.CANCELLED
        )
        return ToolProposal(
            run=proposal.run.transition_to(next_status),
            call=proposal.call,
            policy_result=proposal.policy_result,
            approval=approval,
        )

    def record_execution_result(
        self,
        run: AgentRun,
        *,
        succeeded: bool,
    ) -> AgentRun:
        """Move a completed tool execution to observation or failure."""

        self._require_status(run, AgentStatus.EXECUTING)
        next_status = AgentStatus.OBSERVING if succeeded else AgentStatus.FAILED
        return run.transition_to(next_status)

    def continue_planning(self, run: AgentRun) -> AgentRun:
        """Start another plan step after observing a tool result."""

        self._require_status(run, AgentStatus.OBSERVING)
        return run.transition_to(AgentStatus.PLANNING)

    def complete_run(self, run: AgentRun) -> AgentRun:
        """Complete a run after planning or observing enough information."""

        if run.status not in {AgentStatus.PLANNING, AgentStatus.OBSERVING}:
            raise AgentServiceError(
                f"Cannot complete agent run from status {run.status}"
            )
        return run.transition_to(AgentStatus.COMPLETED)

    def fail_run(self, run: AgentRun) -> AgentRun:
        """Fail any non-terminal run after a bounded application error."""

        if run.status.is_terminal:
            raise AgentServiceError(
                f"Cannot fail terminal agent run with status {run.status}"
            )
        return run.transition_to(AgentStatus.FAILED)

    @staticmethod
    def _require_status(run: AgentRun, expected: AgentStatus) -> None:
        if run.status is not expected:
            raise AgentServiceError(
                f"Agent run must be {expected}; current status is {run.status}"
            )
