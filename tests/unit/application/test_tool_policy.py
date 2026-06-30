"""Unit tests for deterministic agent tool policy."""

import pytest

from kelvin_assistant.application.tool_policy import (
    DefaultToolPolicy,
    ToolPolicyContext,
)
from kelvin_assistant.domain.agent import (
    ToolCall,
    ToolDefinition,
    ToolExecutionTarget,
    ToolPolicyDecision,
    ToolRisk,
)
from kelvin_assistant.tools.registry import StaticToolRegistry


def _definition(name: str, risk: ToolRisk) -> ToolDefinition:
    return ToolDefinition(
        name=name,
        description=f"Execute {name}.",
        input_schema={"type": "object"},
        risk=risk,
        execution_target=ToolExecutionTarget.WINDOWS_CLIENT,
    )


def _call(name: str, risk: ToolRisk) -> ToolCall:
    return ToolCall(
        name=name,
        arguments={"workspace": "C:\\project"},
        reason="Complete the requested task.",
        expected_effect="Depends on the registered operation.",
        risk=risk,
    )


def _policy(*definitions: ToolDefinition) -> DefaultToolPolicy:
    return DefaultToolPolicy(StaticToolRegistry(definitions))


def test_policy_allows_registered_read_tool_in_authorized_workspace() -> None:
    """Read tools can execute automatically inside an authorized workspace."""

    result = _policy(_definition("git.status", ToolRisk.READ)).evaluate(
        _call("git.status", ToolRisk.READ),
        context=ToolPolicyContext(workspace_authorized=True),
    )

    assert result.decision is ToolPolicyDecision.ALLOW


def test_policy_requires_approval_for_write_tool() -> None:
    """Write tools cannot execute without an explicit approval step."""

    result = _policy(_definition("file.patch", ToolRisk.WRITE)).evaluate(
        _call("file.patch", ToolRisk.WRITE),
        context=ToolPolicyContext(workspace_authorized=True),
    )

    assert result.decision is ToolPolicyDecision.REQUIRE_APPROVAL


@pytest.mark.parametrize("risk", [ToolRisk.DESTRUCTIVE, ToolRisk.PRIVILEGED])
def test_policy_denies_disabled_risk_levels(risk: ToolRisk) -> None:
    """Destructive and privileged tools remain disabled in v0.6."""

    result = _policy(_definition("system.change", risk)).evaluate(
        _call("system.change", risk),
        context=ToolPolicyContext(workspace_authorized=True),
    )

    assert result.decision is ToolPolicyDecision.DENY
    assert risk in result.reason


def test_policy_denies_unknown_tool() -> None:
    """A model cannot invent a tool that is absent from the registry."""

    result = _policy().evaluate(
        _call("git.status", ToolRisk.READ),
        context=ToolPolicyContext(workspace_authorized=True),
    )

    assert result.decision is ToolPolicyDecision.DENY
    assert "not registered" in result.reason


def test_policy_denies_unauthorized_workspace() -> None:
    """Even read operations fail when the workspace is not authorized."""

    result = _policy(_definition("git.status", ToolRisk.READ)).evaluate(
        _call("git.status", ToolRisk.READ),
        context=ToolPolicyContext(workspace_authorized=False),
    )

    assert result.decision is ToolPolicyDecision.DENY
    assert "workspace" in result.reason


def test_policy_denies_risk_mismatch() -> None:
    """A proposed risk cannot downgrade the registered tool definition."""

    result = _policy(_definition("file.patch", ToolRisk.WRITE)).evaluate(
        _call("file.patch", ToolRisk.READ),
        context=ToolPolicyContext(workspace_authorized=True),
    )

    assert result.decision is ToolPolicyDecision.DENY
    assert "risk" in result.reason
