"""Structured tool execution safety tests."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from muxtrail.agents.runtime.embedded.tool_loop import run_tool_loop
from muxtrail.tools.execution import execute_tool
from muxtrail.tools.policy import ToolPolicy
from muxtrail.tools.registry import ToolRegistry
from muxtrail.tools.types import ToolDefinition


@pytest.mark.asyncio
async def test_tool_arguments_are_validated_before_execution() -> None:
    called = False

    async def handler(params: dict[str, Any], context: Any = None) -> str:
        nonlocal called
        called = True
        return "ok"

    registry = ToolRegistry()
    registry.register(
        ToolDefinition(
            name="validated",
            description="validated",
            input_schema={
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
            handler=handler,
        )
    )

    result = await execute_tool(registry, ToolPolicy(), "validated", {})

    assert result.success is False
    assert "missing required" in str(result.error)
    assert called is False


@pytest.mark.asyncio
async def test_tool_timeout_is_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    async def handler(params: dict[str, Any], context: Any = None) -> str:
        await asyncio.sleep(0.05)
        return "late"

    registry = ToolRegistry()
    registry.register(ToolDefinition(name="slow", description="slow", handler=handler))
    monkeypatch.setattr("muxtrail.tools.execution.DEFAULT_TOOL_TIMEOUT_SECONDS", 0.001)

    result = await execute_tool(registry, ToolPolicy(), "slow", {})

    assert result.success is False
    assert result.error == "Tool 'slow' timed out"


@pytest.mark.asyncio
async def test_unknown_tool_returns_structured_failure() -> None:
    result = await execute_tool(ToolRegistry(), ToolPolicy(), "missing", {})

    assert result.success is False
    assert result.error == "Tool 'missing' not found"


@pytest.mark.asyncio
async def test_structured_ok_false_is_a_tool_failure() -> None:
    payload = {
        "ok": False,
        "status": 404,
        "url": "https://example.com/missing",
        "error": "Fetch failed: HTTP 404",
    }

    async def handler(params: dict[str, Any], context: Any = None) -> dict[str, Any]:
        return payload

    registry = ToolRegistry()
    registry.register(ToolDefinition(name="fetch", description="fetch", handler=handler))

    result = await execute_tool(registry, ToolPolicy(), "fetch", {})

    assert result.success is False
    assert result.output == payload
    assert result.error == "Fetch failed: HTTP 404"


@pytest.mark.asyncio
async def test_error_only_mapping_is_a_tool_failure_and_preserves_output() -> None:
    payload = {"status": 415, "error": "Unsupported content type"}

    async def handler(params: dict[str, Any], context: Any = None) -> dict[str, Any]:
        return payload

    registry = ToolRegistry()
    registry.register(ToolDefinition(name="fetch", description="fetch", handler=handler))

    result = await execute_tool(registry, ToolPolicy(), "fetch", {})

    assert result.success is False
    assert result.output == payload
    assert result.error == "Unsupported content type"


@pytest.mark.asyncio
async def test_empty_error_string_does_not_turn_success_into_failure() -> None:
    payload = {"ok": True, "error": ""}

    async def handler(params: dict[str, Any], context: Any = None) -> dict[str, Any]:
        return payload

    registry = ToolRegistry()
    registry.register(ToolDefinition(name="fetch", description="fetch", handler=handler))

    result = await execute_tool(registry, ToolPolicy(), "fetch", {})

    assert result.success is True
    assert result.output == payload


@pytest.mark.asyncio
async def test_tool_loop_preserves_structured_failure_for_model_and_trace() -> None:
    async def handler(params: dict[str, Any], context: Any = None) -> dict[str, Any]:
        return {"ok": False, "status": 404, "error": "Fetch failed: HTTP 404"}

    registry = ToolRegistry()
    registry.register(ToolDefinition(name="fetch", description="fetch", handler=handler))

    batches = [
        batch
        async for batch in run_tool_loop(
            [{"id": "call-1", "name": "fetch", "params": {}}],
            registry,
            ToolPolicy(),
        )
    ]
    messages, events = batches[0]

    assert '"ok": false' in messages[0]["content"]
    assert '"status": 404' in messages[0]["content"]
    assert events[-1].metadata["success"] is False
    assert '"error": "Fetch failed: HTTP 404"' in str(events[-1].tool_result)
