# 文件说明：本文件属于 契约测试层。
# 主要职责：覆盖 feishu tool policy 相关行为。
# 阅读提示：验证单模块行为和协议兼容性。
# 运行影响：仅用于源码阅读，不改变运行逻辑。

"""Tool-policy regression tests for remote channel runs."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from muxtrail.agents.providers.registry import ProviderRegistry
from muxtrail.agents.runtime.embedded.runner import EmbeddedRuntime
from muxtrail.contracts.agent.runtime import AgentEventType, AgentRunRequest
from muxtrail.tools.registry import ToolRegistry
from muxtrail.tools.types import ToolDefinition


class ToolCallingProvider:
    id = "test"

    def __init__(self) -> None:
        self.calls = 0

    def list_models(self) -> list[dict[str, Any]]:
        return [{"id": "test-model"}]

    async def create_stream(
        self,
        model: str,
        messages: list[dict[str, Any]],
        system: str = "",
        **kwargs: Any,
    ):
        self.calls += 1
        if self.calls == 1:
            yield {"type": "tool_call", "id": "call-1", "name": "bash", "params": {"command": "id"}}
            return
        yield {"type": "text_delta", "text": "done"}


async def _forbidden_bash(params: dict[str, Any], context: Any = None) -> dict[str, Any]:
    raise AssertionError("bash handler should not be called")


@pytest.mark.asyncio
async def test_messaging_profile_denies_bash_tool() -> None:
    provider_registry = ProviderRegistry()
    provider_registry.register(ToolCallingProvider())
    tool_registry = ToolRegistry()
    tool_registry.register(
        ToolDefinition(
            name="bash",
            description="Run shell",
            input_schema={"type": "object"},
            handler=_forbidden_bash,
        )
    )
    runtime = EmbeddedRuntime(provider_registry=provider_registry, tool_registry=tool_registry)
    request = AgentRunRequest(
        run_id="run-1",
        session_key="dm:feishu:ou_user",
        provider_id="test",
        model_id="test-model",
        system_prompt="",
        user_message="run id",
        metadata={"channel": "feishu", "toolProfile": "messaging"},
    )

    async def collect() -> list[str]:
        results = []
        async for event in runtime.run(request, asyncio.Event()):
            if event.type == AgentEventType.TOOL_CALL_RESULT:
                results.append(str(event.tool_result))
        return results

    results = await collect()
    assert "denied by policy" in results[0]


@pytest.mark.asyncio
async def test_missing_provider_returns_configuration_error_not_mock_echo() -> None:
    runtime = EmbeddedRuntime(provider_registry=ProviderRegistry(), tool_registry=ToolRegistry())
    request = AgentRunRequest(
        run_id="run-missing",
        session_key="web:missing",
        provider_id="openai",
        model_id="gpt-4o",
        system_prompt="",
        user_message="hello",
    )

    events = [event async for event in runtime.run(request, asyncio.Event())]

    assert [event.type for event in events] == [AgentEventType.ERROR]
    assert "not configured" in str(events[0].error)
    assert all("[mock]" not in str(event.text) for event in events)
