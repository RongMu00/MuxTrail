"""Contract tests for Tavily structured search."""

from __future__ import annotations

import json
from typing import Any

import pytest
from muxtrail.tools.builtin.web_search import TAVILY_SEARCH_URL, create_web_search_tool


@pytest.mark.asyncio
async def test_tavily_is_primary_and_accepts_subdomains(
    httpx_mock: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TAVILY_API_KEY", "tvly-test")
    monkeypatch.delenv("BOCHA_API_KEY", raising=False)
    httpx_mock.add_response(
        method="POST",
        url=TAVILY_SEARCH_URL,
        json={
            "request_id": "req-1",
            "results": [
                {
                    "title": "Python documentation",
                    "url": "https://docs.python.org/3/",
                    "content": "Official Python docs",
                    "score": 0.97,
                },
                {
                    "title": "Third party",
                    "url": "https://example.com/python",
                    "content": "Not in the requested domain",
                    "score": 0.3,
                },
            ],
        },
    )
    tool = create_web_search_tool()
    assert tool.handler is not None
    result = await tool.handler(
        {
            "query": "Python documentation",
            "count": 5,
            "search_depth": "advanced",
            "topic": "general",
            "include": ["python.org"],
        },
        None,
    )

    assert result["provider"] == "tavily"
    assert result["result_count"] == 1
    assert result["results"][0]["rank"] == 1
    assert result["results"][0]["url"] == "https://docs.python.org/3/"
    request = httpx_mock.get_request()
    assert request is not None
    body = json.loads(request.content)
    assert body["include_domains"] == ["python.org"]
    assert body["include_answer"] is False


@pytest.mark.asyncio
async def test_tavily_zero_results_is_not_negative_evidence(
    httpx_mock: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TAVILY_API_KEY", "tvly-test")
    monkeypatch.delenv("BOCHA_API_KEY", raising=False)
    httpx_mock.add_response(method="POST", url=TAVILY_SEARCH_URL, json={"results": []})
    tool = create_web_search_tool()
    assert tool.handler is not None

    result = await tool.handler({"query": "rare event"}, None)

    assert result["ok"] is True
    assert result["results"] == []
    assert "not evidence" in result["warning"]
