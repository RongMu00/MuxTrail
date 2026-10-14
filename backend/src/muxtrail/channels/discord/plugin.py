"""Bidirectional Discord Gateway and REST channel adapter."""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import random
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

log = get_logger("channel.discord")
DISCORD_API = "https://discord.com/api/v10"
GATEWAY_VERSION = 10
INTENTS = 1 | 512 | 4096  # guilds, guild messages, direct messages; no privileged intents
MAX_DISCORD_TEXT = 2_000
DEDUPE_TTL_SECONDS = 600.0


class DiscordChannelPlugin:
    """Receive Discord Gateway events and route replies through the shared Gateway."""

    def __init__(
        self, on_inbound: Callable[[InboundMessage], Awaitable[None]] | None = None
    ) -> None:
        self._on_inbound = on_inbound
        self._bot_token = ""
        self._bot_user_id = ""
        self._task: asyncio.Task[None] | None = None
        self._heartbeat_task: asyncio.Task[None] | None = None
        self._stop = asyncio.Event()
        self._seen: dict[str, float] = {}
        self._sequence: int | None = None
        self._session_id = ""
        self._resume_url = ""

    @property
    def id(self) -> str:
        return "discord"

    @property
    def meta(self) -> ChannelMeta:
        return ChannelMeta(
            id="discord",
            label="Discord",
            selectionLabel="Discord",
            docsPath="docs/discord-setup.md",
            blurb="Discord bot using Gateway events and REST replies",
            markdownCapable=True,
        )

    @property
    def capabilities(self) -> ChannelCapabilities:
        return ChannelCapabilities(chatTypes=["dm", "channel", "thread"], threads=True, reply=True)

    def list_account_ids(self, config: dict[str, Any]) -> list[str]:
        cfg = config.get("channels", {}).get("discord", {})
        enabled = cfg.get("enabled") is True or os.environ.get(
            "MUXTRAIL_DISCORD_ENABLED", ""
        ).lower() in {"1", "true", "yes", "on"}
        return ["default"] if enabled else []

    async def start(self, account_id: str, config: dict[str, Any]) -> None:
        cfg = config.get("channels", {}).get("discord", {})
        self._bot_token = str(cfg.get("botToken") or os.environ.get("DISCORD_BOT_TOKEN", ""))
        if not self._bot_token:
            raise RuntimeError("Discord is enabled but DISCORD_BOT_TOKEN is required")
        identity = await self._rest("GET", "/users/@me")
        self._bot_user_id = str(identity.get("id") or "")
        self._stop.clear()
        self._task = asyncio.create_task(self._gateway_loop(account_id), name="muxtrail-discord")
        log.info("discord_channel_started", account_id=account_id, bot_user_id=self._bot_user_id)

    async def stop(self, account_id: str) -> None:
        self._stop.set()
        for task in (self._heartbeat_task, self._task):
            if task:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task
        self._heartbeat_task = None
        self._task = None
        log.info("discord_channel_stopped", account_id=account_id)

    async def _rest(
        self, method: str, path: str, payload: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        for attempt in range(3):
            async with httpx.AsyncClient(timeout=20) as client:
                response = await client.request(
                    method,
                    f"{DISCORD_API}{path}",
                    headers={"Authorization": f"Bot {self._bot_token}"},
                    json=payload,
                )
            if response.status_code == 429 and attempt < 2:
                try:
                    retry_after = float(response.json().get("retry_after", 1))
                except (TypeError, ValueError):
                    retry_after = 1.0
                await asyncio.sleep(min(retry_after, 5.0))
                continue
            if response.status_code in {401, 403}:
                raise RuntimeError(
                    f"Discord authentication or permission error (HTTP {response.status_code})"
                )
            response.raise_for_status()
            return response.json() if response.content else {}
        raise RuntimeError("Discord API remained rate limited")

    async def _gateway_loop(self, account_id: str) -> None:
        delay = 1.0
        while not self._stop.is_set():
            try:
                gateway = await self._rest("GET", "/gateway/bot")
                base_url = self._resume_url or str(gateway.get("url") or "")
                if not base_url:
                    raise RuntimeError("Discord did not return a Gateway URL")
                url = f"{base_url}?v={GATEWAY_VERSION}&encoding=json"
                async with websockets.connect(url, ping_interval=None) as socket:
                    delay = 1.0
                    async for raw in socket:
                        frame = json.loads(raw)
                        sequence = frame.get("s")
                        if isinstance(sequence, int):
                            self._sequence = sequence
                        op = frame.get("op")
                        if op == 10:
                            interval = float(frame["d"]["heartbeat_interval"]) / 1000
                            self._heartbeat_task = asyncio.create_task(
                                self._heartbeat(socket, interval)
                            )
                            await asyncio.sleep(random.uniform(0, min(interval, 1.0)))
                            await self._identify_or_resume(socket)
                        elif op == 0:
                            await self.handle_dispatch(
                                account_id, str(frame.get("t") or ""), frame.get("d")
                            )
                        elif op == 1:
                            await socket.send(json.dumps({"op": 1, "d": self._sequence}))
                        elif op in {7, 9}:
                            if op == 9:
                                self._session_id = ""
                                self._resume_url = ""
                            break
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                log.warning("discord_gateway_reconnect", error=str(exc), retry_seconds=delay)
                await asyncio.sleep(delay)
                delay = min(delay * 2, 30.0)
            finally:
                if self._heartbeat_task:
                    self._heartbeat_task.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await self._heartbeat_task
                    self._heartbeat_task = None

    async def _heartbeat(self, socket: Any, interval: float) -> None:
        while not self._stop.is_set():
            await asyncio.sleep(interval)
            await socket.send(json.dumps({"op": 1, "d": self._sequence}))

    async def _identify_or_resume(self, socket: Any) -> None:
        if self._session_id and self._sequence is not None:
            payload = {
                "op": 6,
                "d": {
                    "token": self._bot_token,
                    "session_id": self._session_id,
                    "seq": self._sequence,
                },
            }
        else:
            payload = {
                "op": 2,
                "d": {
                    "token": self._bot_token,
                    "intents": INTENTS,
                    "properties": {
                        "os": "linux",
                        "browser": "muxtrail",
                        "device": "muxtrail",
                    },
                },
            }
        await socket.send(json.dumps(payload))

    async def handle_dispatch(self, account_id: str, event_type: str, data: Any) -> bool:
        """Normalize one Gateway dispatch; exposed for mocked round-trip tests."""
        if not isinstance(data, dict):
            return False
        if event_type == "READY":
            self._session_id = str(data.get("session_id") or "")
            self._resume_url = str(data.get("resume_gateway_url") or "")
            user = data.get("user") or {}
            self._bot_user_id = str(user.get("id") or self._bot_user_id)
            return True
        if event_type != "MESSAGE_CREATE":
            return False
        author = data.get("author") or {}
        sender = str(author.get("id") or "")
        if author.get("bot") or sender == self._bot_user_id:
            return False
        message_id = str(data.get("id") or "")
        if message_id and self._is_duplicate(message_id):
            return False
        guild_id = str(data.get("guild_id") or "")
        is_dm = not guild_id
        mentions = data.get("mentions") if isinstance(data.get("mentions"), list) else []
        mentioned = any(
            str(item.get("id") or "") == self._bot_user_id
            for item in mentions
            if isinstance(item, dict)
        )
        if not is_dm and not mentioned:
            return False
        text = str(data.get("content") or "")
        text = (
            text.replace(f"<@{self._bot_user_id}>", "")
            .replace(f"<@!{self._bot_user_id}>", "")
            .strip()
        )
        if not text:
            return False
        if message_id:
            self._seen[message_id] = time.monotonic()
        channel_id = str(data.get("channel_id") or "")
        reference = data.get("message_reference")
        reference = reference if isinstance(reference, dict) else {}
        thread_id = channel_id if data.get("thread") else str(reference.get("message_id") or "root")
        message = InboundMessage(
            channel="discord",
            accountId=account_id,
            workspaceId=guild_id or "dm",
            senderId=sender,
            conversationId=channel_id,
            threadId=thread_id,
            messageId=message_id,
            replyTarget=message_id,
            text=text,
            attachments=data.get("attachments") or None,
            chatType="dm" if is_dm else ("thread" if data.get("thread") else "channel"),
            capabilities={"messageReferences": True, "markdown": True},
            raw={"guild_id": guild_id, "message_id": message_id},
        )
        if self._on_inbound:
            await self._on_inbound(message)
        return True

    def _is_duplicate(self, message_id: str) -> bool:
        now = time.monotonic()
        self._seen = {
            key: seen for key, seen in self._seen.items() if now - seen < DEDUPE_TTL_SECONDS
        }
        return message_id in self._seen

    async def send(
        self, account_id: str, conversation_id: str, message: OutboundMessage
    ) -> DeliveryResult:
        if not self._bot_token:
            raise RuntimeError("Discord channel is not started")
        text = message.text or ""
        parts = [
            text[index : index + MAX_DISCORD_TEXT]
            for index in range(0, len(text), MAX_DISCORD_TEXT)
        ]
        if not parts:
            parts = [""]
        message_ids: list[str] = []
        for index, part in enumerate(parts):
            payload: dict[str, Any] = {"content": part, "allowed_mentions": {"parse": []}}
            if index == 0 and message.reply_to_id:
                payload["message_reference"] = {
                    "message_id": message.reply_to_id,
                    "channel_id": conversation_id,
                    "fail_if_not_exists": False,
                }
            result = await self._rest("POST", f"/channels/{conversation_id}/messages", payload)
            if result.get("id"):
                message_ids.append(str(result["id"]))
        return DeliveryResult(ok=True, channel="discord", messageIds=message_ids)
