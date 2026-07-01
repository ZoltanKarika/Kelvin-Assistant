"""Local client orchestration for approved read-only agent tools."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from kelvin_assistant.domain.agent import (
    MAX_TOOL_OUTPUT_LENGTH,
    AgentRun,
    AgentStatus,
    JsonValue,
    ToolExecutionResult,
    ToolPolicyDecision,
    ToolProposal,
    ToolRisk,
)
from kelvin_assistant.ports.agent_client import AgentApiClient, AgentClientError
from kelvin_assistant.ports.tools import (
    PreviewableToolExecutor,
    ToolExecutionError,
    ToolExecutor,
)


class LocalAgentClientError(AgentClientError):
    """Raised when the local and remote agent states are inconsistent."""


class ToolApprovalRejectedError(LocalAgentClientError):
    """Raised after the user safely rejects a pending write proposal."""


@dataclass(frozen=True, slots=True)
class LocalToolRunResult:
    """Completed local tool output and final remote run state."""

    run: AgentRun
    execution: ToolExecutionResult


class LocalReadToolClient:
    """Coordinate backend policy, approval, and local Windows execution."""

    def __init__(
        self,
        *,
        api_client: AgentApiClient,
        executors: Mapping[str, ToolExecutor],
        workspace_id: str,
        workspace_root: Path,
        approval_handler: Callable[[str], bool] | None = None,
    ) -> None:
        """Bind an opaque server workspace ID to one local root path."""

        normalized_workspace_id = workspace_id.strip()
        if not normalized_workspace_id:
            raise ValueError("Workspace ID cannot be empty")
        self._api_client = api_client
        self._executors = dict(executors)
        self._workspace_id = normalized_workspace_id
        self._workspace_root = workspace_root
        self._approval_handler = approval_handler

    async def run_tool(
        self,
        name: str,
        arguments: Mapping[str, JsonValue],
    ) -> LocalToolRunResult:
        """Run one tool through the complete remote policy lifecycle."""

        executor = self._executors.get(name)
        if executor is None:
            raise LocalAgentClientError(f"Local executor is not registered: {name}")

        run = await self._api_client.create_run(
            goal=f"Execute tool {name}.",
            workspace_id=self._workspace_id,
        )
        self._verify_workspace(run)
        planned = await self._api_client.begin_planning(run.id)
        if planned.status is not AgentStatus.PLANNING:
            raise LocalAgentClientError("Remote agent did not enter planning")

        proposal = await self._api_client.propose_tool(
            planned.id,
            name=name,
            arguments=arguments,
            reason=f"Run {name} from the local Kelvin client.",
            expected_effect=(
                "Read workspace state without modifying files."
                if executor.definition.risk is ToolRisk.READ
                else "Apply the exact user-approved workspace change."
            ),
            risk=executor.definition.risk,
        )
        self._verify_workspace(proposal.run)
        if proposal.call.name != executor.definition.name:
            raise LocalAgentClientError("Remote proposal does not match local executor")
        if proposal.call.risk is not executor.definition.risk:
            raise LocalAgentClientError(
                "Remote proposal risk does not match local executor"
            )

        if proposal.policy_result.decision is ToolPolicyDecision.DENY:
            raise LocalAgentClientError(
                f"Tool proposal was not allowed: {proposal.policy_result.reason}"
            )
        if (
            executor.definition.risk is not ToolRisk.READ
            and proposal.policy_result.decision is ToolPolicyDecision.ALLOW
        ):
            raise LocalAgentClientError(
                "Write tool cannot execute without explicit approval"
            )
        if proposal.policy_result.decision is ToolPolicyDecision.REQUIRE_APPROVAL:
            proposal = await self._resolve_write_approval(proposal, executor)
        elif proposal.run.status is not AgentStatus.EXECUTING:
            raise LocalAgentClientError("Allowed tool is not ready for execution")

        try:
            execution = await executor.execute(
                proposal.call,
                workspace_root=self._workspace_root,
            )
        except ToolExecutionError as exc:
            execution = ToolExecutionResult(
                tool_call_id=proposal.call.id,
                tool_name=proposal.call.name,
                succeeded=False,
                error=str(exc)[:MAX_TOOL_OUTPUT_LENGTH],
            )
        updated_run = await self._api_client.submit_result(
            proposal.run.id,
            execution,
        )
        expected_status = (
            AgentStatus.OBSERVING if execution.succeeded else AgentStatus.FAILED
        )
        if updated_run.status is not expected_status:
            raise LocalAgentClientError(
                "Remote agent returned an unexpected result state"
            )
        return LocalToolRunResult(run=updated_run, execution=execution)

    async def _resolve_write_approval(
        self,
        proposal: ToolProposal,
        executor: ToolExecutor,
    ) -> ToolProposal:
        """Prepare a complete preview and submit one explicit decision."""

        if proposal.run.status is not AgentStatus.AWAITING_APPROVAL:
            raise LocalAgentClientError("Write tool is not awaiting approval")
        if not isinstance(executor, PreviewableToolExecutor):
            raise LocalAgentClientError("Write tool does not provide a safe preview")
        if self._approval_handler is None:
            raise LocalAgentClientError("Write tool requires an approval handler")

        try:
            preview = await executor.preview(
                proposal.call,
                workspace_root=self._workspace_root,
            )
        except ToolExecutionError:
            await self._api_client.resolve_approval(
                proposal.run.id,
                tool_call_id=proposal.call.id,
                approved=False,
            )
            raise

        approved = self._approval_handler(preview.content)
        resolved = await self._api_client.resolve_approval(
            proposal.run.id,
            tool_call_id=proposal.call.id,
            approved=approved,
        )
        self._verify_workspace(resolved.run)
        if resolved.call != proposal.call:
            raise LocalAgentClientError(
                "Resolved approval changed the active tool call"
            )
        if not approved:
            if resolved.run.status is not AgentStatus.CANCELLED:
                raise LocalAgentClientError(
                    "Rejected tool did not enter cancelled state"
                )
            raise ToolApprovalRejectedError("Tool change was rejected")
        if resolved.run.status is not AgentStatus.EXECUTING:
            raise LocalAgentClientError("Approved tool is not ready for execution")
        return resolved

    def _verify_workspace(self, run: AgentRun) -> None:
        if run.workspace_id != self._workspace_id:
            raise LocalAgentClientError(
                "Remote agent run is bound to a different workspace"
            )
