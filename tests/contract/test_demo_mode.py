"""Security and cost boundaries for the public demo."""

import pytest
from fastapi.testclient import TestClient
from muxtrail.gateway.app import create_app
from muxtrail.gateway.demo import DemoGate, DemoLimits
from muxtrail.tools.policy import ToolPolicy


def test_demo_tool_policy_only_allows_public_web_tools() -> None:
    policy = ToolPolicy(profile="demo")

    assert policy.is_allowed("web_search")
    assert policy.is_allowed("web_fetch")
    assert not policy.is_allowed("read_file")
    assert not policy.is_allowed("bash")
    assert not policy.is_allowed("sessions_send")
    assert not policy.is_allowed("feishu_docs_create")


@pytest.mark.asyncio
async def test_demo_gate_enforces_hourly_budget() -> None:
    gate = DemoGate(
        DemoLimits(
            max_messages_per_hour=1,
            max_messages_per_day=10,
            max_concurrent_runs=2,
        )
    )

    allowed, _ = await gate.reserve("visitor")
    assert allowed
    await gate.release()

    allowed, reason = await gate.reserve("visitor")
    assert not allowed
    assert "Hourly" in reason


@pytest.mark.asyncio
async def test_demo_gate_rejects_excess_concurrency_without_charging_quota() -> None:
    gate = DemoGate(
        DemoLimits(
            max_messages_per_hour=3,
            max_messages_per_day=3,
            max_concurrent_runs=1,
        )
    )

    allowed, _ = await gate.reserve("first")
    assert allowed
    allowed, reason = await gate.reserve("second")
    assert not allowed
    assert "busy" in reason
    await gate.release()

    allowed, _ = await gate.reserve("second")
    assert allowed
    await gate.release()


def test_demo_websocket_does_not_expose_owner_methods(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MUXTRAIL_DEMO_ENABLED", "true")
    app = create_app(boot=False)

    with (
        TestClient(app) as client,
        client.websocket_connect(
            "/demo/ws", headers={"origin": "http://localhost:3001"}
        ) as websocket,
    ):
        websocket.send_json(
            {
                "type": "req",
                "id": "connect-1",
                "method": "connect",
                "params": {
                    "minProtocol": 1,
                    "maxProtocol": 3,
                    "client": {
                        "id": "test-demo",
                        "version": "0.1.0",
                        "platform": "test",
                        "mode": "demo",
                    },
                },
            }
        )
        hello = websocket.receive_json()
        assert hello["ok"] is True
        assert hello["payload"]["features"]["methods"] == [
            "connect",
            "demo.send",
            "demo.reset",
        ]
        assert hello["payload"]["snapshot"]["presence"] == []

        websocket.send_json(
            {"type": "req", "id": "owner-method", "method": "sessions.list", "params": {}}
        )
        rejected = websocket.receive_json()
        assert rejected["ok"] is False
        assert rejected["error"]["code"] == "METHOD_NOT_FOUND"
