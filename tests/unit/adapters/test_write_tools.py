"""Unit tests for approval-gated workspace file changes."""

import asyncio
from pathlib import Path

import pytest

from kelvin_assistant.adapters.write_tools import FilePatchExecutor
from kelvin_assistant.domain.agent import ToolCall, ToolRisk
from kelvin_assistant.ports.tools import ToolExecutionError


def _call(
    *,
    path: str = "notes.txt",
    old_text: str = "old value",
    new_text: str = "new value",
) -> ToolCall:
    return ToolCall(
        name="file.patch",
        arguments={
            "path": path,
            "old_text": old_text,
            "new_text": new_text,
        },
        reason="Update one documented value.",
        expected_effect="Replace one exact text occurrence.",
        risk=ToolRisk.WRITE,
    )


def test_patch_previews_then_atomically_updates_exact_file(
    tmp_path: Path,
) -> None:
    """Approved execution applies exactly the complete previewed change."""

    target = tmp_path / "notes.txt"
    target.write_text("before\nold value\nafter\n", encoding="utf-8", newline="")
    executor = FilePatchExecutor()
    call = _call()

    preview = asyncio.run(executor.preview(call, workspace_root=tmp_path))

    assert "--- a/notes.txt" in preview.content
    assert "+++ b/notes.txt" in preview.content
    assert "-old value" in preview.content
    assert "+new value" in preview.content
    assert target.read_text(encoding="utf-8") == "before\nold value\nafter\n"

    result = asyncio.run(executor.execute(call, workspace_root=tmp_path))

    assert result.succeeded
    assert result.output == "Updated notes.txt"
    assert target.read_text(encoding="utf-8") == "before\nnew value\nafter\n"


def test_patch_refuses_execution_without_preview(tmp_path: Path) -> None:
    """A backend approval cannot bypass the local preview boundary."""

    (tmp_path / "notes.txt").write_text("old value", encoding="utf-8")
    executor = FilePatchExecutor()

    with pytest.raises(ToolExecutionError, match="must be previewed"):
        asyncio.run(executor.execute(_call(), workspace_root=tmp_path))


def test_patch_refuses_file_changed_after_preview(tmp_path: Path) -> None:
    """Concurrent file changes invalidate the approval and prepared patch."""

    target = tmp_path / "notes.txt"
    target.write_text("old value", encoding="utf-8")
    executor = FilePatchExecutor()
    call = _call()
    asyncio.run(executor.preview(call, workspace_root=tmp_path))
    target.write_text("prefix old value", encoding="utf-8")

    with pytest.raises(ToolExecutionError, match="changed after preview"):
        asyncio.run(executor.execute(call, workspace_root=tmp_path))

    assert target.read_text(encoding="utf-8") == "prefix old value"


def test_patch_requires_old_text_to_be_unique(tmp_path: Path) -> None:
    """Ambiguous replacements fail closed rather than editing many locations."""

    (tmp_path / "notes.txt").write_text(
        "old value and old value",
        encoding="utf-8",
    )

    with pytest.raises(ToolExecutionError, match="exactly once"):
        asyncio.run(
            FilePatchExecutor().preview(
                _call(),
                workspace_root=tmp_path,
            )
        )


def test_patch_rejects_workspace_escape(tmp_path: Path) -> None:
    """Relative traversal cannot reach files outside the trusted workspace."""

    with pytest.raises(ToolExecutionError, match="escapes the workspace"):
        asyncio.run(
            FilePatchExecutor().preview(
                _call(path="../outside.txt"),
                workspace_root=tmp_path,
            )
        )
