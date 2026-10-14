"""Secret redaction tests for user-visible and logged structures."""

from muxtrail.core.redaction import redact


def test_redaction_handles_keys_and_embedded_tokens() -> None:
    value = {
        "api_key": "sk-secret",
        "nested": {"authorization": "Bearer abcdefghijklmnop"},
        "message": "request used " + "xoxb-" + "abcdefghijklmnop",
    }

    result = redact(value)

    assert result["api_key"] == "[redacted]"
    assert result["nested"]["authorization"] == "[redacted]"
    assert "xoxb-" not in result["message"]


def test_redaction_removes_provider_and_discord_tokens_embedded_in_text() -> None:
    secrets = [
        "sk-proj-" + "abcdefghijklmnopqrstuvwx",
        "sk-" + "abcdefghijklmnopqrstuvwx",
        "sk-ant-" + "abcdefghijklmnopqrstuvwx",
        "tvly-" + "abcdefghijklmnopqrstuvwx",
        "mfa." + "abcdefghijklmnopqrstuvwxyz012345",
        "Abcdefghijklmnopqrstuvw." + "ABC123." + "abcdefghijklmnopqrstuvwxyz012345",
    ]
    result = redact("tokens: " + " ".join(secrets))

    assert result.count("[redacted]") == len(secrets)
    assert all(secret not in result for secret in secrets)


def test_redaction_avoids_short_product_terms_and_identifiers() -> None:
    text = "sk-short tvly-concept package.token.value and abc.def"

    assert redact(text) == text
