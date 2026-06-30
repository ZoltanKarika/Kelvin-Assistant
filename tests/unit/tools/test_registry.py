"""Unit tests for the static tool registry."""

import pytest

from kelvin_assistant.domain.agent import (
    AgentDomainError,
    ToolDefinition,
    ToolExecutionTarget,
    ToolRisk,
)
from kelvin_assistant.ports.tools import DuplicateToolError, UnknownToolError
from kelvin_assistant.tools.registry import StaticToolRegistry


def _definition(
    name: str,
    *,
    risk: ToolRisk = ToolRisk.READ,
) -> ToolDefinition:
    return ToolDefinition(
        name=name,
        description=f"Execute {name}.",
        input_schema={
            "type": "object",
            "properties": {
                "workspace": {"type": "string"},
            },
            "required": ("workspace",),
        },
        risk=risk,
        execution_target=ToolExecutionTarget.WINDOWS_CLIENT,
    )


def test_tool_definition_normalizes_and_freezes_schema() -> None:
    """Definitions expose normalized metadata and immutable schemas."""

    definition = ToolDefinition(
        name=" git.status ",
        description="  Show repository state.  ",
        input_schema={"type": "object"},
        risk=ToolRisk.READ,
        execution_target=ToolExecutionTarget.WINDOWS_CLIENT,
        timeout_seconds=10,
    )

    assert definition.name == "git.status"
    assert definition.description == "Show repository state."
    assert definition.input_schema == {"type": "object"}
    assert definition.timeout_seconds == 10

    with pytest.raises(TypeError):
        definition.input_schema["type"] = "array"  # type: ignore[index]


@pytest.mark.parametrize("timeout_seconds", [0, 301])
def test_tool_definition_rejects_invalid_timeout(timeout_seconds: int) -> None:
    """Definitions require a bounded positive timeout."""

    with pytest.raises(AgentDomainError, match="timeout"):
        ToolDefinition(
            name="git.status",
            description="Show repository state.",
            input_schema={"type": "object"},
            risk=ToolRisk.READ,
            execution_target=ToolExecutionTarget.WINDOWS_CLIENT,
            timeout_seconds=timeout_seconds,
        )


def test_registry_returns_tools_in_deterministic_order() -> None:
    """Registry lookup is exact and listing is sorted by tool name."""

    registry = StaticToolRegistry(
        [
            _definition("git.status"),
            _definition("file.search"),
            _definition("git.diff"),
        ]
    )

    assert registry.get("git.status").name == "git.status"
    assert [tool.name for tool in registry.list_all()] == [
        "file.search",
        "git.diff",
        "git.status",
    ]


def test_registry_rejects_duplicate_names() -> None:
    """Two tools cannot share the same stable name."""

    definition = _definition("git.status")

    with pytest.raises(DuplicateToolError, match="already registered"):
        StaticToolRegistry([definition, definition])


def test_registry_rejects_unknown_tool() -> None:
    """Unknown tools fail closed instead of returning a fallback."""

    registry = StaticToolRegistry([_definition("git.status")])

    with pytest.raises(UnknownToolError, match="not registered"):
        registry.get("git.diff")
