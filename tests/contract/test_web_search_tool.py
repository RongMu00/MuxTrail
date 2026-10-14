# 文件说明：本文件属于 契约测试层。
# 主要职责：覆盖 web search tool 相关行为。
# 阅读提示：验证单模块行为和协议兼容性。
# 运行影响：仅用于源码阅读，不改变运行逻辑。

"""Contract tests for web_search."""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
from muxtrail.tools.builtin.web_search import (
    BOCHA_WEB_SEARCH_URL,
    create_web_search_tool,
)
from muxtrail.tools.types import ToolContext


@pytest.mark.asyncio
async def test_web_search_uses_bocha_when_key_is_configured(
    httpx_mock: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BOCHA_API_KEY", "bocha-test-key")
    httpx_mock.add_response(
        method="POST",
        url=BOCHA_WEB_SEARCH_URL,
        json={
            "code": 0,
            "data": {
                "webPages": {
                    "value": [
                        {
                            "name": "MuxTrail Search",
                            "url": "https://example.com/muxtrail",
                            "snippet": "A search result.",
                            "summary": "A summarized search result.",
                            "siteName": "Example",
                            "datePublished": "2026-04-26",
                        }
                    ]
                }
            },
        },
    )

    tool = create_web_search_tool()
    assert tool.handler is not None
    result = await tool.handler({"query": "MuxTrail", "count": 3, "freshness": "oneWeek"}, None)

    assert result["provider"] == "bocha"
    assert result["results"][0]["title"] == "MuxTrail Search"
    assert result["results"][0]["site_name"] == "Example"

    request = httpx_mock.get_request()
    assert request is not None
    assert request.headers["authorization"] == "Bearer bocha-test-key"
    payload = json.loads(request.content.decode())
    assert payload["query"] == "MuxTrail"
    assert payload["count"] == 3
    assert payload["freshness"] == "oneWeek"
    assert payload["summary"] is True


@pytest.mark.asyncio
async def test_bocha_domain_filters_are_strings_and_enforced_locally(
    httpx_mock: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BOCHA_API_KEY", "bocha-test-key")
    httpx_mock.add_response(
        method="POST",
        url=BOCHA_WEB_SEARCH_URL,
        json={
            "code": 200,
            "data": {
                "webPages": {
                    "value": [
                        {
                            "name": "Python release",
                            "url": "https://docs.python.org/3.14/whatsnew/3.14.html",
                        },
                        {
                            "name": "Unrelated mirror",
                            "url": "https://example.invalid/python-3-14",
                        },
                    ]
                }
            },
        },
    )

    tool = create_web_search_tool()
    assert tool.handler is not None
    result = await tool.handler(
        {"query": "Python 3.14", "include": ["python.org", "www.python.org"]},
        None,
    )

    request = httpx_mock.get_request()
    assert request is not None
    payload = json.loads(request.content.decode())
    assert payload["include"] == "python.org|www.python.org"
    assert [item["url"] for item in result["results"]] == [
        "https://docs.python.org/3.14/whatsnew/3.14.html"
    ]


@pytest.mark.asyncio
async def test_bocha_error_includes_provider_message(
    httpx_mock: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BOCHA_API_KEY", "bocha-test-key")
    httpx_mock.add_response(
        method="POST",
        url=BOCHA_WEB_SEARCH_URL,
        status_code=400,
        json={"msg": "invalid include"},
    )

    tool = create_web_search_tool()
    assert tool.handler is not None
    result = await tool.handler({"query": "Python", "include": ["python.org"]}, None)

    assert result["results"] == []
    assert result["error"] == "Bocha search failed: HTTP 400 — invalid include"


@pytest.mark.asyncio
async def test_bocha_reports_when_required_domain_has_no_results(
    httpx_mock: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BOCHA_API_KEY", "bocha-test-key")
    httpx_mock.add_response(
        method="POST",
        url=BOCHA_WEB_SEARCH_URL,
        json={"code": 200, "data": {"webPages": {"value": []}}},
    )
    httpx_mock.add_response(
        method="GET",
        text="<?xml version='1.0'?><rss><channel></channel></rss>",
        headers={"content-type": "text/xml"},
    )

    tool = create_web_search_tool()
    assert tool.handler is not None
    result = await tool.handler({"query": "Python", "include": ["python.org"]}, None)

    assert result["results"] == []
    assert result["error"].endswith("python.org")
    assert result["fallback_provider"] == "bing-rss"


@pytest.mark.asyncio
async def test_bocha_empty_results_fall_back_to_focused_bing_rss(
    httpx_mock: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BOCHA_API_KEY", "bocha-test-key")
    for _ in range(3):
        httpx_mock.add_response(
            method="POST",
            url=BOCHA_WEB_SEARCH_URL,
            json={"code": 200, "data": {"webPages": {"value": []}}},
        )

    def bing_response(request: httpx.Request) -> httpx.Response:
        assert request.url.params["format"] == "rss"
        assert request.url.params["q"] == 'site:python.org "Python 3.14"'
        return httpx.Response(
            200,
            headers={"content-type": "text/xml"},
            text="""<?xml version="1.0"?>
                <rss><channel>
                  <item>
                    <title>Python Release Python 3.14.0 | Python.org</title>
                    <link>https://www.python.org/downloads/release/python-3140/</link>
                    <description>Python 3.14.0 is the stable release.</description>
                  </item>
                  <item>
                    <title>Third-party Python 3.14 article</title>
                    <link>https://example.com/python-314</link>
                    <description>Unofficial coverage.</description>
                  </item>
                  <item>
                    <title>Python Release Python 3.12.4 | Python.org</title>
                    <link>https://www.python.org/downloads/release/python-3124/</link>
                    <description>An older release.</description>
                  </item>
                </channel></rss>""",
        )

    httpx_mock.add_callback(bing_response, method="GET")

    tool = create_web_search_tool()
    assert tool.handler is not None
    result = await tool.handler(
        {
            "query": "Python 3.14 release official announcement",
            "include": ["python.org"],
        },
        None,
    )

    assert result["provider"] == "bing-rss"
    assert result["fallback_from"] == "bocha"
    assert result["effective_query"] == 'site:python.org "Python 3.14"'
    assert result["primary_attempted_queries"] == [
        "Python 3.14 release official announcement",
        "Python 3.14 release",
        '"Python 3.14"',
    ]
    assert [item["url"] for item in result["results"]] == [
        "https://www.python.org/downloads/release/python-3140/"
    ]


@pytest.mark.asyncio
async def test_duckduckgo_challenge_is_reported_as_an_error(
    httpx_mock: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("BOCHA_API_KEY", raising=False)
    httpx_mock.add_response(
        method="POST",
        url="https://html.duckduckgo.com/html/",
        status_code=202,
        html="<html><title>DuckDuckGo</title><div class='anomaly challenge'>bot</div></html>",
    )
    httpx_mock.add_response(
        method="GET",
        text="<?xml version='1.0'?><rss><channel></channel></rss>",
        headers={"content-type": "text/xml"},
    )

    tool = create_web_search_tool()
    assert tool.handler is not None
    result = await tool.handler({"query": "Python"}, None)

    assert result["results"] == []
    assert "anti-automation challenge" in result["error"]


@pytest.mark.asyncio
async def test_public_search_fallback_reports_missing_tavily_provenance(
    httpx_mock: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    monkeypatch.delenv("BOCHA_API_KEY", raising=False)
    httpx_mock.add_response(
        method="POST",
        url="https://html.duckduckgo.com/html/",
        html="<html><body>No results</body></html>",
    )
    httpx_mock.add_response(
        method="GET",
        url="https://www.bing.com/search?format=rss&q=MuxTrail",
        headers={"content-type": "text/xml"},
        text=(
            "<?xml version='1.0'?><rss><channel><item><title>Source</title>"
            "<link>https://example.com/source</link><description>Evidence</description>"
            "</item></channel></rss>"
        ),
    )
    tool = create_web_search_tool()
    assert tool.handler is not None

    result = await tool.handler({"query": "MuxTrail"}, None)

    assert result["provider"] == "bing-rss"
    assert result["fallback_from"] == "tavily"
    assert result["fallback_reason"] == "TAVILY_API_KEY is not configured"
    assert result["intermediate_provider"] == "duckduckgo"


@pytest.mark.asyncio
async def test_official_source_request_requires_include_domain(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BOCHA_API_KEY", "bocha-test-key")
    tool = create_web_search_tool()
    assert tool.handler is not None

    result = await tool.handler(
        {"query": "Python 3.14 release"},
        ToolContext(user_message="搜索 Python 3.14 的官方发布信息"),
    )

    assert result["provider"] == "policy"
    assert result["results"] == []
    assert "include" in result["error"]
    assert "third-party" in result["error"]


def test_web_search_tool_exposes_research_prompt_instruction() -> None:
    tool = create_web_search_tool()

    assert "deep exploration" in tool.prompt_instructions
    assert "current or changing information" in tool.prompt_instructions
    assert "never invent citations" in tool.prompt_instructions
    assert "do not guess factual conclusions" in tool.prompt_instructions
