"""Unit tests for the initial read-only tool definitions."""

from kelvin_assistant.domain.agent import ToolExecutionTarget, ToolRisk
from kelvin_assistant.tools.read_definitions import read_tool_definitions


def test_read_tool_definitions_are_windows_read_only_tools() -> None:
    """The first tool set contains only the three approved read operations."""

    definitions = read_tool_definitions()

    assert [definition.name for definition in definitions] == [
        "file.search",
        "git.diff",
        "git.status",
    ]
    assert all(definition.risk is ToolRisk.READ for definition in definitions)
    assert all(
        definition.execution_target is ToolExecutionTarget.WINDOWS_CLIENT
        for definition in definitions
    )
