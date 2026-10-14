# 文件说明：本文件属于 工具系统层。
# 主要职责：实现 web search 相关能力。
# 阅读提示：注册、执行和限制工具调用。
# 运行影响：仅用于源码阅读，不改变运行逻辑。

"""联网搜索工具：优先使用 Bocha，没有 API Key 时降级到 DuckDuckGo HTML 搜索。"""

from __future__ import annotations

import os
import re
from typing import Any
from urllib.parse import unquote, urlparse
from xml.etree import ElementTree

import httpx

from muxtrail.tools.types import ToolDefinition

BOCHA_WEB_SEARCH_URL = "https://api.bocha.cn/v1/web-search"
DEFAULT_RESULT_COUNT = 8
MAX_RESULT_COUNT = 20
BING_RSS_SEARCH_URL = "https://www.bing.com/search"
WEB_SEARCH_PROMPT_INSTRUCTIONS = (
    "Use web_search for deep exploration, current or changing information, niche topics, "
    "fact verification, and source-backed answers. For requests asking for a detailed analysis "
    "of a concept that may require external context, search first, then synthesize using the "
    "returned sources. When search results will be used in a report or document, use the actual "
    "returned titles, URLs, snippets, summaries, and publication dates; never invent citations "
    "or leave placeholders such as URL_1, source TBD, 指标A, or 待补充. If the search result does "
    "not provide official or primary material, say that clearly in the generated content. If "
    "the tool returns an error or no results, state that search failed or found no usable "
    "results; do not infer that an event did not happen and do not guess factual conclusions. "
    "Do not call web_search for simple stable facts or purely local tasks."
)


def _normalize_domains(value: Any) -> list[str]:
    """Normalize include/exclude values into validated hostnames."""
    if isinstance(value, str):
        raw_items = re.split(r"[|,]", value)
    elif isinstance(value, list):
        raw_items = [str(item) for item in value]
    else:
        return []

    domains: list[str] = []
    for raw in raw_items:
        candidate = raw.strip().lower()
        if not candidate:
            continue
        parsed = urlparse(candidate if "://" in candidate else f"https://{candidate}")
        hostname = (parsed.hostname or "").strip(".")
        if (
            hostname
            and re.fullmatch(r"[a-z0-9][a-z0-9.-]*\.[a-z]{2,}", hostname)
            and hostname not in domains
        ):
            domains.append(hostname)
    return domains


def _matches_domain(url: str, domain: str) -> bool:
    try:
        hostname = (urlparse(url).hostname or "").lower()
    except ValueError:
        return False
    return hostname == domain or hostname.endswith(f".{domain}")


def _filter_results(
    results: list[dict[str, str]], include: list[str], exclude: list[str]
) -> list[dict[str, str]]:
    filtered: list[dict[str, str]] = []
    for result in results:
        url = result.get("url", "")
        if not url:
            continue
        if exclude and any(_matches_domain(url, domain) for domain in exclude):
            continue
        if include and not any(_matches_domain(url, domain) for domain in include):
            continue
        filtered.append(result)
    return filtered


def _extract_version_anchor(query: str) -> str:
    """Extract a stable product/version phrase such as ``Python 3.14``.

    Search providers often perform poorly on long requests containing words such as
    "official announcement".  The product/version pair is a safer retry anchor than a
    provider-specific rewrite or a hard-coded product name.
    """
    match = re.search(
        r"\b([A-Za-z][A-Za-z0-9_+#.-]*(?:\s+[A-Za-z][A-Za-z0-9_+#.-]*){0,2})"
        r"\s+(v?\d+(?:\.\d+){1,3})\b",
        query,
        re.I,
    )
    if not match:
        return ""
    product = re.sub(r"\s+", " ", match.group(1)).strip()
    version = match.group(2).lstrip("vV")
    return f"{product} {version}"


def _query_variants(query: str) -> list[str]:
    """Create a small, deterministic set of increasingly focused retries."""
    variants = [query]
    cleaned = re.sub(
        r"\b(official\s+announcement|official\s+release\s+information)\b",
        " ",
        query,
        flags=re.I,
    )
    cleaned = re.sub(r"(官方发布信息|官方公告|官方信息)", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,，。")
    if cleaned and cleaned.lower() != query.lower():
        variants.append(cleaned)

    anchor = _extract_version_anchor(query)
    if anchor:
        quoted_anchor = f'"{anchor}"'
        if all(quoted_anchor.lower() != item.lower() for item in variants):
            variants.append(quoted_anchor)
    return variants[:3]


def _result_matches_anchor(result: dict[str, str], anchor: str) -> bool:
    if not anchor:
        return True
    haystack = " ".join(
        str(result.get(field, ""))
        for field in ("title", "url", "snippet", "summary")
    ).lower()
    return all(token.lower() in haystack for token in anchor.split())


def _bing_query(query: str, include: list[str]) -> str:
    anchor = _extract_version_anchor(query)
    search_terms = f'"{anchor}"' if anchor else query
    if not include:
        return search_terms
    if len(include) == 1:
        return f"site:{include[0]} {search_terms}"
    site_terms = " OR ".join(f"site:{domain}" for domain in include)
    return f"({site_terms}) {search_terms}"


def _official_sources_required(context: Any) -> bool:
    user_message = str(getattr(context, "user_message", "") or "")
    return "官方" in user_message or bool(re.search(r"\bofficial\b", user_message, re.I))


def _clamp_count(value: Any) -> int:
    try:
        count = int(value)
    except (TypeError, ValueError):
        count = DEFAULT_RESULT_COUNT
    return max(1, min(count, MAX_RESULT_COUNT))


def _bocha_result(item: dict[str, Any]) -> dict[str, str]:
    # Bocha 返回字段和内部工具字段不完全一致，这里统一成模型稳定可读的结果结构。
    title = item.get("name") or item.get("title") or ""
    snippet = item.get("snippet") or item.get("summary") or ""
    return {
        "title": str(title),
        "url": str(item.get("url") or ""),
        "snippet": str(snippet),
        "summary": str(item.get("summary") or ""),
        "site_name": str(item.get("siteName") or item.get("site_name") or ""),
        "date_published": str(item.get("datePublished") or item.get("date_published") or ""),
    }


async def _bocha_search(params: dict[str, Any], api_key: str) -> dict[str, Any]:
    query = str(params.get("query") or "").strip()
    if not query:
        raise ValueError("query is required")

    count = _clamp_count(params.get("count", params.get("max_results", DEFAULT_RESULT_COUNT)))
    freshness = str(params.get("freshness") or "noLimit")
    summary = bool(params.get("summary", True))
    base_body: dict[str, Any] = {
        "freshness": freshness,
        "summary": summary,
        "count": count,
    }
    include = _normalize_domains(params.get("include"))
    exclude = _normalize_domains(params.get("exclude"))
    # Bocha requires a string, not an array. Keep a local post-filter as a safety check.
    if include:
        base_body["include"] = "|".join(include)
    if exclude:
        base_body["exclude"] = "|".join(exclude)

    variants = _query_variants(query) if include else [query]
    attempted_queries: list[str] = []
    anchor = _extract_version_anchor(query) if include else ""
    results: list[dict[str, str]] = []
    effective_query = query

    async with httpx.AsyncClient(timeout=30) as client:
        for candidate in variants:
            attempted_queries.append(candidate)
            body = {**base_body, "query": candidate}
            resp = await client.post(
                BOCHA_WEB_SEARCH_URL,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=body,
            )
            if resp.status_code != 200:
                detail = ""
                try:
                    error_payload = resp.json()
                    detail = str(
                        error_payload.get("msg") or error_payload.get("message") or ""
                    ).strip()
                except Exception:
                    detail = resp.text.strip()[:300]
                return {
                    "query": query,
                    "provider": "bocha",
                    "results": [],
                    "attempted_queries": attempted_queries,
                    "error": (
                        f"Bocha search failed: HTTP {resp.status_code}"
                        + (f" — {detail}" if detail else "")
                    ),
                }

            payload = resp.json()
            raw_data = payload.get("data") if isinstance(payload, dict) else {}
            data: dict[str, Any] = raw_data if isinstance(raw_data, dict) else {}
            raw_web_pages = data.get("webPages")
            web_pages = raw_web_pages if isinstance(raw_web_pages, dict) else {}
            raw_items = web_pages.get("value")
            items: list[Any] = raw_items if isinstance(raw_items, list) else []
            # 搜索结果里偶发异常 item 时直接跳过，避免一个坏条目导致整次搜索失败。
            results = [_bocha_result(item) for item in items if isinstance(item, dict)]
            results = _filter_results(results, include, exclude)
            if anchor:
                results = [item for item in results if _result_matches_anchor(item, anchor)]
            if results:
                effective_query = candidate
                break

    response: dict[str, Any] = {
        "query": query,
        "provider": "bocha",
        "freshness": freshness,
        "summary": summary,
        "results": results[:count],
        "attempted_queries": attempted_queries,
    }
    if effective_query != query:
        response["effective_query"] = effective_query
        response["query_rewritten"] = True
    if not results:
        response["retryable"] = True
        if include:
            response["error"] = (
                "Bocha returned no usable results matching required domains: "
                + ", ".join(include)
            )
        else:
            response["error"] = "Bocha returned no usable results"
    return response


async def _bing_rss_search(params: dict[str, Any]) -> dict[str, Any]:
    """Use Bing's public RSS results as a provider-independent fallback."""
    query = str(params.get("query") or "").strip()
    if not query:
        raise ValueError("query is required")
    count = _clamp_count(params.get("count", params.get("max_results", DEFAULT_RESULT_COUNT)))
    include = _normalize_domains(params.get("include"))
    exclude = _normalize_domains(params.get("exclude"))
    effective_query = _bing_query(query, include)

    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            resp = await client.get(
                BING_RSS_SEARCH_URL,
                params={"format": "rss", "q": effective_query},
                headers={"User-Agent": "Mozilla/5.0 (compatible; MuxTrail/0.1)"},
            )
    except Exception as exc:
        return {
            "query": query,
            "provider": "bing-rss",
            "results": [],
            "effective_query": effective_query,
            "error": f"Bing RSS fallback failed: {exc}",
        }

    if resp.status_code != 200:
        return {
            "query": query,
            "provider": "bing-rss",
            "results": [],
            "effective_query": effective_query,
            "error": f"Bing RSS fallback failed: HTTP {resp.status_code}",
        }

    try:
        root = ElementTree.fromstring(resp.text)
    except ElementTree.ParseError as exc:
        return {
            "query": query,
            "provider": "bing-rss",
            "results": [],
            "effective_query": effective_query,
            "error": f"Bing RSS fallback returned invalid XML: {exc}",
        }

    results: list[dict[str, str]] = []
    for item in root.findall("./channel/item"):
        results.append(
            {
                "title": str(item.findtext("title") or "").strip(),
                "url": str(item.findtext("link") or "").strip(),
                "snippet": str(item.findtext("description") or "").strip(),
                "summary": "",
                "site_name": "",
                "date_published": str(item.findtext("pubDate") or "").strip(),
            }
        )
    results = _filter_results(results, include, exclude)
    anchor = _extract_version_anchor(query)
    if anchor:
        results = [item for item in results if _result_matches_anchor(item, anchor)]

    response: dict[str, Any] = {
        "query": query,
        "provider": "bing-rss",
        "effective_query": effective_query,
        "query_rewritten": effective_query != query,
        "results": results[:count],
    }
    if not results:
        response["error"] = "Bing RSS fallback returned no usable results"
    return response


async def _duckduckgo_search(params: dict[str, Any]) -> dict[str, Any]:
    query = str(params.get("query") or "").strip()
    if not query:
        raise ValueError("query is required")
    count = _clamp_count(params.get("count", params.get("max_results", DEFAULT_RESULT_COUNT)))

    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            resp = await client.post(
                "https://html.duckduckgo.com/html/",
                data={"q": query},
                headers={"User-Agent": "Mozilla/5.0 (compatible; MuxTrail/0.1)"},
            )
            html = resp.text
    except Exception as e:
        return {
            "query": query,
            "provider": "duckduckgo",
            "error": f"Search failed: {e}",
            "results": [],
        }

    lowered = html.lower()
    if resp.status_code != 200 or (
        "result__a" not in lowered
        and any(marker in lowered for marker in ("anomaly", "challenge", "bot"))
    ):
        return {
            "query": query,
            "provider": "duckduckgo",
            "error": "DuckDuckGo returned an anti-automation challenge instead of results",
            "results": [],
        }

    results: list[dict[str, str]] = []
    links = re.findall(r'<a rel="nofollow" class="result__a" href="([^"]+)"[^>]*>(.*?)</a>', html)
    snippets = re.findall(r'<a class="result__snippet"[^>]*>(.*?)</a>', html, re.DOTALL)

    for index, (href, title) in enumerate(links[:count]):
        title_clean = re.sub(r"<[^>]+>", "", title).strip()
        snippet = re.sub(r"<[^>]+>", "", snippets[index]).strip() if index < len(snippets) else ""
        actual_url = href
        uddg_match = re.search(r"uddg=([^&]+)", href)
        if uddg_match:
            # DuckDuckGo HTML 结果会把真实目标地址包在 uddg 参数里，需要解包。
            actual_url = unquote(uddg_match.group(1))
        results.append({"title": title_clean, "url": actual_url, "snippet": snippet})

    include = _normalize_domains(params.get("include"))
    exclude = _normalize_domains(params.get("exclude"))
    results = _filter_results(results, include, exclude)
    response: dict[str, Any] = {"query": query, "provider": "duckduckgo", "results": results}
    if not results:
        response["error"] = "DuckDuckGo returned no usable results"
    return response


async def _handler(params: dict[str, Any], context: Any = None) -> dict[str, Any]:
    if _official_sources_required(context) and not _normalize_domains(params.get("include")):
        return {
            "query": str(params.get("query") or "").strip(),
            "provider": "policy",
            "results": [],
            "error": (
                "Official-source request blocked: call web_search again with include set to "
                "the official domain (for example, ['python.org']). Do not use unverified "
                "third-party results."
            ),
        }
    api_key = os.environ.get("BOCHA_API_KEY", "").strip()
    if api_key:
        primary = await _bocha_search(params, api_key)
        if primary.get("results") or not primary.get("retryable"):
            return primary
    else:
        primary = await _duckduckgo_search(params)
        if primary.get("results"):
            return primary

    fallback = await _bing_rss_search(params)
    if fallback.get("results"):
        fallback["fallback_from"] = primary.get("provider", "unknown")
        fallback["primary_error"] = primary.get("error", "")
        if primary.get("attempted_queries"):
            fallback["primary_attempted_queries"] = primary["attempted_queries"]
        fallback["search_warning"] = (
            "The primary provider returned no usable results. These fallback results passed "
            "the requested domain and topic checks; fetch the relevant pages before answering."
        )
        return fallback

    primary["fallback_provider"] = "bing-rss"
    primary["fallback_error"] = fallback.get("error", "")
    primary["fallback_effective_query"] = fallback.get("effective_query", "")
    return primary


def create_web_search_tool() -> ToolDefinition:
    return ToolDefinition(
        name="web_search",
        description=(
            "Search the web for current, factual, or deep-research information. Uses Bocha "
            "Web Search API when BOCHA_API_KEY is configured, otherwise tries DuckDuckGo. If "
            "the primary provider has no usable results, retries focused queries and uses Bing "
            "RSS as a fallback. Use returned result fields directly as evidence; do not "
            "fabricate citations."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query."},
                "count": {
                    "type": "integer",
                    "default": DEFAULT_RESULT_COUNT,
                    "description": "Number of results to return, 1-20.",
                },
                "max_results": {
                    "type": "integer",
                    "default": DEFAULT_RESULT_COUNT,
                    "description": "Backward-compatible alias for count.",
                },
                "freshness": {
                    "type": "string",
                    "enum": ["oneDay", "oneWeek", "oneMonth", "oneYear", "noLimit"],
                    "default": "noLimit",
                },
                "summary": {"type": "boolean", "default": True},
                "include": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional domains to include.",
                },
                "exclude": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional domains to exclude.",
                },
            },
            "required": ["query"],
        },
        prompt_instructions=WEB_SEARCH_PROMPT_INSTRUCTIONS,
        handler=_handler,
    )
