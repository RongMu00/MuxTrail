"""Contract tests for model-facing transcript history."""

from openclaw.gateway.boot import (
    _extract_search_error,
    _history_for_model,
    _search_failure_reply,
)


def test_history_excludes_failed_runs_with_run_ids() -> None:
    raw = [
        {"role": "user", "content": "works", "runId": "ok"},
        {"role": "assistant", "content": "yes", "runId": "ok"},
        {"role": "user", "content": "fails", "runId": "bad"},
        {"role": "error", "content": "provider error", "runId": "bad"},
    ]

    assert _history_for_model(raw) == raw[:2]


def test_history_removes_legacy_no_response_pairs() -> None:
    raw = [
        {"role": "user", "content": "failed old request"},
        {"role": "assistant", "content": "[No response]"},
        {"role": "user", "content": "successful request"},
        {"role": "assistant", "content": "successful response"},
    ]

    assert _history_for_model(raw) == raw[2:]


def test_search_error_detection_distinguishes_usable_results() -> None:
    assert (
        _extract_search_error('{"results": [], "error": "no official matches"}')
        == "no official matches"
    )
    assert _extract_search_error('{"results": [{"url": "https://python.org"}]}') is None


def test_search_failure_reply_rejects_factual_inference() -> None:
    reply = _search_failure_reply("no official matches")

    assert "no official matches" in reply
    assert "不能据此判断" in reply
    assert "版本尚未发布" in reply
