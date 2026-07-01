"""Unit tests for the structured LLM agent planner adapter."""

import asyncio
import json
from collections.abc import AsyncIterator, Sequence

import pytest

from kelvin_assistant.adapters.llm_planner import StructuredLLMAgentPlanner
from kelvin_assistant.domain.agent import (
    ToolDefinition,
    ToolExecutionTarget,
    ToolRisk,
)
from kelvin_assistant.domain.chat import ChatMessage, ChatRole
from kelvin_assistant.domain.planner import (
    ClarifyDecision,
    CompleteDecision,
    PlannerRequest,
    ToolDecision,
)
from kelvin_assistant.ports.llm import LLMUnavailableError
from kelvin_assistant.ports.planner import (
    AgentPlannerResponseError,
    AgentPlannerUnavailableError,
)


def test_planner_parses_registered_tool_decision() -> None:
    """A valid JSON decision maps to the provider-independent domain."""

    provider = StubLLMProvider(
        responses=[
            json.dumps(
                {
                    "action": "tool",
                    "tool_name": "git.status",
                    "arguments": {"include_untracked": True},
                    "reason": "Inspect repository state.",
                    "expected_effect": "No workspace change.",
                }
            )
        ]
    )

    decision = asyncio.run(StructuredLLMAgentPlanner(provider).plan(_request()))

    assert isinstance(decision, ToolDecision)
    assert decision.tool_name == "git.status"
    assert decision.arguments == {"include_untracked": True}
    assert len(provider.calls) == 1
    system, user = provider.calls[0]
    assert system.role is ChatRole.SYSTEM
    assert "Never invent tools" in system.content
    request_payload = json.loads(user.content)
    assert request_payload["goal"] == "Inspect the repository."
    assert request_payload["remaining_steps"] == 3
    assert request_payload["tools"][0]["name"] == "git.status"


def test_planner_parses_clarification_decision() -> None:
    """A targeted question remains separate from execution approval."""

    provider = StubLLMProvider(
        responses=[
            json.dumps(
                {
                    "action": "clarify",
                    "question": "Which file should be changed?",
                    "reason": "The target file is missing.",
                }
            )
        ]
    )

    decision = asyncio.run(StructuredLLMAgentPlanner(provider).plan(_request()))

    assert decision == ClarifyDecision(
        question="Which file should be changed?",
        reason="The target file is missing.",
    )


def test_planner_parses_completion_decision() -> None:
    """The model can finish without inventing an unnecessary tool call."""

    provider = StubLLMProvider(
        responses=['{"action":"complete","summary":"No action is required."}']
    )

    decision = asyncio.run(StructuredLLMAgentPlanner(provider).plan(_request()))

    assert decision == CompleteDecision(summary="No action is required.")


def test_planner_repairs_invalid_json_once() -> None:
    """One malformed response gets one bounded correction attempt."""

    provider = StubLLMProvider(
        responses=[
            "```json\n{}\n```",
            '{"action":"complete","summary":"Finished."}',
        ]
    )

    decision = asyncio.run(StructuredLLMAgentPlanner(provider).plan(_request()))

    assert decision == CompleteDecision(summary="Finished.")
    assert len(provider.calls) == 2
    repair_messages = provider.calls[1]
    assert repair_messages[-2].role is ChatRole.ASSISTANT
    assert repair_messages[-2].content == "```json\n{}\n```"
    assert "Validation error" in repair_messages[-1].content


def test_planner_fails_after_second_invalid_response() -> None:
    """Two invalid responses fail closed without producing a decision."""

    provider = StubLLMProvider(responses=["not json", "still not json"])

    with pytest.raises(
        AgentPlannerResponseError,
        match="invalid structured output twice",
    ):
        asyncio.run(StructuredLLMAgentPlanner(provider).plan(_request()))

    assert len(provider.calls) == 2


def test_planner_rejects_unknown_tool_then_repairs() -> None:
    """A model-selected tool absent from the registry never reaches policy."""

    provider = StubLLMProvider(
        responses=[
            json.dumps(
                {
                    "action": "tool",
                    "tool_name": "powershell.run",
                    "arguments": {"command": "Remove-Item -Recurse"},
                    "reason": "Run a command.",
                    "expected_effect": "Files change.",
                }
            ),
            '{"action":"complete","summary":"Unsafe request rejected."}',
        ]
    )

    decision = asyncio.run(StructuredLLMAgentPlanner(provider).plan(_request()))

    assert decision == CompleteDecision(summary="Unsafe request rejected.")
    assert "unknown tool" in provider.calls[1][-1].content


def test_planner_rejects_extra_risk_or_command_fields() -> None:
    """The model cannot smuggle authorization or raw commands into output."""

    unsafe = json.dumps(
        {
            "action": "tool",
            "tool_name": "git.status",
            "arguments": {},
            "reason": "Inspect state.",
            "expected_effect": "No change.",
            "risk": "read",
            "command": "whoami",
        }
    )
    provider = StubLLMProvider(responses=[unsafe, unsafe])

    with pytest.raises(AgentPlannerResponseError):
        asyncio.run(StructuredLLMAgentPlanner(provider).plan(_request()))


def test_planner_rejects_nonstandard_json_constants() -> None:
    """NaN and Infinity cannot enter otherwise JSON-compatible arguments."""

    invalid = (
        '{"action":"tool","tool_name":"git.status",'
        '"arguments":{"value":NaN},"reason":"Inspect.",'
        '"expected_effect":"No change."}'
    )
    provider = StubLLMProvider(responses=[invalid, invalid])

    with pytest.raises(AgentPlannerResponseError):
        asyncio.run(StructuredLLMAgentPlanner(provider).plan(_request()))


def test_planner_translates_provider_unavailability() -> None:
    """An unreachable Ollama runtime retains a stable planner error."""

    provider = StubLLMProvider(
        responses=[],
        error=LLMUnavailableError("offline"),
    )

    with pytest.raises(
        AgentPlannerUnavailableError,
        match="unavailable",
    ):
        asyncio.run(StructuredLLMAgentPlanner(provider).plan(_request()))


def _request() -> PlannerRequest:
    return PlannerRequest.create(
        "Inspect the repository.",
        (
            ToolDefinition(
                name="git.status",
                description="Show concise Git repository status.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "include_untracked": {"type": "boolean"},
                    },
                    "additionalProperties": False,
                },
                risk=ToolRisk.READ,
                execution_target=ToolExecutionTarget.WINDOWS_CLIENT,
            ),
        ),
        remaining_steps=3,
    )


class StubLLMProvider:
    """Return queued chat responses and record planner prompts."""

    def __init__(
        self,
        *,
        responses: list[str],
        error: LLMUnavailableError | None = None,
    ) -> None:
        self._responses = responses
        self._error = error
        self.calls: list[tuple[ChatMessage, ...]] = []

    async def generate(self, prompt: str) -> str:
        raise NotImplementedError

    async def chat(self, messages: Sequence[ChatMessage]) -> str:
        self.calls.append(tuple(messages))
        if self._error is not None:
            raise self._error
        return self._responses.pop(0)

    async def stream_chat(
        self,
        messages: Sequence[ChatMessage],
    ) -> AsyncIterator[str]:
        if False:
            yield ""

    async def check_readiness(self) -> None:
        return None
