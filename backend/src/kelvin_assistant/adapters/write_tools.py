"""Approval-gated local executors for workspace file changes."""

from __future__ import annotations

import difflib
import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from uuid import UUID

from kelvin_assistant.domain.agent import (
    MAX_TOOL_OUTPUT_LENGTH,
    ToolCall,
    ToolDefinition,
    ToolExecutionResult,
    ToolRisk,
)
from kelvin_assistant.ports.tools import ToolExecutionError, ToolPreview
from kelvin_assistant.tools.write_definitions import write_tool_definitions

MAX_PATCH_FILE_BYTES = 1_048_576
MAX_PATCH_TEXT_LENGTH = 32_768
_DEFINITIONS = {definition.name: definition for definition in write_tool_definitions()}


@dataclass(frozen=True, slots=True)
class _PreparedPatch:
    """Exact file state retained between preview and approved execution."""

    path: Path
    relative_path: str
    original: str
    updated: str
    preview: str


class FilePatchExecutor:
    """Replace one exact string after a complete unified-diff preview."""

    definition = _DEFINITIONS["file.patch"]

    def __init__(self) -> None:
        self._prepared: dict[UUID, _PreparedPatch] = {}

    async def preview(
        self,
        call: ToolCall,
        *,
        workspace_root: Path,
    ) -> ToolPreview:
        """Validate and retain the exact file version shown to the user."""

        prepared = _prepare_patch(call, workspace_root, self.definition)
        self._prepared[call.id] = prepared
        return ToolPreview(content=prepared.preview)

    async def execute(
        self,
        call: ToolCall,
        *,
        workspace_root: Path,
    ) -> ToolExecutionResult:
        """Atomically apply only the exact patch that was previewed."""

        started_at = perf_counter()
        prepared = self._prepared.pop(call.id, None)
        if prepared is None:
            raise ToolExecutionError("File patch must be previewed before execution")

        root = _resolve_workspace(workspace_root)
        if prepared.path.parent != root and root not in prepared.path.parents:
            raise ToolExecutionError("Prepared patch escapes the workspace")

        current = _read_utf8(prepared.path)
        if current != prepared.original:
            raise ToolExecutionError("File changed after preview; prepare a new patch")

        _atomic_write_utf8(prepared.path, prepared.updated)
        duration_ms = int((perf_counter() - started_at) * 1000)
        return ToolExecutionResult(
            tool_call_id=call.id,
            tool_name=call.name,
            succeeded=True,
            output=f"Updated {prepared.relative_path}",
            duration_ms=duration_ms,
        )


def _prepare_patch(
    call: ToolCall,
    workspace_root: Path,
    definition: ToolDefinition,
) -> _PreparedPatch:
    root = _resolve_workspace(workspace_root)
    _validate_call(call, definition)
    relative_path = _required_text(call, "path")
    old_text = _required_text(call, "old_text")
    new_text = _required_string(call, "new_text")
    if len(old_text) > MAX_PATCH_TEXT_LENGTH or len(new_text) > MAX_PATCH_TEXT_LENGTH:
        raise ToolExecutionError(
            f"Patch text cannot exceed {MAX_PATCH_TEXT_LENGTH} characters"
        )

    path = _resolve_file(root, relative_path)
    original = _read_utf8(path)
    occurrence_count = original.count(old_text)
    if occurrence_count != 1:
        raise ToolExecutionError(
            "Patch old_text must occur exactly once in the target file"
        )
    updated = original.replace(old_text, new_text, 1)
    if updated == original:
        raise ToolExecutionError("File patch would not change the target file")

    normalized_path = path.relative_to(root).as_posix()
    preview = "".join(
        difflib.unified_diff(
            original.splitlines(keepends=True),
            updated.splitlines(keepends=True),
            fromfile=f"a/{normalized_path}",
            tofile=f"b/{normalized_path}",
        )
    )
    if len(preview) > MAX_TOOL_OUTPUT_LENGTH:
        raise ToolExecutionError("Patch preview is too large for safe approval")
    return _PreparedPatch(
        path=path,
        relative_path=normalized_path,
        original=original,
        updated=updated,
        preview=preview,
    )


def _resolve_workspace(workspace_root: Path) -> Path:
    try:
        root = workspace_root.resolve(strict=True)
    except OSError as exc:
        raise ToolExecutionError("Workspace does not exist") from exc
    if not root.is_dir():
        raise ToolExecutionError("Workspace must be a directory")
    return root


def _resolve_file(workspace_root: Path, relative_path: str) -> Path:
    candidate_input = Path(relative_path)
    if candidate_input.is_absolute():
        raise ToolExecutionError("Tool path must be relative to the workspace")
    unresolved_candidate = (workspace_root / candidate_input).resolve(strict=False)
    if workspace_root not in unresolved_candidate.parents:
        raise ToolExecutionError("Tool path escapes the workspace")
    try:
        candidate = (workspace_root / candidate_input).resolve(strict=True)
    except OSError as exc:
        raise ToolExecutionError("Patch target file does not exist") from exc
    if workspace_root not in candidate.parents:
        raise ToolExecutionError("Tool path escapes the workspace")
    if not candidate.is_file():
        raise ToolExecutionError("Patch target must be a regular file")
    try:
        size = candidate.stat().st_size
    except OSError as exc:
        raise ToolExecutionError("Cannot inspect patch target file") from exc
    if size > MAX_PATCH_FILE_BYTES:
        raise ToolExecutionError(
            f"Patch target cannot exceed {MAX_PATCH_FILE_BYTES} bytes"
        )
    return candidate


def _validate_call(call: ToolCall, definition: ToolDefinition) -> None:
    if call.name != definition.name:
        raise ToolExecutionError(
            f"Executor for '{definition.name}' cannot run '{call.name}'"
        )
    if call.risk is not ToolRisk.WRITE:
        raise ToolExecutionError("File patch executor requires write risk")
    unknown_arguments = set(call.arguments) - {"path", "old_text", "new_text"}
    if unknown_arguments:
        names = ", ".join(sorted(unknown_arguments))
        raise ToolExecutionError(f"Unsupported tool arguments: {names}")


def _required_text(call: ToolCall, name: str) -> str:
    value = _required_string(call, name)
    if not value:
        raise ToolExecutionError(f"Tool argument '{name}' must be a non-empty string")
    return value


def _required_string(call: ToolCall, name: str) -> str:
    value = call.arguments.get(name)
    if not isinstance(value, str):
        raise ToolExecutionError(f"Tool argument '{name}' must be a string")
    return value


def _read_utf8(path: Path) -> str:
    try:
        with path.open("r", encoding="utf-8", newline="") as stream:
            return stream.read()
    except UnicodeDecodeError as exc:
        raise ToolExecutionError("Patch target must be UTF-8 text") from exc
    except OSError as exc:
        raise ToolExecutionError("Cannot read patch target file") from exc


def _atomic_write_utf8(path: Path, content: str) -> None:
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            newline="",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".kelvin.tmp",
            delete=False,
        ) as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
            temporary_path = Path(stream.name)
        shutil.copymode(path, temporary_path)
        os.replace(temporary_path, path)
    except OSError as exc:
        raise ToolExecutionError("Cannot atomically update patch target") from exc
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink(missing_ok=True)
