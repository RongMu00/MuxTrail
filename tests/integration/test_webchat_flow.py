# 文件说明：本文件属于 集成测试层。
# 主要职责：覆盖 webchat flow 相关行为。
# 阅读提示：验证 Gateway 与通道端到端链路。
# 运行影响：仅用于源码阅读，不改变运行逻辑。

"""Integration test: WebChat uses Gateway EventFrame push, not channel.send()."""

from types import SimpleNamespace
from typing import Any

import pytest
from muxtrail.channels.webchat.plugin import WebChatPlugin
from muxtrail.contracts.channel.plugin import OutboundMessage
from muxtrail.gateway.boot import AgentRunResult
from muxtrail.gateway.methods.sessions import handle_sessions_send


class TestWebChatDesign:
    """Verify WebChat is a Gateway WS push channel, not an independent adapter."""

    @pytest.mark.asyncio
    async def test_webchat_send_is_noop(self) -> None:
        """WebChat.send() is intentionally empty — delivery via Gateway EventFrame."""
        plugin = WebChatPlugin()
        # send() should not raise, and should not do anything
        msg = OutboundMessage(text="test")
        await plugin.send("default", "conv-1", msg)
        # If we get here without error, the no-op behavior is correct

    @pytest.mark.asyncio
    async def test_webchat_start_stop_are_noop(self) -> None:
        """WebChat start/stop are no-ops — no persistent connection to manage."""
        plugin = WebChatPlugin()
        await plugin.start("default", {})
        await plugin.stop("default")

    def test_webchat_meta(self) -> None:
        plugin = WebChatPlugin()
        assert plugin.id == "webchat"
        assert plugin.capabilities.chat_types == ["dm"]

    def test_webchat_accounts(self) -> None:
        plugin = WebChatPlugin()
        assert plugin.list_account_ids({}) == ["default"]


@pytest.mark.asyncio
async def test_webchat_send_emits_reply_delivery_event() -> None:
    emitted: list[dict[str, Any]] = []
    frames: list[dict[str, Any]] = []

    class Runtime:
        async def run_agent_for_session(self, **kwargs: Any) -> AgentRunResult:
            result = AgentRunResult()
            result.run_id = "trace-webchat"
            result.texts = ["MuxTrail reply"]
            return result

        async def _emit_runtime_event(self, event_type: str, **kwargs: Any) -> None:
            emitted.append({"type": event_type, **kwargs})

    class Client:
        async def send_json(self, frame: dict[str, Any]) -> None:
            frames.append(frame)

    state = SimpleNamespace(_gateway_runtime_ref=Runtime())
    response = await handle_sessions_send(
        {"sessionKey": "web:test", "message": "hello"}, Client(), state
    )

    assert response["ok"] is True
    reply = next(item for item in emitted if item["type"] == "runtime.channel.reply_sent")
    assert reply["layer"] == "reply"
    assert reply["status"] == "done"
    assert reply["run_id"] == "trace-webchat"
    assert reply["data"]["delivery"] == {
        "ok": True,
        "transport": "gateway-websocket",
    }
    assert frames[-1]["payload"]["type"] == "complete"
