"""Safe local executors for the first read-only agent tools."""

from __future__ import annotations

import fnmatch
from collections.abc import Mapping
from pathlib import Path

from kelvin_assistant.domain.agent import (
    MAX_TOOL_OUTPUT_LENGTH,
    JsonValue,
    ToolCall,
    ToolDefinition,
    ToolExecutionResult,
    ToolRisk,
)
from kelvin_assistant.ports.processes import (
    ProcessRequest,
    ProcessResult,
    ProcessRunner,
    ProcessRunnerError,
)
from kelvin_assistant.ports.tools import ToolExecutionError
from kelvin_assistant.tools.read_definitions import read_tool_definitions

_DEFINITIONS = {definition.name: definition for definition in read_tool_definitions()}


def should_ignore_path(path: Path, workspace_root: Path) -> bool:
    """Return whether a path matches standard or workspace-defined ignore patterns."""
    try:
        abs_path = path.resolve()
        abs_root = workspace_root.resolve()
    except OSError:
        abs_path = path.absolute()
        abs_root = workspace_root.absolute()

    if abs_path == abs_root:
        return False

    try:
        rel_path = abs_path.relative_to(abs_root)
    except ValueError:
        return True

    # Standard patterns that are always ignored
    standard_ignored_names = {
        ".git",
        ".venv",
        "venv",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".coverage",
        "htmlcov",
        ".idea",
        ".vscode",
        "logs",
        "models",
        "chroma",
        ".uv-cache",
        ".sandbox-pytest-temp",
    }

    standard_ignored_globs = {
        "*.pyc",
        "*.pyo",
        "*.pyd",
        "*.so",
        "*.log",
        "*.tmp",
        "*.bak",
        "*~",
        ".env",
        ".env.*",
        "api-tokens.json",
    }

    for part in rel_path.parts:
        if part in standard_ignored_names:
            return True
        for pattern in standard_ignored_globs:
            if fnmatch.fnmatch(part, pattern):
                return True

    # Check if any part matches custom patterns from workspace .gitignore
    gitignore_file = abs_root / ".gitignore"
    if gitignore_file.is_file():
        try:
            lines = gitignore_file.read_text(encoding="utf-8").splitlines()
        except OSError:
            lines = []

        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("!"):
                continue

            pattern = line
            if pattern.endswith("/"):
                pattern = pattern[:-1]

            if pattern.startswith("/"):
                pattern_sub = pattern[1:]
                if fnmatch.fnmatch(rel_path.as_posix(), pattern_sub) or fnmatch.fnmatch(
                    rel_path.as_posix(), f"{pattern_sub}/*"
                ):
                    return True
            else:
                for part in rel_path.parts:
                    if fnmatch.fnmatch(part, pattern):
                        return True
                if fnmatch.fnmatch(
                    rel_path.as_posix(), f"**/{pattern}/**"
                ) or fnmatch.fnmatch(rel_path.as_posix(), pattern):
                    return True

    return False


class GitStatusExecutor:
    """Execute the structured git.status read operation."""

    definition = _DEFINITIONS["git.status"]

    def __init__(self, runner: ProcessRunner) -> None:
        self._runner = runner

    async def execute(
        self,
        call: ToolCall,
        *,
        workspace_root: Path,
    ) -> ToolExecutionResult:
        """Return concise repository status without accepting arbitrary flags."""

        root = _resolve_workspace(workspace_root)
        _validate_call(call, self.definition, {"include_untracked"})
        include_untracked = _optional_bool(
            call.arguments,
            "include_untracked",
            default=True,
        )
        arguments = ["status", "--short", "--branch"]
        if not include_untracked:
            arguments.append("--untracked-files=no")
        result = await _run_tool(
            runner=self._runner,
            call=call,
            definition=self.definition,
            request=ProcessRequest(
                executable="git",
                arguments=tuple(arguments),
                cwd=root,
                timeout_seconds=self.definition.timeout_seconds,
            ),
        )
        if not result.succeeded or not result.output:
            return result

        filtered_lines = []
        for line in result.output.splitlines():
            if len(line) > 3:
                status_path = line[3:].strip()
                if " -> " in status_path:
                    status_path = status_path.split(" -> ", 1)[-1].strip()
                if should_ignore_path(root / status_path, root):
                    continue
            filtered_lines.append(line)

        return ToolExecutionResult(
            tool_call_id=result.tool_call_id,
            tool_name=result.tool_name,
            succeeded=True,
            output="\n".join(filtered_lines),
            truncated=result.truncated,
            duration_ms=result.duration_ms,
        )


class GitDiffExecutor:
    """Execute the structured git.diff read operation."""

    definition = _DEFINITIONS["git.diff"]

    def __init__(self, runner: ProcessRunner) -> None:
        self._runner = runner

    async def execute(
        self,
        call: ToolCall,
        *,
        workspace_root: Path,
    ) -> ToolExecutionResult:
        """Return a bounded Git diff for the whole workspace or one path."""

        root = _resolve_workspace(workspace_root)
        _validate_call(call, self.definition, {"staged", "path"})
        staged = _optional_bool(call.arguments, "staged", default=False)
        target = _optional_path(call.arguments, root)
        arguments = ["diff", "--no-ext-diff"]
        if staged:
            arguments.append("--cached")
        arguments.append("--")
        if target is not None:
            arguments.append(target)
        return await _run_tool(
            runner=self._runner,
            call=call,
            definition=self.definition,
            request=ProcessRequest(
                executable="git",
                arguments=tuple(arguments),
                cwd=root,
                timeout_seconds=self.definition.timeout_seconds,
            ),
        )


class FileSearchExecutor:
    """Execute fixed-string workspace search through ripgrep."""

    definition = _DEFINITIONS["file.search"]

    def __init__(self, runner: ProcessRunner) -> None:
        self._runner = runner

    async def execute(
        self,
        call: ToolCall,
        *,
        workspace_root: Path,
    ) -> ToolExecutionResult:
        """Search workspace files with bounded results and no regex input."""

        root = _resolve_workspace(workspace_root)
        _validate_call(call, self.definition, {"query", "path", "max_results"})
        query = _required_string(call.arguments, "query")
        target = _optional_path(call.arguments, root) or "."
        max_results = _optional_int(
            call.arguments,
            "max_results",
            default=50,
            minimum=1,
            maximum=200,
        )
        result = await _run_tool(
            runner=self._runner,
            call=call,
            definition=self.definition,
            request=ProcessRequest(
                executable="rg",
                arguments=(
                    "--line-number",
                    "--no-heading",
                    "--color",
                    "never",
                    "--fixed-strings",
                    "--max-filesize",
                    "1M",
                    "--",
                    query,
                    target,
                ),
                cwd=root,
                timeout_seconds=self.definition.timeout_seconds,
            ),
            successful_return_codes=frozenset({0, 1}),
        )
        if not result.succeeded:
            return result

        lines = result.output.splitlines()
        filtered_lines = []
        for line in lines:
            parts = line.split(":", 2)
            if len(parts) >= 2:
                file_rel_path = parts[0]
                if should_ignore_path(root / file_rel_path, root):
                    continue
            filtered_lines.append(line)

        limited_output = "\n".join(filtered_lines[:max_results])
        was_truncated = result.truncated or len(filtered_lines) > max_results
        return ToolExecutionResult(
            tool_call_id=result.tool_call_id,
            tool_name=result.tool_name,
            succeeded=True,
            output=limited_output,
            truncated=was_truncated,
            duration_ms=result.duration_ms,
        )


def _resolve_workspace(workspace_root: Path) -> Path:
    try:
        root = workspace_root.resolve(strict=True)
    except OSError as exc:
        raise ToolExecutionError("Workspace does not exist") from exc
    if not root.is_dir():
        raise ToolExecutionError("Workspace must be a directory")
    return root


def _validate_call(
    call: ToolCall,
    definition: ToolDefinition,
    allowed_arguments: set[str],
) -> None:
    if call.name != definition.name:
        raise ToolExecutionError(
            f"Executor for '{definition.name}' cannot run '{call.name}'"
        )
    if call.risk is not ToolRisk.READ:
        raise ToolExecutionError("Read-only executor requires read risk")
    unknown_arguments = set(call.arguments) - allowed_arguments
    if unknown_arguments:
        names = ", ".join(sorted(unknown_arguments))
        raise ToolExecutionError(f"Unsupported tool arguments: {names}")


def _optional_bool(
    arguments: Mapping[str, JsonValue],
    name: str,
    *,
    default: bool,
) -> bool:
    value = arguments.get(name, default)
    if not isinstance(value, bool):
        raise ToolExecutionError(f"Tool argument '{name}' must be a boolean")
    return value


def _required_string(
    arguments: Mapping[str, JsonValue],
    name: str,
) -> str:
    value = arguments.get(name)
    if not isinstance(value, str) or not value.strip():
        raise ToolExecutionError(f"Tool argument '{name}' must be a non-empty string")
    return value.strip()


def _optional_int(
    arguments: Mapping[str, JsonValue],
    name: str,
    *,
    default: int,
    minimum: int,
    maximum: int,
) -> int:
    value = arguments.get(name, default)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ToolExecutionError(f"Tool argument '{name}' must be an integer")
    if value < minimum or value > maximum:
        raise ToolExecutionError(
            f"Tool argument '{name}' must be between {minimum} and {maximum}"
        )
    return value


def _optional_path(
    arguments: Mapping[str, JsonValue],
    workspace_root: Path,
) -> str | None:
    value = arguments.get("path")
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ToolExecutionError("Tool argument 'path' must be a non-empty string")
    candidate_input = Path(value.strip())
    if candidate_input.is_absolute():
        raise ToolExecutionError("Tool path must be relative to the workspace")
    candidate = (workspace_root / candidate_input).resolve(strict=False)
    if candidate != workspace_root and workspace_root not in candidate.parents:
        raise ToolExecutionError("Tool path escapes the workspace")
    if should_ignore_path(candidate, workspace_root):
        raise ToolExecutionError("Tool path is ignored by workspace rules")
    return candidate.relative_to(workspace_root).as_posix()


async def _run_tool(
    *,
    runner: ProcessRunner,
    call: ToolCall,
    definition: ToolDefinition,
    request: ProcessRequest,
    successful_return_codes: frozenset[int] = frozenset({0}),
) -> ToolExecutionResult:
    try:
        process_result = await runner.run(request)
    except ProcessRunnerError as exc:
        error, truncated = _bounded_text(str(exc))
        return ToolExecutionResult(
            tool_call_id=call.id,
            tool_name=call.name,
            succeeded=False,
            error=error,
            truncated=truncated,
        )
    return _process_tool_result(
        call,
        process_result,
        successful_return_codes=successful_return_codes,
    )


def _process_tool_result(
    call: ToolCall,
    process_result: ProcessResult,
    *,
    successful_return_codes: frozenset[int],
) -> ToolExecutionResult:
    succeeded = process_result.return_code in successful_return_codes
    output, output_truncated = _bounded_text(process_result.stdout.strip())
    error_text = process_result.stderr.strip()
    if not succeeded and not error_text:
        error_text = f"Tool process exited with code {process_result.return_code}"
    error, error_truncated = _bounded_text(error_text)
    return ToolExecutionResult(
        tool_call_id=call.id,
        tool_name=call.name,
        succeeded=succeeded,
        output=output,
        error=None if succeeded else error,
        truncated=output_truncated or error_truncated,
        duration_ms=process_result.duration_ms,
    )


def _bounded_text(value: str) -> tuple[str, bool]:
    if len(value) <= MAX_TOOL_OUTPUT_LENGTH:
        return value, False
    return value[:MAX_TOOL_OUTPUT_LENGTH], True
