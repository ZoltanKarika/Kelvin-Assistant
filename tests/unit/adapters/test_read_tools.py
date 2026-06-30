"""Unit tests for safe read-only local tool executors."""

import asyncio
from pathlib import Path

import pytest

from kelvin_assistant.adapters.read_tools import (
    FileSearchExecutor,
    GitDiffExecutor,
    GitStatusExecutor,
)
from kelvin_assistant.domain.agent import ToolCall, ToolRisk
from kelvin_assistant.ports.processes import (
    ProcessRequest,
    ProcessResult,
    ProcessTimeoutError,
)
from kelvin_assistant.ports.tools import ToolExecutionError


class FakeProcessRunner:
    """Record structured requests and return a configured process result."""

    def __init__(
        self,
        result: ProcessResult | None = None,
        error: ProcessTimeoutError | None = None,
    ) -> None:
        self._result = result or ProcessResult(
            return_code=0,
            stdout="",
            stderr="",
            duration_ms=5,
        )
        self._error = error
        self.requests: list[ProcessRequest] = []

    async def run(self, request: ProcessRequest) -> ProcessResult:
        """Record one request and return or raise the configured result."""

        self.requests.append(request)
        if self._error is not None:
            raise self._error
        return self._result


def _call(
    name: str,
    arguments: dict[str, str | int | bool] | None = None,
) -> ToolCall:
    return ToolCall(
        name=name,
        arguments=arguments or {},
        reason="Inspect the workspace.",
        expected_effect="No state change.",
        risk=ToolRisk.READ,
    )


def test_git_status_uses_fixed_structured_arguments() -> None:
    """git.status never accepts or constructs free-form shell text."""

    async def scenario() -> None:
        runner = FakeProcessRunner(
            ProcessResult(
                return_code=0,
                stdout="## main\n M README.md\n",
                stderr="",
                duration_ms=7,
            )
        )
        executor = GitStatusExecutor(runner)

        result = await executor.execute(
            _call("git.status", {"include_untracked": False}),
            workspace_root=Path.cwd(),
        )

        assert result.succeeded is True
        assert result.output == "## main\n M README.md"
        assert runner.requests[0].executable == "git"
        assert runner.requests[0].arguments == (
            "status",
            "--short",
            "--branch",
            "--untracked-files=no",
        )

    asyncio.run(scenario())


def test_git_diff_limits_flags_and_resolves_relative_path() -> None:
    """git.diff converts typed options into a fixed argument sequence."""

    async def scenario() -> None:
        runner = FakeProcessRunner()
        executor = GitDiffExecutor(runner)

        await executor.execute(
            _call("git.diff", {"staged": True, "path": "backend"}),
            workspace_root=Path.cwd(),
        )

        assert runner.requests[0].arguments == (
            "diff",
            "--no-ext-diff",
            "--cached",
            "--",
            "backend",
        )

    asyncio.run(scenario())


def test_git_diff_rejects_workspace_escape() -> None:
    """A relative path cannot resolve outside the trusted workspace."""

    async def scenario() -> None:
        runner = FakeProcessRunner()
        executor = GitDiffExecutor(runner)

        with pytest.raises(ToolExecutionError, match="escapes"):
            await executor.execute(
                _call("git.diff", {"path": "../outside"}),
                workspace_root=Path.cwd(),
            )

        assert runner.requests == []

    asyncio.run(scenario())


def test_file_search_uses_fixed_string_mode_and_limits_results() -> None:
    """file.search invokes rg without regex input and bounds returned lines."""

    async def scenario() -> None:
        runner = FakeProcessRunner(
            ProcessResult(
                return_code=0,
                stdout="a.py:1:Kelvin\nb.py:2:Kelvin\nc.py:3:Kelvin\n",
                stderr="",
                duration_ms=9,
            )
        )
        executor = FileSearchExecutor(runner)

        result = await executor.execute(
            _call(
                "file.search",
                {
                    "query": "Kelvin",
                    "path": "backend",
                    "max_results": 2,
                },
            ),
            workspace_root=Path.cwd(),
        )

        assert result.succeeded is True
        assert result.output == "a.py:1:Kelvin\nb.py:2:Kelvin"
        assert result.truncated is True
        assert runner.requests[0].executable == "rg"
        assert "--fixed-strings" in runner.requests[0].arguments
        assert runner.requests[0].arguments[-2:] == ("Kelvin", "backend")

    asyncio.run(scenario())


def test_file_search_treats_no_matches_as_success() -> None:
    """ripgrep return code 1 means an empty successful search."""

    async def scenario() -> None:
        runner = FakeProcessRunner(
            ProcessResult(
                return_code=1,
                stdout="",
                stderr="",
                duration_ms=4,
            )
        )
        executor = FileSearchExecutor(runner)

        result = await executor.execute(
            _call("file.search", {"query": "missing"}),
            workspace_root=Path.cwd(),
        )

        assert result.succeeded is True
        assert result.output == ""

    asyncio.run(scenario())


def test_executor_converts_process_timeout_to_failed_result() -> None:
    """A process timeout is data for the agent, not an unhandled exception."""

    async def scenario() -> None:
        runner = FakeProcessRunner(
            error=ProcessTimeoutError("Process timed out"),
        )
        executor = GitStatusExecutor(runner)

        result = await executor.execute(
            _call("git.status"),
            workspace_root=Path.cwd(),
        )

        assert result.succeeded is False
        assert result.error == "Process timed out"

    asyncio.run(scenario())


def test_executor_rejects_unknown_arguments() -> None:
    """Tool calls cannot smuggle unsupported command flags."""

    async def scenario() -> None:
        runner = FakeProcessRunner()
        executor = GitStatusExecutor(runner)

        with pytest.raises(ToolExecutionError, match="Unsupported"):
            await executor.execute(
                _call("git.status", {"command": "reset --hard"}),
                workspace_root=Path.cwd(),
            )

        assert runner.requests == []

    asyncio.run(scenario())
