"""Central recursive redaction for logs, traces, config responses, and errors."""

from __future__ import annotations

import re
from typing import Any

SENSITIVE_KEYS = ("secret", "token", "password", "api_key", "apikey", "authorization")
TOKEN_PATTERN = re.compile(
    r"(?i)(bearer\s+)[A-Za-z0-9._~-]{8,}|\b(?:xox[baprs]-|xapp-)[A-Za-z0-9-]+"
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
