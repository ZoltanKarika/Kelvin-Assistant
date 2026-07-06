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


def test_policy_allows_valid_relative_path_for_write_tool() -> None:
    """A write tool with a valid relative path requires approval."""

    call = ToolCall(
        name="file.patch",
        arguments={"workspace": "C:\\project", "path": "src/utils.py"},
        reason="Update code.",
        expected_effect="Patch file.",
        risk=ToolRisk.WRITE,
    )
    result = _policy(_definition("file.patch", ToolRisk.WRITE)).evaluate(
        call,
        context=ToolPolicyContext(workspace_authorized=True),
    )

    assert result.decision is ToolPolicyDecision.REQUIRE_APPROVAL


@pytest.mark.parametrize(
    "invalid_path",
    [
        "/etc/passwd",
        "\\absolute\\path",
        "C:\\absolute\\path",
        "d:\\project\\file.txt",
        "../outside.txt",
        "src/../../outside.txt",
    ],
)
def test_policy_denies_invalid_path_for_write_tool(invalid_path: str) -> None:
    """A write tool with an absolute or traversing path is denied."""

    call = ToolCall(
        name="file.patch",
        arguments={"workspace": "C:\\project", "path": invalid_path},
        reason="Update code.",
        expected_effect="Patch file.",
        risk=ToolRisk.WRITE,
    )
    result = _policy(_definition("file.patch", ToolRisk.WRITE)).evaluate(
        call,
        context=ToolPolicyContext(workspace_authorized=True),
    )

    assert result.decision is ToolPolicyDecision.DENY
    assert "path" in result.reason


def test_policy_denies_non_string_path_for_write_tool() -> None:
    """A write tool with a non-string path argument is denied."""

    call = ToolCall(
        name="file.patch",
        arguments={"workspace": "C:\\project", "path": 123},
        reason="Update code.",
        expected_effect="Patch file.",
        risk=ToolRisk.WRITE,
    )
    result = _policy(_definition("file.patch", ToolRisk.WRITE)).evaluate(
        call,
        context=ToolPolicyContext(workspace_authorized=True),
    )

    assert result.decision is ToolPolicyDecision.DENY
    assert "must be a string" in result.reason
