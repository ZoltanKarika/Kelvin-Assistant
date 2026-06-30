"""Local client orchestration for approved read-only agent tools."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from kelvin_assistant.domain.agent import (
    AgentRun,
    AgentStatus,
    JsonValue,
    ToolExecutionResult,
    ToolPolicyDecision,
)
from kelvin_assistant.ports.agent_client import AgentApiClient, AgentClientError
from kelvin_assistant.ports.tools import ToolExecutor


class LocalAgentClientError(AgentClientError):
    """Raised when the local and remote agent states are inconsistent."""


@dataclass(frozen=True, slots=True)
class LocalToolRunResult:
    """Completed local tool output and final remote run state."""

    run: AgentRun
    execution: ToolExecutionResult


class LocalReadToolClient:
    """Coordinate backend policy with local Windows read tool execution."""

    def __init__(
        self,
        *,
        api_client: AgentApiClient,
        executors: Mapping[str, ToolExecutor],
        workspace_id: str,
        workspace_root: Path,
    ) -> None:
        """Bind an opaque server workspace ID to one local root path."""

        normalized_workspace_id = workspace_id.strip()
        if not normalized_workspace_id:
            raise ValueError("Workspace ID cannot be empty")
        self._api_client = api_client
        self._executors = dict(executors)
        self._workspace_id = normalized_workspace_id
        self._workspace_root = workspace_root

    async def run_tool(
        self,
        name: str,
        arguments: Mapping[str, JsonValue],
    ) -> LocalToolRunResult:
        """Run one read tool through the complete remote policy lifecycle."""

        executor = self._executors.get(name)
        if executor is None:
            raise LocalAgentClientError(f"Local executor is not registered: {name}")

        run = await self._api_client.create_run(
            goal=f"Execute read-only tool {name}.",
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
            expected_effect="Read workspace state without modifying files.",
        )
        self._verify_workspace(proposal.run)
        if proposal.policy_result.decision is not ToolPolicyDecision.ALLOW:
            raise LocalAgentClientError(
                f"Tool proposal was not allowed: {proposal.policy_result.reason}"
            )
        if proposal.run.status is not AgentStatus.EXECUTING:
            raise LocalAgentClientError("Allowed tool is not ready for execution")
        if proposal.call.name != executor.definition.name:
            raise LocalAgentClientError("Remote proposal does not match local executor")

        execution = await executor.execute(
            proposal.call,
            workspace_root=self._workspace_root,
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

    def _verify_workspace(self, run: AgentRun) -> None:
        if run.workspace_id != self._workspace_id:
            raise LocalAgentClientError(
                "Remote agent run is bound to a different workspace"
            )
