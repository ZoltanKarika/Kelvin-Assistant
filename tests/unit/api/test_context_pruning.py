"""Unit tests for workspace context pruning and ignore logic."""

import asyncio
from pathlib import Path

import pytest

from kelvin_assistant.adapters.read_tools import (
    FileSearchExecutor,
    GitStatusExecutor,
    _optional_path,
    should_ignore_path,
)
from kelvin_assistant.adapters.write_tools import _resolve_file
from kelvin_assistant.domain.agent import ToolCall, ToolRisk
from kelvin_assistant.ports.processes import ProcessRequest, ProcessResult
from kelvin_assistant.ports.tools import ToolExecutionError


class FakeProcessRunner:
    """Record process requests and return configured results."""

    def __init__(self, result: ProcessResult) -> None:
        self.result = result
        self.requests: list[ProcessRequest] = []

    async def run(self, request: ProcessRequest) -> ProcessResult:
        self.requests.append(request)
        return self.result


def _call(name: str, arguments: dict[str, str | int | bool] | None = None) -> ToolCall:
    return ToolCall(
        name=name,
        arguments=arguments or {},
        reason="Test tool",
        expected_effect="Test effect",
        risk=ToolRisk.READ if "patch" not in name else ToolRisk.WRITE,
    )


def test_should_ignore_path_basic(tmp_path: Path) -> None:
    """Verify standard folders/files are ignored."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    # Ignored directories
    assert should_ignore_path(workspace / ".git", workspace) is True
    assert should_ignore_path(workspace / ".git" / "config", workspace) is True
    assert should_ignore_path(workspace / ".venv", workspace) is True
    assert should_ignore_path(workspace / ".venv" / "bin" / "python", workspace) is True
    assert should_ignore_path(workspace / "__pycache__", workspace) is True
    assert (
        should_ignore_path(workspace / "backend" / "__pycache__" / "a.pyc", workspace)
        is True
    )
    assert (
        should_ignore_path(workspace / ".pytest_cache" / "v" / "cache", workspace)
        is True
    )

    # Ignored temporary/config files
    assert should_ignore_path(workspace / ".env", workspace) is True
    assert should_ignore_path(workspace / "api-tokens.json", workspace) is True
    assert should_ignore_path(workspace / "sub" / "api-tokens.json", workspace) is True
    assert should_ignore_path(workspace / "test.log", workspace) is True
    assert should_ignore_path(workspace / "notes.tmp", workspace) is True
    assert should_ignore_path(workspace / "old.bak", workspace) is True

    # Non-ignored paths
    assert should_ignore_path(workspace, workspace) is False
    assert (
        should_ignore_path(workspace / "backend" / "src" / "app.py", workspace) is False
    )
    assert should_ignore_path(workspace / "README.md", workspace) is False


def test_should_ignore_path_custom_gitignore(tmp_path: Path) -> None:
    """Verify custom patterns from .gitignore are parsed and respected."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    gitignore = workspace / ".gitignore"
    gitignore.write_text(
        "# Custom ignore rules\ncustom_ignored/\n*.secret\n/absolute_only\n",
        encoding="utf-8",
    )

    # Respect directory ignore
    assert (
        should_ignore_path(workspace / "custom_ignored" / "file.txt", workspace) is True
    )
    assert (
        should_ignore_path(workspace / "sub" / "custom_ignored" / "file.txt", workspace)
        is True
    )

    # Respect extension ignore
    assert should_ignore_path(workspace / "my_key.secret", workspace) is True
    assert should_ignore_path(workspace / "sub" / "key.secret", workspace) is True

    # Respect relative root-only ignore
    assert should_ignore_path(workspace / "absolute_only", workspace) is True
    # If it's nested under sub-directory, a starting '/' pattern
    # in gitignore matches relative to root
    assert should_ignore_path(workspace / "sub" / "absolute_only", workspace) is False


def test_optional_path_rejects_ignored(tmp_path: Path) -> None:
    """Verify _optional_path raises error on ignored paths."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    # Allowed path
    resolved = _optional_path({"path": "src/app.py"}, workspace)
    assert resolved == "src/app.py"

    # Ignored path should raise ToolExecutionError
    with pytest.raises(ToolExecutionError, match="ignored"):
        _optional_path({"path": ".venv/bin/pip"}, workspace)


def test_file_search_prunes_ignored_files(tmp_path: Path) -> None:
    """Verify FileSearchExecutor filters out results belonging to ignored paths."""

    async def scenario() -> None:
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        # Ripgrep stdout returns matching lines with path prefixes
        fake_stdout = (
            "src/app.py:10:def main():\n"
            ".venv/lib/site-packages/pytest.py:50:class Pytest:\n"
            "tests/test_app.py:5:def test_main():\n"
            "__pycache__/app.cpython.pyc:1:some binary match\n"
        )
        runner = FakeProcessRunner(
            ProcessResult(
                return_code=0,
                stdout=fake_stdout,
                stderr="",
                duration_ms=10,
            )
        )
        executor = FileSearchExecutor(runner)

        result = await executor.execute(
            _call("file.search", {"query": "def", "max_results": 10}),
            workspace_root=workspace,
        )

        assert result.succeeded is True
        # Match from .venv and __pycache__ must be pruned
        expected = "src/app.py:10:def main():\ntests/test_app.py:5:def test_main():"
        assert result.output == expected

    asyncio.run(scenario())


def test_git_status_prunes_ignored_files(tmp_path: Path) -> None:
    """Verify GitStatusExecutor filters out untracked/modified ignored paths."""

    async def scenario() -> None:
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        fake_stdout = (
            "## main...origin/main\n"
            " M src/app.py\n"
            "?? .venv/bin/pip\n"
            "?? notes.tmp\n"
            "?? tests/test_app.py\n"
        )
        runner = FakeProcessRunner(
            ProcessResult(
                return_code=0,
                stdout=fake_stdout,
                stderr="",
                duration_ms=5,
            )
        )
        executor = GitStatusExecutor(runner)

        result = await executor.execute(
            _call("git.status"),
            workspace_root=workspace,
        )

        assert result.succeeded is True
        # .venv/bin/pip and notes.tmp should be pruned
        expected = "## main...origin/main\n M src/app.py\n?? tests/test_app.py"
        assert result.output == expected

    asyncio.run(scenario())


def test_resolve_file_rejects_ignored_write_target(tmp_path: Path) -> None:
    """Verify write tool resolution blocks patch target in ignored directories."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    ignored_dir = workspace / ".venv"
    ignored_dir.mkdir()
    ignored_file = ignored_dir / "target.py"
    ignored_file.write_text("content", encoding="utf-8")

    with pytest.raises(ToolExecutionError, match="ignored"):
        _resolve_file(workspace, ".venv/target.py")
