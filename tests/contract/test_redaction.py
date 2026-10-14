"""Secret redaction tests for user-visible and logged structures."""

from muxtrail.core.redaction import redact


def test_redaction_handles_keys_and_embedded_tokens() -> None:
    value = {
        "api_key": "sk-secret",
        "nested": {"authorization": "Bearer abcdefghijklmnop"},
        "message": "request used xoxb-123456789-secret",
    }

    result = redact(value)

    assert result["api_key"] == "[redacted]"
    assert result["nested"]["authorization"] == "[redacted]"
    assert "xoxb-" not in result["message"]
