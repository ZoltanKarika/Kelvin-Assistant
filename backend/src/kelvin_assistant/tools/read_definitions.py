"""Definitions for the first read-only Windows client tools."""

from kelvin_assistant.domain.agent import (
    ToolDefinition,
    ToolExecutionTarget,
    ToolRisk,
)


def read_tool_definitions() -> tuple[ToolDefinition, ...]:
    """Return immutable definitions for the initial read-only tool set."""

    return (
        ToolDefinition(
            name="file.search",
            description="Search for fixed text inside files in the workspace.",
            input_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "path": {"type": "string"},
                    "max_results": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 200,
                    },
                },
                "required": ("query",),
                "additionalProperties": False,
            },
            risk=ToolRisk.READ,
            execution_target=ToolExecutionTarget.WINDOWS_CLIENT,
            timeout_seconds=30,
        ),
        ToolDefinition(
            name="git.diff",
            description="Show unstaged or staged Git changes in the workspace.",
            input_schema={
                "type": "object",
                "properties": {
                    "staged": {"type": "boolean"},
                    "path": {"type": "string"},
                },
                "additionalProperties": False,
            },
            risk=ToolRisk.READ,
            execution_target=ToolExecutionTarget.WINDOWS_CLIENT,
            timeout_seconds=30,
        ),
        ToolDefinition(
            name="git.status",
            description="Show concise Git repository status for the workspace.",
            input_schema={
                "type": "object",
                "properties": {
                    "include_untracked": {"type": "boolean"},
                },
                "additionalProperties": False,
            },
            risk=ToolRisk.READ,
            execution_target=ToolExecutionTarget.WINDOWS_CLIENT,
            timeout_seconds=15,
        ),
    )
