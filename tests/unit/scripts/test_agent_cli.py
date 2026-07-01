"""Unit tests for the PowerShell-friendly Kelvin client."""

import asyncio
from collections.abc import Mapping
from pathlib import Path
from uuid import UUID

import pytest

from kelvin_assistant.cli.agent import (
    ClientCommand,
    build_parser,
    execute_command,
    parse_command,
)
from kelvin_assistant.domain.agent import (
    AgentRun,
    AgentStatus,
    JsonValue,
    ToolCall,
    ToolExecutionResult,
    ToolPolicyDecision,
    ToolPolicyResult,
    ToolProposal,
    ToolRisk,
)
from kelvin_assistant.ports.processes import ProcessRequest, ProcessResult

RUN_ID = UUID("11111111-1111-4111-8111-111111111111")
CALL_ID = UUID("22222222-2222-4222-8222-222222222222")


def _run(status: AgentStatus, version: int) -> AgentRun:
    return AgentRun(
        id=RUN_ID,
        goal="Execute read-only tool git.status.",
        status=status,
        step_count=1 if status in {AgentStatus.EXECUTING, AgentStatus.OBSERVING} else 0,
        version=version,
        workspace_id="kelvin-assistant",
    )


class FakeAgentApiClient:
    """Mirror the requested tool while returning valid backend states."""

    def __init__(self) -> None:
        self.name = ""
        self.arguments: Mapping[str, JsonValue] = {}

    async def create_run(self, *, goal: str, workspace_id: str) -> AgentRun:
        assert workspace_id == "kelvin-assistant"
        return _run(AgentStatus.RECEIVED, 0)

    async def begin_planning(self, run_id: UUID) -> AgentRun:
        return _run(AgentStatus.PLANNING, 1)

    async def propose_tool(
        self,
        run_id: UUID,
        *,
        name: str,
        arguments: Mapping[str, JsonValue],
        reason: str,
        expected_effect: str,
        risk: ToolRisk,
    ) -> ToolProposal:
        self.name = name
        self.arguments = arguments
        return ToolProposal(
            run=_run(AgentStatus.EXECUTING, 2),
            call=ToolCall(
                id=CALL_ID,
                name=name,
                arguments=arguments,
                reason=reason,
                expected_effect=expected_effect,
                risk=risk,
            ),
            policy_result=ToolPolicyResult(
                decision=ToolPolicyDecision.ALLOW,
                reason="Read-only tool is allowed.",
            ),
        )

    async def resolve_approval(
        self,
        run_id: UUID,
        *,
        tool_call_id: UUID,
        approved: bool,
    ) -> ToolProposal:
        raise AssertionError("Read tool must not request approval")

    async def submit_result(
        self,
        run_id: UUID,
        result: ToolExecutionResult,
    ) -> AgentRun:
        assert result.tool_call_id == CALL_ID
        return _run(AgentStatus.OBSERVING, 3)


class FakeProcessRunner:
    """Capture the safe process request without invoking Git or ripgrep."""

    def __init__(self) -> None:
        self.request: ProcessRequest | None = None

    async def run(self, request: ProcessRequest) -> ProcessResult:
        self.request = request
        return ProcessResult(
            return_code=0,
            stdout="## main...origin/main\n",
            stderr="",
            duration_ms=3,
        )


def test_parser_builds_git_diff_command() -> None:
    """PowerShell arguments become one structured, relative Git operation."""

    workspace_root = Path.cwd()
    command = parse_command(
        build_parser(),
        [
            "--api-url",
            "http://192.168.10.13:8000",
            "--workspace-id",
            "kelvin-assistant",
            "--workspace",
            str(workspace_root),
            "git",
            "diff",
            "--staged",
            "--path",
            "backend",
        ],
    )

    assert command == ClientCommand(
        api_url="http://192.168.10.13:8000",
        workspace_id="kelvin-assistant",
        workspace_root=workspace_root.resolve(),
        tool_name="git.diff",
        arguments={"staged": True, "path": "backend"},
    )


def test_parser_builds_fixed_text_search_command() -> None:
    """File search remains fixed-text and bounded by a result limit."""

    workspace_root = Path.cwd()
    command = parse_command(
        build_parser(),
        [
            "--workspace-id",
            "kelvin-assistant",
            "--workspace",
            str(workspace_root),
            "file",
            "search",
            "AgentService",
            "--max-results",
            "10",
        ],
    )

    assert command.tool_name == "file.search"
    assert command.arguments == {
        "query": "AgentService",
        "max_results": 10,
    }


def test_parser_builds_approval_gated_file_patch() -> None:
    """Patch input becomes one exact replacement without shell text."""

    command = parse_command(
        build_parser(),
        [
            "--workspace-id",
            "kelvin-assistant",
            "--workspace",
            str(Path.cwd()),
            "file",
            "patch",
            "notes.txt",
            "--old-text",
            "old value",
            "--new-text",
            "new value",
        ],
    )

    assert command.tool_name == "file.patch"
    assert command.arguments == {
        "path": "notes.txt",
        "old_text": "old value",
        "new_text": "new value",
    }


def test_execute_command_prints_local_tool_output(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The CLI completes policy, local execution, and result submission."""

    workspace_root = Path.cwd()
    api_client = FakeAgentApiClient()
    runner = FakeProcessRunner()
    command = ClientCommand(
        api_url="http://kelvin.test:8000",
        workspace_id="kelvin-assistant",
        workspace_root=workspace_root,
        tool_name="git.status",
        arguments={"include_untracked": False},
    )

    exit_code = asyncio.run(
        execute_command(
            command,
            api_client=api_client,
            process_runner=runner,
        )
    )

    assert exit_code == 0
    assert api_client.name == "git.status"
    assert api_client.arguments == {"include_untracked": False}
    assert runner.request == ProcessRequest(
        executable="git",
        arguments=(
            "status",
            "--short",
            "--branch",
            "--untracked-files=no",
        ),
        cwd=workspace_root.resolve(),
        timeout_seconds=15,
    )
    assert "## main...origin/main" in capsys.readouterr().out
