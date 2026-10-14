"""Central recursive redaction for logs, traces, config responses, and errors."""

from __future__ import annotations

import re
from typing import Any

SENSITIVE_KEYS = ("secret", "token", "password", "api_key", "apikey", "authorization")
TOKEN_PATTERN = re.compile(
    r"(?i)"
    r"(bearer\s+)[A-Za-z0-9._~-]{8,}"
    r"|\b(?:xox[baprs]-|xapp-)[A-Za-z0-9-]{8,}"
    r"|\bsk-ant-[A-Za-z0-9_-]{16,}\b"
    r"|\bsk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{16,}\b"
    r"|\btvly-[A-Za-z0-9_-]{16,}\b"
    r"|\bmfa\.[A-Za-z0-9_-]{20,}\b"
    r"|\b[A-Za-z0-9_-]{23,28}\.[A-Za-z0-9_-]{6}\.[A-Za-z0-9_-]{25,}\b"
)


def redact(value: Any, key: str = "") -> Any:
    if key and any(part in key.lower() for part in SENSITIVE_KEYS):
        return "[redacted]"
    if isinstance(value, str):
        return TOKEN_PATTERN.sub(
            lambda match: f"{match.group(1)}[redacted]" if match.group(1) else "[redacted]", value
        )
    if isinstance(value, dict):
        return {str(item_key): redact(item, str(item_key)) for item_key, item in value.items()}
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact(item) for item in value)
    return value
