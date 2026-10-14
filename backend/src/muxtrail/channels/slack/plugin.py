"""Bidirectional Slack Socket Mode channel adapter."""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import time
from typing import TYPE_CHECKING, Any

import httpx
import websockets

from muxtrail.contracts.channel.plugin import (
    ChannelCapabilities,
    ChannelMeta,
    DeliveryResult,
    InboundMessage,
    OutboundMessage,
)
from muxtrail.core.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

log = get_logger("channel.slack")
SLACK_API = "https://slack.com/api"
MAX_SLACK_TEXT = 39_000
DEDUPE_TTL_SECONDS = 600.0


class SlackChannelPlugin:
    """Receive Slack events over Socket Mode and reply through the shared Gateway."""

    def __init__(
        self, on_inbound: Callable[[InboundMessage], Awaitable[None]] | None = None
    ) -> None:
        self._on_inbound = on_inbound
        self._bot_token = ""
        self._app_token = ""
        self._bot_user_id = ""
        self._team_id = ""
        self._task: asyncio.Task[None] | None = None
        self._stop = asyncio.Event()
        self._seen: dict[str, float] = {}

    @property
    def id(self) -> str:
        return "slack"

    @property
    def meta(self) -> ChannelMeta:
        return ChannelMeta(
            id="slack",
            label="Slack",
            selectionLabel="Slack",
            docsPath="docs/slack-setup.md",
            blurb="Slack bot using Socket Mode",
            markdownCapable=True,
        )

    @property
    def capabilities(self) -> ChannelCapabilities:
        return ChannelCapabilities(chatTypes=["dm", "channel", "thread"], threads=True, reply=True)

    def list_account_ids(self, config: dict[str, Any]) -> list[str]:
        cfg = config.get("channels", {}).get("slack", {})
        enabled = cfg.get("enabled") is True or os.environ.get(
            "MUXTRAIL_SLACK_ENABLED", ""
        ).lower() in {"1", "true", "yes", "on"}
        return ["default"] if enabled else []

    async def start(self, account_id: str, config: dict[str, Any]) -> None:
        cfg = config.get("channels", {}).get("slack", {})
        self._bot_token = str(cfg.get("botToken") or os.environ.get("SLACK_BOT_TOKEN", ""))
        self._app_token = str(cfg.get("appToken") or os.environ.get("SLACK_APP_TOKEN", ""))
        if not self._bot_token or not self._app_token:
            raise RuntimeError(
                "Slack is enabled but SLACK_BOT_TOKEN and SLACK_APP_TOKEN are both required"
            )
        identity = await self._api("auth.test", {})
        self._bot_user_id = str(identity.get("user_id") or "")
        self._team_id = str(identity.get("team_id") or "")
        self._stop.clear()
        self._task = asyncio.create_task(self._socket_loop(account_id), name="muxtrail-slack")
        log.info("slack_channel_started", account_id=account_id, team_id=self._team_id)

    async def stop(self, account_id: str) -> None:
        self._stop.set()
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        log.info("slack_channel_stopped", account_id=account_id)

    async def _api(self, method: str, payload: dict[str, Any]) -> dict[str, Any]:
        for attempt in range(3):
            async with httpx.AsyncClient(timeout=20) as client:
                response = await client.post(
                    f"{SLACK_API}/{method}",
                    headers={"Authorization": f"Bearer {self._bot_token}"},
                    json=payload,
                )
            if response.status_code == 429 and attempt < 2:
                await asyncio.sleep(min(float(response.headers.get("retry-after", "1")), 5.0))
                continue
            if response.status_code in {401, 403}:
                raise RuntimeError(
                    f"Slack authentication or permission error (HTTP {response.status_code})"
                )
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, dict):
                raise RuntimeError(f"Slack API {method} returned an invalid response")
            if not data.get("ok"):
                raise RuntimeError(
                    f"Slack API {method} failed: {data.get('error', 'unknown_error')}"
                )
            return data
        raise RuntimeError(f"Slack API {method} remained rate limited")

    async def _api_with_app_token(self, method: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(
                f"{SLACK_API}/{method}", headers={"Authorization": f"Bearer {self._app_token}"}
            )
        if response.status_code in {401, 403}:
            raise RuntimeError("Slack app-level token was rejected")
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict):
            raise RuntimeError(f"Slack API {method} returned an invalid response")
        if not data.get("ok"):
            raise RuntimeError(f"Slack API {method} failed: {data.get('error', 'unknown_error')}")
        return data

    async def _socket_loop(self, account_id: str) -> None:
        delay = 1.0
        while not self._stop.is_set():
            try:
                connection = await self._api_with_app_token("apps.connections.open")
                url = str(connection.get("url") or "")
                if not url:
                    raise RuntimeError("Slack Socket Mode did not return a connection URL")
                async with websockets.connect(url, ping_interval=20, ping_timeout=20) as socket:
                    delay = 1.0
                    async for raw in socket:
                        envelope = json.loads(raw)
                        envelope_id = envelope.get("envelope_id")
                        if envelope_id:
                            await socket.send(json.dumps({"envelope_id": envelope_id}))
                        await self.handle_envelope(account_id, envelope)
                        if self._stop.is_set():
                            break
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                log.warning("slack_socket_reconnect", error=str(exc), retry_seconds=delay)
                await asyncio.sleep(delay)
                delay = min(delay * 2, 30.0)

    async def handle_envelope(self, account_id: str, envelope: dict[str, Any]) -> bool:
        """Normalize one acknowledged Socket Mode envelope; exposed for mocked tests."""
        payload = envelope.get("payload")
        if envelope.get("type") != "events_api" or not isinstance(payload, dict):
            return False
        event = payload.get("event")
        if not isinstance(event, dict) or event.get("type") not in {"message", "app_mention"}:
            return False
        if event.get("subtype") or event.get("bot_id") or event.get("user") == self._bot_user_id:
            return False
        event_id = str(
            payload.get("event_id") or event.get("client_msg_id") or event.get("ts") or ""
        )
        if event_id and self._is_duplicate(event_id):
            return False
        channel = str(event.get("channel") or "")
        sender = str(event.get("user") or "")
        text = str(event.get("text") or "")
        is_dm = event.get("channel_type") == "im"
        if not is_dm:
            mention = f"<@{self._bot_user_id}>"
            if event.get("type") != "app_mention" and mention not in text:
                return False
            text = text.replace(mention, "").strip()
        if not channel or not sender or not text:
            return False
        if event_id:
            self._seen[event_id] = time.monotonic()
        thread_ts = str(event.get("thread_ts") or event.get("ts") or "")
        message = InboundMessage(
            channel="slack",
            accountId=account_id,
            workspaceId=str(payload.get("team_id") or self._team_id or "unknown"),
            senderId=sender,
            conversationId=channel,
            threadId=thread_ts,
            messageId=str(event.get("ts") or ""),
            replyTarget=thread_ts,
            text=text,
            chatType="dm" if is_dm else ("thread" if event.get("thread_ts") else "channel"),
            capabilities={"threads": True, "markdown": True},
            raw={"event_id": event_id, "retry": envelope.get("retry_attempt")},
        )
        if self._on_inbound:
            await self._on_inbound(message)
        return True

    def _is_duplicate(self, event_id: str) -> bool:
        now = time.monotonic()
        self._seen = {
            key: seen for key, seen in self._seen.items() if now - seen < DEDUPE_TTL_SECONDS
        }
        return event_id in self._seen

    async def send(
        self, account_id: str, conversation_id: str, message: OutboundMessage
    ) -> DeliveryResult:
        if not self._bot_token:
            raise RuntimeError("Slack channel is not started")
        text = message.text or ""
        parts = [
            text[index : index + MAX_SLACK_TEXT] for index in range(0, len(text), MAX_SLACK_TEXT)
        ]
        if not parts:
            parts = [""]
        message_ids: list[str] = []
        for part in parts:
            payload: dict[str, Any] = {"channel": conversation_id, "text": part}
            thread_id = message.thread_id or message.reply_to_id
            if thread_id:
                payload["thread_ts"] = thread_id
            data = await self._api("chat.postMessage", payload)
            if data.get("ts"):
                message_ids.append(str(data["ts"]))
        return DeliveryResult(ok=True, channel="slack", messageIds=message_ids)
