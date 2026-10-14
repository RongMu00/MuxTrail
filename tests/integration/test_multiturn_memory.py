"""End-to-end active-session memory and isolation test with a deterministic provider."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
from muxtrail.contracts.config.types_muxtrail import MuxTrailConfig
from muxtrail.gateway.boot import GatewayRuntime

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


class MemoryProvider:
    id = "memory-test"

    def list_models(self) -> list[dict[str, Any]]:
        return [{"id": "memory-model"}]

    async def create_stream(
        self,
        model: str,
        messages: list[dict[str, Any]],
        system: str = "",
        **kwargs: Any,
    ) -> AsyncIterator[dict[str, Any]]:
        transcript = "\n".join(str(item.get("content") or "") for item in messages)
        if "What was the test code" in transcript and "Blue Lobster 729" in transcript:
            yield {"type": "text_delta", "text": "Blue Lobster 729."}
        elif "What was the test code" in transcript:
            yield {"type": "text_delta", "text": "I do not have a code in this session."}
        else:
            yield {"type": "text_delta", "text": "I will remember that test code."}


@pytest.mark.asyncio
async def test_same_session_recall_cross_session_isolation_and_reset(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MUXTRAIL_STATE_DIR", str(tmp_path))
    runtime = GatewayRuntime(MuxTrailConfig())
    runtime.boot()
    runtime.provider_registry.register(MemoryProvider())
    runtime.default_provider = "memory-test"
    runtime.default_model = "memory-model"

    first = await runtime.run_agent_for_session(
        "session-a", "Remember this test code: Blue Lobster 729.", channel="webchat"
    )
    recall = await runtime.run_agent_for_session(
        "session-a", "What was the test code I gave you?", channel="webchat"
    )
    isolated = await runtime.run_agent_for_session(
        "session-b", "What was the test code I gave you?", channel="webchat"
    )
    runtime.session_store.reset("session-a")
    after_reset = await runtime.run_agent_for_session(
        "session-a", "What was the test code I gave you?", channel="webchat"
    )

    assert "remember" in "".join(first.texts).lower()
    assert "".join(recall.texts) == "Blue Lobster 729."
    assert "do not have" in "".join(isolated.texts)
    assert "do not have" in "".join(after_reset.texts)
