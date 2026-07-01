"""Tests for approval-gated write tool definitions."""

from kelvin_assistant.domain.agent import (
    ToolExecutionTarget,
    ToolRisk,
)
from kelvin_assistant.tools.write_definitions import write_tool_definitions


def test_file_patch_is_a_windows_write_tool() -> None:
    """The initial patch tool always requires backend approval."""

    (definition,) = write_tool_definitions()

    assert definition.name == "file.patch"
    assert definition.risk is ToolRisk.WRITE
    assert definition.execution_target is ToolExecutionTarget.WINDOWS_CLIENT
    assert definition.input_schema["required"] == (
        "path",
        "old_text",
        "new_text",
    )
