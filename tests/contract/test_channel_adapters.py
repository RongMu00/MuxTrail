"""Mocked bidirectional channel and session-isolation tests."""

from __future__ import annotations

from typing import Any

import pytest
from muxtrail.channels.discord.plugin import DiscordChannelPlugin
from muxtrail.channels.routing import resolve_session_key
from muxtrail.channels.slack.plugin import SlackChannelPlugin
from muxtrail.contracts.channel.plugin import InboundMessage, OutboundMessage
from muxtrail.contracts.config.types_muxtrail import MuxTrailConfig
from muxtrail.gateway.boot import GatewayRuntime


@pytest.mark.asyncio
async def test_slack_mocked_inbound_and_thread_reply(monkeypatch: pytest.MonkeyPatch) -> None:
    received: list[InboundMessage] = []

    async def on_inbound(message: InboundMessage) -> None:
        received.append(message)

    plugin = SlackChannelPlugin(on_inbound)
    plugin._bot_user_id = "B1"
    plugin._bot_token = "xoxb-test"
    handled = await plugin.handle_envelope(
        "default",
        {
            "type": "events_api",
            "payload": {
                "team_id": "T1",
                "event_id": "Ev1",
                "event": {
                    "type": "app_mention",
                    "user": "U1",
                    "channel": "C1",
                    "ts": "10.1",
                    "text": "<@B1> hello",
                },
            },
        },
    )
    calls: list[dict[str, Any]] = []

    async def fake_api(method: str, payload: dict[str, Any]) -> dict[str, Any]:
        calls.append(payload)
        return {"ok": True, "ts": "11.1"}

    monkeypatch.setattr(plugin, "_api", fake_api)
    delivery = await plugin.send("default", "C1", OutboundMessage(text="world", replyToId="10.1"))

    assert handled is True
    assert received[0].text == "hello"
    assert received[0].workspace_id == "T1"
    assert calls[0]["thread_ts"] == "10.1"
    assert delivery.ok is True


@pytest.mark.asyncio
async def test_discord_mocked_inbound_and_reply(monkeypatch: pytest.MonkeyPatch) -> None:
    received: list[InboundMessage] = []

    async def on_inbound(message: InboundMessage) -> None:
        received.append(message)

    plugin = DiscordChannelPlugin(on_inbound)
    plugin._bot_user_id = "B1"
    plugin._bot_token = "discord-test"
    handled = await plugin.handle_dispatch(
        "default",
        "MESSAGE_CREATE",
        {
            "id": "M1",
            "guild_id": "G1",
            "channel_id": "C1",
            "author": {"id": "U1", "bot": False},
            "mentions": [{"id": "B1"}],
            "content": "<@B1> hello",
        },
    )
    calls: list[dict[str, Any]] = []

    async def fake_rest(
        method: str, path: str, payload: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        calls.append(payload or {})
        return {"id": "M2"}

    monkeypatch.setattr(plugin, "_rest", fake_rest)
    delivery = await plugin.send("default", "C1", OutboundMessage(text="world", replyToId="M1"))

    assert handled is True
    assert received[0].text == "hello"
    assert received[0].workspace_id == "G1"
    assert calls[0]["message_reference"]["message_id"] == "M1"
    assert delivery.ok is True


def test_session_keys_isolate_channel_workspace_thread_and_user() -> None:
    base = {
        "accountId": "default",
        "conversationId": "C1",
        "text": "hello",
        "chatType": "thread",
    }
    first = InboundMessage(channel="slack", workspaceId="T1", senderId="U1", threadId="TH1", **base)
    second = InboundMessage(
        channel="slack", workspaceId="T2", senderId="U1", threadId="TH1", **base
    )
    third = InboundMessage(
        channel="discord", workspaceId="T1", senderId="U1", threadId="TH1", **base
    )
    fourth = InboundMessage(
        channel="slack", workspaceId="T1", senderId="U2", threadId="TH1", **base
    )

    keys = {resolve_session_key(item) for item in (first, second, third, fourth)}
    assert len(keys) == 4


def test_all_channels_are_registered_on_the_shared_gateway(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MUXTRAIL_STATE_DIR", str(tmp_path))
    runtime = GatewayRuntime(MuxTrailConfig())
    runtime.boot()

    assert set(runtime.channel_registry.list_ids()) == {"webchat", "slack", "discord", "feishu"}
    for channel_id in ("slack", "discord", "feishu"):
        channel = runtime.channel_registry.get(channel_id)
        assert channel is not None
        callback = channel._on_inbound
        assert callback.__self__ is runtime
