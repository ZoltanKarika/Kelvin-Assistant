"""Definitions for approval-gated Windows client write tools."""

from kelvin_assistant.domain.agent import (
    ToolDefinition,
    ToolExecutionTarget,
    ToolRisk,
)


def write_tool_definitions() -> tuple[ToolDefinition, ...]:
    """Return immutable definitions for the initial write tool set."""

    return (
        ToolDefinition(
            name="file.patch",
            description=(
                "Replace one exact text occurrence in a UTF-8 workspace file "
                "after showing a complete unified diff."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "old_text": {"type": "string"},
                    "new_text": {"type": "string"},
                },
                "required": ("path", "old_text", "new_text"),
                "additionalProperties": False,
            },
            risk=ToolRisk.WRITE,
            execution_target=ToolExecutionTarget.WINDOWS_CLIENT,
            timeout_seconds=15,
        ),
    )
