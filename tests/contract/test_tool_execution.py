"""Structured tool execution safety tests."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
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
