"""Restricted, connection-scoped public demo WebSocket."""

from __future__ import annotations

import asyncio
import os
import secrets
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from pydantic import ValidationError
from starlette.websockets import WebSocket, WebSocketDisconnect

from muxtrail.contracts.protocol.frames import RequestFrame, ResponseFrame
from muxtrail.core.errors import ProtocolError
from muxtrail.core.logging import get_logger
from muxtrail.gateway.constants import (
    DEFAULT_MAX_BUFFERED_BYTES,
    DEFAULT_MAX_PAYLOAD,
    DEFAULT_TICK_INTERVAL_MS,
)
from muxtrail.gateway.websocket.connection import GatewayWsClient
from muxtrail.gateway.websocket.frames import make_event, make_response, parse_frame
from muxtrail.gateway.websocket.handshake import perform_handshake
from muxtrail.gateway.websocket.heartbeat import TickEmitter

log = get_logger("gateway.demo")

if TYPE_CHECKING:
    from muxtrail.gateway.state import GatewayRuntimeState


def _env_int(name: str, default: int, minimum: int, maximum: int) -> int:
    raw = os.environ.get(name, "")
    try:
        value = int(raw) if raw else default
    except ValueError:
        value = default
    return max(minimum, min(value, maximum))


@dataclass(frozen=True)
class DemoLimits:
    max_message_chars: int = 1000
    max_turns_per_session: int = 5
    max_messages_per_hour: int = 10
    max_messages_per_day: int = 100
    max_concurrent_runs: int = 2
    run_timeout_seconds: int = 60

    @classmethod
    def from_env(cls) -> DemoLimits:
        return cls(
            max_message_chars=_env_int("MUXTRAIL_DEMO_MAX_MESSAGE_CHARS", 1000, 100, 4000),
            max_turns_per_session=_env_int("MUXTRAIL_DEMO_MAX_TURNS", 5, 1, 20),
            max_messages_per_hour=_env_int("MUXTRAIL_DEMO_MESSAGES_PER_HOUR", 10, 1, 100),
            max_messages_per_day=_env_int("MUXTRAIL_DEMO_DAILY_MESSAGE_LIMIT", 100, 1, 10000),
            max_concurrent_runs=_env_int("MUXTRAIL_DEMO_MAX_CONCURRENT", 2, 1, 20),
            run_timeout_seconds=_env_int("MUXTRAIL_DEMO_TIMEOUT_SECONDS", 60, 10, 300),
        )


class DemoGate:
    """In-memory abuse and cost guard shared by all demo connections."""

    def __init__(self, limits: DemoLimits | None = None) -> None:
        self.limits = limits or DemoLimits.from_env()
        self._hourly: dict[str, deque[float]] = defaultdict(deque)
        self._daily_bucket = time.strftime("%Y-%m-%d", time.gmtime())
        self._daily_count = 0
        self._active_runs = 0
        self._lock = asyncio.Lock()

    async def reserve(self, client_id: str) -> tuple[bool, str]:
        now = time.time()
        async with self._lock:
            bucket = time.strftime("%Y-%m-%d", time.gmtime(now))
            if bucket != self._daily_bucket:
                self._daily_bucket = bucket
                self._daily_count = 0

            attempts = self._hourly[client_id]
            while attempts and attempts[0] <= now - 3600:
                attempts.popleft()
            if len(attempts) >= self.limits.max_messages_per_hour:
                return False, "Hourly demo limit reached. Please try again later."
            if self._daily_count >= self.limits.max_messages_per_day:
                return False, "The demo has reached today's usage budget."
            if self._active_runs >= self.limits.max_concurrent_runs:
                return False, "The demo is busy. Please try again in a moment."

            attempts.append(now)
            self._daily_count += 1
            self._active_runs += 1
            return True, ""

    async def release(self) -> None:
        async with self._lock:
            self._active_runs = max(0, self._active_runs - 1)


def demo_enabled() -> bool:
    return os.environ.get("MUXTRAIL_DEMO_ENABLED", "false").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _client_identity(ws: WebSocket) -> str:
    # The production origin is reachable only through cloudflared on loopback,
    # so Cloudflare's connecting-IP header is the useful rate-limit key.
    forwarded = ws.headers.get("cf-connecting-ip", "").strip()
    if forwarded:
        return forwarded
    return ws.client.host if ws.client else "unknown"


def _safe_hello(
    params: dict[str, Any], client: GatewayWsClient, state: GatewayRuntimeState
) -> dict[str, Any]:
    hello = perform_handshake(
        params,
        client,
        state,
        supported_methods=["connect", "demo.send", "demo.reset"],
        supported_events=["tick", "agent.event", "runtime.event"],
    )
    hello["snapshot"] = {
        "presence": [],
        "health": {"demo": "ready"},
        "stateVersion": {"presence": 0, "health": 0},
        "uptimeMs": state.uptime_ms,
        "sessionDefaults": {
            "defaultAgentId": "demo",
            "mainKey": "demo",
            "mainSessionKey": "demo",
        },
        "authMode": "restricted-demo",
    }
    hello["policy"] = {
        "maxPayload": DEFAULT_MAX_PAYLOAD,
        "maxBufferedBytes": DEFAULT_MAX_BUFFERED_BYTES,
        "tickIntervalMs": DEFAULT_TICK_INTERVAL_MS,
    }
    return hello


async def handle_demo_websocket(
    ws: WebSocket,
    state: GatewayRuntimeState,
    gate: DemoGate,
) -> None:
    """Serve a public demo without joining the privileged broadcast pool."""
    await ws.accept()
    client = GatewayWsClient(ws=ws)
    tick = TickEmitter()
    session_key = f"demo:{secrets.token_urlsafe(18)}"
    turns = 0
    runtime: Any = getattr(state, "_gateway_runtime_ref", None)

    async def cleanup_session() -> None:
        if runtime is None:
            return
        entry = runtime.session_store.get(session_key)
        if entry is not None:
            runtime.transcript_manager.clear(entry.session_id)
            runtime.session_store.delete(session_key)
            runtime.session_store.save()

    try:
        raw = await ws.receive_json()
        frame = parse_frame(raw)
        if not isinstance(frame, RequestFrame) or frame.method != "connect":
            frame_id = frame.id if isinstance(frame, (RequestFrame, ResponseFrame)) else "?"
            await client.send_json(
                make_response(
                    frame_id,
                    False,
                    error={"code": "INVALID_REQUEST", "message": "First message must be connect"},
                )
            )
            return

        hello = _safe_hello(frame.params or {}, client, state)
        hello["demo"] = {
            "sessionKey": session_key,
            "maxTurns": gate.limits.max_turns_per_session,
            "maxMessageChars": gate.limits.max_message_chars,
        }
        await client.send_json(make_response(frame.id, True, payload=hello))
        if runtime is not None:
            runtime.attach_session_event_client(session_key, client)
        tick.start(client.send_json)

        while True:
            raw = await ws.receive_json()
            frame = parse_frame(raw)
            if not isinstance(frame, RequestFrame):
                continue

            if frame.method == "demo.reset":
                await cleanup_session()
                turns = 0
                await client.send_json(
                    make_response(frame.id, True, payload={"ok": True, "sessionKey": session_key})
                )
                continue

            if frame.method != "demo.send":
                await client.send_json(
                    make_response(
                        frame.id,
                        False,
                        error={
                            "code": "METHOD_NOT_FOUND",
                            "message": "Method is not available in demo mode",
                        },
                    )
                )
                continue

            message = str((frame.params or {}).get("message", "")).strip()
            if not message:
                await client.send_json(
                    make_response(
                        frame.id,
                        False,
                        error={"code": "INVALID_REQUEST", "message": "Message is required"},
                    )
                )
                continue
            if len(message) > gate.limits.max_message_chars:
                await client.send_json(
                    make_response(
                        frame.id,
                        False,
                        error={
                            "code": "MESSAGE_TOO_LONG",
                            "message": (
                                "Demo messages are limited to "
                                f"{gate.limits.max_message_chars} characters"
                            ),
                        },
                    )
                )
                continue
            if turns >= gate.limits.max_turns_per_session:
                await client.send_json(
                    make_response(
                        frame.id,
                        False,
                        error={
                            "code": "SESSION_LIMIT",
                            "message": "Start a new demo conversation to continue",
                        },
                    )
                )
                continue
            if runtime is None:
                await client.send_json(
                    make_response(
                        frame.id,
                        False,
                        error={"code": "UNAVAILABLE", "message": "Demo runtime is unavailable"},
                    )
                )
                continue

            reserved, reason = await gate.reserve(_client_identity(ws))
            if not reserved:
                await client.send_json(
                    make_response(
                        frame.id,
                        False,
                        error={"code": "RATE_LIMITED", "message": reason},
                    )
                )
                continue

            turns += 1
            run_id = secrets.token_urlsafe(12)
            await runtime._emit_runtime_event(
                "runtime.channel.inbound",
                layer="channel",
                session_key=session_key,
                run_id=run_id,
                status="done",
                title="Inbound message",
                detail=message,
                data={"channel": "public-demo", "message": message},
            )

            async def on_text_delta(text: str, event_run_id: str = run_id) -> None:
                await client.send_json(
                    make_event(
                        "agent.event",
                        {
                            "type": "text_delta",
                            "sessionKey": session_key,
                            "runId": event_run_id,
                            "text": text,
                        },
                    )
                )

            try:
                async with asyncio.timeout(gate.limits.run_timeout_seconds):
                    result = await runtime.run_agent_for_session(
                        session_key=session_key,
                        user_message=message,
                        channel="public-demo",
                        sender_id="anonymous-demo",
                        conversation_id=session_key,
                        trace_id=run_id,
                        on_text_delta=on_text_delta,
                        tool_profile="demo",
                    )
                response_text = result.preferred_response or "".join(result.texts)
                if not response_text:
                    response_text = result.error or "The model returned an empty response."
                await runtime._emit_runtime_event(
                    "runtime.channel.reply_sent",
                    layer="reply",
                    session_key=session_key,
                    run_id=run_id,
                    status="done",
                    title="Reply delivered to Public Demo",
                    detail=response_text[:300],
                    data={
                        "channel": "public-demo",
                        "conversationId": session_key,
                        "traceId": run_id,
                        "delivery": {"ok": True, "transport": "gateway-websocket"},
                        "text": response_text,
                    },
                )
                await client.send_json(
                    make_response(
                        frame.id,
                        result.error is None,
                        payload={
                            "ok": result.error is None,
                            "turnsRemaining": gate.limits.max_turns_per_session - turns,
                        },
                        error=(
                            {"code": "RUN_FAILED", "message": result.error}
                            if result.error
                            else None
                        ),
                    )
                )
            except TimeoutError:
                await runtime._emit_runtime_event(
                    "runtime.run.completed",
                    layer="runtime",
                    session_key=session_key,
                    run_id=run_id,
                    status="failed",
                    title="Run timed out",
                    detail="The demo request timed out.",
                    data={"responseText": "The demo request timed out."},
                )
                await client.send_json(
                    make_response(
                        frame.id,
                        False,
                        error={"code": "TIMEOUT", "message": "The demo request timed out"},
                    )
                )
            finally:
                await gate.release()
    except (WebSocketDisconnect, ProtocolError, ValidationError):
        pass
    except Exception as exc:
        log.warning("demo_ws_error", error=str(exc))
    finally:
        tick.stop()
        if runtime is not None:
            runtime.detach_session_event_client(session_key, client)
        await cleanup_session()
