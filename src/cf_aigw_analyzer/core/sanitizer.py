"""Strip request/response body content from log metadata before persistence.

The Cloudflare AI Gateway logs endpoint returns metadata that **sometimes**
includes inline body fields (especially for short prompts/responses). We do
not want to persist body content. This module walks the JSON tree and drops
keys that match a deny-list, recursively.
"""

from __future__ import annotations

from typing import Any

REDACTED = "<redacted>"

BODY_FIELD_KEYS = frozenset(
    {
        "request",
        "response",
        "request_body",
        "response_body",
        "_request_content",
        "_response_content",
        "body",
        "content",
        "contents",
        "message",
        "messages",
        "prompt",
        "prompts",
        "input",
        "inputs",
        "output",
        "outputs",
        "text",
    }
)

GATEWAY_SECRET_KEYS = frozenset(
    {
        "api_key",
        "apikey",
        "authorization",
        "cookie",
        "headers",
        "password",
        "secret",
        "set-cookie",
        "token",
        "x-api-key",
        "x-api-token",
        "x-auth-key",
    }
)


def sanitize_log_metadata(value: Any) -> Any:
    """Return a copy of ``value`` with body-like keys removed at every depth."""

    if isinstance(value, dict):
        return {
            key: sanitize_log_metadata(child)
            for key, child in value.items()
            if str(key).lower() not in BODY_FIELD_KEYS
        }
    if isinstance(value, list):
        return [sanitize_log_metadata(item) for item in value]
    return value


def sanitize_gateway_metadata(value: Any) -> Any:
    """Return gateway config metadata with secrets redacted but policy shape preserved."""

    if isinstance(value, dict):
        cleaned: dict[str, Any] = {}
        for key, child in value.items():
            if str(key).lower() in GATEWAY_SECRET_KEYS:
                cleaned[key] = REDACTED
            else:
                cleaned[key] = sanitize_gateway_metadata(child)
        return cleaned
    if isinstance(value, list):
        return [sanitize_gateway_metadata(item) for item in value]
    return value
