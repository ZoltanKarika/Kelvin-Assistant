"""Deterministic authorization policy for proposed agent tool calls."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from kelvin_assistant.domain.agent import ToolCall, ToolRisk
from kelvin_assistant.ports.tools import ToolRegistry, UnknownToolError


class ToolPolicyDecision(StrEnum):
    """Authorization result for one proposed tool call."""

    ALLOW = "allow"
    REQUIRE_APPROVAL = "require_approval"
    DENY = "deny"


@dataclass(frozen=True, slots=True)
class ToolPolicyContext:
    """Trusted facts supplied by the execution boundary."""

    workspace_authorized: bool


@dataclass(frozen=True, slots=True)
class ToolPolicyResult:
    """A policy decision with a user-readable reason."""

    decision: ToolPolicyDecision
    reason: str


class DefaultToolPolicy:
    """Fail-closed policy for the first v0.6 tool set."""

    def __init__(self, registry: ToolRegistry) -> None:
        """Create a policy backed by the configured tool registry."""

        self._registry = registry

    def evaluate(
        self,
        call: ToolCall,
        *,
        context: ToolPolicyContext,
    ) -> ToolPolicyResult:
        """Classify a tool call without consulting the language model."""

        try:
            definition = self._registry.get(call.name)
        except UnknownToolError:
            return ToolPolicyResult(
                decision=ToolPolicyDecision.DENY,
                reason="The requested tool is not registered.",
            )

        if not context.workspace_authorized:
            return ToolPolicyResult(
                decision=ToolPolicyDecision.DENY,
                reason="The requested workspace is not authorized.",
            )

        if call.risk is not definition.risk:
            return ToolPolicyResult(
                decision=ToolPolicyDecision.DENY,
                reason="The proposed risk does not match the registered tool.",
            )

        if definition.risk in {ToolRisk.DESTRUCTIVE, ToolRisk.PRIVILEGED}:
            return ToolPolicyResult(
                decision=ToolPolicyDecision.DENY,
                reason=f"{definition.risk} tools are disabled in v0.6.",
            )

        if definition.risk is ToolRisk.WRITE:
            return ToolPolicyResult(
                decision=ToolPolicyDecision.REQUIRE_APPROVAL,
                reason="State-changing tools require explicit user approval.",
            )

        return ToolPolicyResult(
            decision=ToolPolicyDecision.ALLOW,
            reason="Read-only tool is allowed in the authorized workspace.",
        )
