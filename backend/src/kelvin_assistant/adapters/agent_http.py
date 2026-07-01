"""HTTP adapter for the versioned Kelvin agent API."""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Any, cast
from uuid import UUID

import httpx2

from kelvin_assistant.domain.agent import (
    AgentRun,
    AgentStatus,
    JsonValue,
    ToolCall,
    ToolExecutionResult,
    ToolPolicyDecision,
    ToolPolicyResult,
    ToolProposal,
    ToolRisk,
)
from kelvin_assistant.ports.agent_client import (
    AgentClientResponseError,
    AgentClientUnavailableError,
)


class HttpAgentApiClient:
    """Call Kelvin agent endpoints over the local host-to-VM network."""

    def __init__(
        self,
        base_url: str,
        *,
        timeout_seconds: float = 30.0,
        transport: httpx2.AsyncBaseTransport | None = None,
    ) -> None:
        """Configure the client with an injectable HTTP transport."""

        normalized_url = base_url.rstrip("/")
        if not normalized_url:
            raise ValueError("Agent API URL cannot be empty")
        if timeout_seconds <= 0:
            raise ValueError("Agent API timeout must be positive")
        self._base_url = normalized_url
        self._timeout_seconds = timeout_seconds
        self._transport = transport

    async def create_run(
        self,
        *,
        goal: str,
        workspace_id: str,
    ) -> AgentRun:
        """Create one server-managed agent run."""

        payload = await self._request(
            "POST",
            "/api/v1/agent/runs",
            {
                "goal": goal,
                "workspace_id": workspace_id,
            },
        )
        return _parse_run(payload)

    async def begin_planning(self, run_id: UUID) -> AgentRun:
        """Move one server-managed run into planning."""

        payload = await self._request(
            "POST",
            f"/api/v1/agent/runs/{run_id}/plan",
        )
        return _parse_run(payload)

    async def propose_tool(
        self,
        run_id: UUID,
        *,
        name: str,
        arguments: Mapping[str, JsonValue],
        reason: str,
        expected_effect: str,
        risk: ToolRisk,
    ) -> ToolProposal:
        """Submit one tool proposal and parse deterministic server policy."""

        payload = await self._request(
            "POST",
            f"/api/v1/agent/runs/{run_id}/tools",
            {
                "name": name,
                "arguments": _thaw_json(arguments),
                "reason": reason,
                "expected_effect": expected_effect,
                "risk": risk.value,
            },
        )
        return _parse_proposal(payload)

    async def resolve_approval(
        self,
        run_id: UUID,
        *,
        tool_call_id: UUID,
        approved: bool,
    ) -> ToolProposal:
        """Submit one explicit local user decision for a pending tool."""

        payload = await self._request(
            "POST",
            f"/api/v1/agent/runs/{run_id}/approval",
            {
                "tool_call_id": str(tool_call_id),
                "decision": "approved" if approved else "rejected",
            },
        )
        return _parse_proposal(payload)

    async def submit_result(
        self,
        run_id: UUID,
        result: ToolExecutionResult,
    ) -> AgentRun:
        """Submit one local tool result and return the updated run."""

        payload = await self._request(
            "POST",
            f"/api/v1/agent/runs/{run_id}/result",
            {
                "tool_call_id": str(result.tool_call_id),
                "succeeded": result.succeeded,
                "output": result.output,
                "error": result.error,
                "truncated": result.truncated,
                "duration_ms": result.duration_ms,
            },
        )
        try:
            return _parse_run(_require_mapping(payload["run"]))
        except (KeyError, TypeError, ValueError) as exc:
            raise AgentClientResponseError(
                "Kelvin API returned an invalid tool result response"
            ) from exc

    async def _request(
        self,
        method: str,
        path: str,
        payload: Mapping[str, object] | None = None,
    ) -> Mapping[str, Any]:
        try:
            async with httpx2.AsyncClient(
                base_url=self._base_url,
                timeout=self._timeout_seconds,
                transport=self._transport,
            ) as client:
                response = await client.request(method, path, json=payload)
            response.raise_for_status()
        except httpx2.RequestError as exc:
            raise AgentClientUnavailableError(
                "Kelvin agent API is unavailable"
            ) from exc
        except httpx2.HTTPStatusError as exc:
            detail = _response_error_detail(exc.response)
            raise AgentClientResponseError(
                f"Kelvin agent API rejected the request: {detail}"
            ) from exc

        try:
            return _require_mapping(response.json())
        except (TypeError, ValueError) as exc:
            raise AgentClientResponseError(
                "Kelvin agent API returned invalid JSON"
            ) from exc


def _parse_run(payload: Mapping[str, Any]) -> AgentRun:
    try:
        workspace_id = payload.get("workspace_id")
        if workspace_id is not None:
            workspace_id = _require_string(workspace_id)
        return AgentRun(
            id=UUID(_require_string(payload["id"])),
            goal=_require_string(payload["goal"]),
            status=AgentStatus(_require_string(payload["status"])),
            step_count=_require_int(payload["step_count"]),
            max_steps=_require_int(payload["max_steps"]),
            version=_require_int(payload["version"]),
            workspace_id=workspace_id,
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise AgentClientResponseError(
            "Kelvin API returned an invalid agent run"
        ) from exc


def _parse_proposal(payload: Mapping[str, Any]) -> ToolProposal:
    try:
        run_payload = _require_mapping(payload["run"])
        call = ToolCall(
            id=UUID(_require_string(payload["tool_call_id"])),
            name=_require_string(payload["tool_name"]),
            arguments=_freeze_json_mapping(payload["arguments"]),
            reason=_require_string(payload["reason"]),
            expected_effect=_require_string(payload["expected_effect"]),
            risk=ToolRisk(_require_string(payload["risk"])),
        )
        return ToolProposal(
            run=_parse_run(run_payload),
            call=call,
            policy_result=ToolPolicyResult(
                decision=ToolPolicyDecision(
                    _require_string(payload["policy_decision"])
                ),
                reason=_require_string(payload["policy_reason"]),
            ),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise AgentClientResponseError(
            "Kelvin API returned an invalid tool proposal"
        ) from exc


def _freeze_json_mapping(value: object) -> Mapping[str, JsonValue]:
    mapping = _require_mapping(value)
    return MappingProxyType(
        {str(key): _freeze_json(item) for key, item in mapping.items()}
    )


def _freeze_json(value: object) -> JsonValue:
    if isinstance(value, dict):
        return _freeze_json_mapping(value)
    if isinstance(value, list):
        return tuple(_freeze_json(item) for item in value)
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError("Value is not JSON-compatible")


def _thaw_json(value: JsonValue) -> object:
    if isinstance(value, Mapping):
        return {key: _thaw_json(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw_json(item) for item in value]
    return value


def _require_mapping(value: object) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise TypeError("Expected JSON object")
    return cast(Mapping[str, Any], value)


def _require_string(value: object) -> str:
    if not isinstance(value, str):
        raise TypeError("Expected string")
    return value


def _require_int(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError("Expected integer")
    return value


def _response_error_detail(response: httpx2.Response) -> str:
    try:
        payload = response.json()
        if isinstance(payload, dict) and isinstance(payload.get("detail"), str):
            return cast(str, payload["detail"])
    except ValueError:
        pass
    return f"HTTP {response.status_code}"
