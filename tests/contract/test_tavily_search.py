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


@pytest.mark.asyncio
async def test_tavily_rejects_duplicate_superseded_release_results(
    httpx_mock: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TAVILY_API_KEY", "tvly-test")
    monkeypatch.delenv("BOCHA_API_KEY", raising=False)
    stale = {
        "title": "Python Release Python 3.9.0 | Python.org",
        "content": (
            "Python 3.9.0 has been superseded by Python 3.9.25. "
            "This is a legacy release and is no longer supported."
        ),
        "score": 0.83,
        "published_date": "Mon, 05 Oct 2020 00:00:00 GMT",
    }
    httpx_mock.add_response(
        method="POST",
        url=TAVILY_SEARCH_URL,
        json={
            "request_id": "req-stale",
            "results": [
                {**stale, "url": "http://www.python.org/downloads/release/python-390"},
                {**stale, "url": "https://www.python.org/downloads/release/python-390/"},
                {**stale, "url": "https://python.org/downloads/release/python-390"},
            ],
        },
    )
    tool = create_web_search_tool()
    assert tool.handler is not None

    result = await tool.handler(
        {
            "query": "latest stable Python release site:python.org",
            "include": ["python.org"],
            "search_depth": "basic",
        },
        None,
    )

    assert result["provider"] == "tavily"
    assert result["results"] == []
    assert result["result_count"] == 0
    assert len(result["rejected_results"]) == 1
    assert result["rejected_results"][0]["reason"] == "superseded release"
    assert "zero current, usable results" in result["warning"]
    request = httpx_mock.get_request()
    assert request is not None
    body = json.loads(request.content)
    assert body["query"] == "latest stable Python release"
    assert body["include_domains"] == ["python.org"]
    assert body["search_depth"] == "advanced"
    assert body["time_range"] == "year"
    assert body["include_published_date"] is True
    assert body["filter_by_published_date"] is True
    assert body["language"] == "en"


@pytest.mark.asyncio
async def test_tavily_prefers_version_status_and_rejects_old_release_dates(
    httpx_mock: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TAVILY_API_KEY", "tvly-test")
    monkeypatch.delenv("BOCHA_API_KEY", raising=False)
    httpx_mock.add_response(
        method="POST",
        url=TAVILY_SEARCH_URL,
        json={
            "request_id": "req-status",
            "results": [
                {
                    "title": "Python 3.9.7",
                    "url": "https://www.python.org/downloads/release/python-397/",
                    "content": "Release date: Aug. 30, 2021",
                    "score": 0.99,
                },
                {
                    "title": "Python 3.13.16",
                    "url": "https://www.python.org/downloads/release/python-31316/",
                    "content": "A supported maintenance release.",
                    "score": 0.95,
                },
                {
                    "title": "Status of Python versions",
                    "url": "https://devguide.python.org/versions/",
                    "content": "Current feature and security branches.",
                    "score": 0.60,
                },
            ],
        },
    )
    tool = create_web_search_tool()
    assert tool.handler is not None

    result = await tool.handler(
        {"query": "latest stable Python release", "include": ["python.org"]}, None
    )

    assert result["results"][0]["url"] == "https://devguide.python.org/versions/"
    assert result["results"][0]["source_kind"] == "official-status"
    assert any(
        item["url"].endswith("python-397/")
        and item["reason"] == "release date is from 2021"
        for item in result["rejected_results"]
    )
