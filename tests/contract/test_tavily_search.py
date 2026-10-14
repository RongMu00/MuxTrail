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


@pytest.mark.asyncio
async def test_tavily_reranks_official_release_above_old_discussion(
    httpx_mock: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TAVILY_API_KEY", "tvly-test")
    monkeypatch.delenv("BOCHA_API_KEY", raising=False)
    httpx_mock.add_response(
        method="POST",
        url=TAVILY_SEARCH_URL,
        json={
            "request_id": "req-authority",
            "results": [
                {
                    "title": "Python latest stable version?",
                    "url": "https://discuss.python.org/t/python-latest-stable-version/24563",
                    "content": "An old discussion mentioning Python 3.11.2.",
                    "score": 0.99,
                },
                {
                    "title": "Python 3.15.0",
                    "url": "https://www.python.org/downloads/release/python-3150/",
                    "content": "This is the stable release of Python 3.15.0.",
                    "score": 0.75,
                },
            ],
        },
    )
    tool = create_web_search_tool()
    assert tool.handler is not None

    result = await tool.handler(
        {
            "query": "latest stable Python release",
            "include": ["python.org"],
            "count": 5,
        },
        None,
    )

    assert result["results"][0]["url"].endswith("/downloads/release/python-3150/")
    assert result["results"][0]["source_kind"] == "official-release"
    assert result["results"][0]["rank"] == 1
    assert result["results"][1]["source_kind"] == "discussion"
    assert result["provider_metadata"]["ranking_policy"] == "authority-aware-v1"
    assert "Do not use a discussion thread" in result["research_guidance"]
