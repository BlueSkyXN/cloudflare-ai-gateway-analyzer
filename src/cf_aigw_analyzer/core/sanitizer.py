"""Keep only analytics-safe log metadata and redact gateway secrets.

Cloudflare is an external, evolving contract. A deny-list cannot guarantee the
project invariant that request/response bodies never reach SQLite because a
new alias such as ``requestBody`` or a stringified JSON wrapper would be kept by
default. Log sanitization is therefore fail-closed: only known scalar analytics
fields plus a small numeric ``timings`` object are persisted.
"""

from __future__ import annotations

import re
from math import isfinite
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

LOG_METADATA_SCALAR_KEYS = frozenset(
    {
        "id",
        "log_id",
        "created_at",
        "provider",
        "model",
        "model_type",
        "success",
        "cached",
        "status_code",
        "cost",
        "cost_usd",
        "custom_cost",
        "tokens_in",
        "tokens_out",
        "input_tokens",
        "output_tokens",
        "total_tokens",
        "duration",
        "request_content_type",
        "response_content_type",
        "request_type",
        "step",
        "feedback",
        "event_id",
        "wholesale",
        "compatibility_mode",
        "dlp_action",
        "_total_ms",
        "_latency_ms",
        "_generation_ms",
        "_input_tps",
        "_output_tps",
        "_reasoning_tokens",
    }
)

TIMING_FIELD_KEYS = frozenset(
    {
        "total",
        "latency",
        "generation",
        "ttft",
        "time_to_first_token",
        "time_to_first_byte",
    }
)

GATEWAY_SECRET_KEYS = frozenset(
    {
        "api_key",
        "api_token",
        "apikey",
        "access_token",
        "auth",
        "authorization",
        "authorization_header",
        "client_secret",
        "cookie",
        "credentials",
        "headers",
        "id_token",
        "password",
        "private_key",
        "secret",
        "secret_key",
        "set_cookie",
        "token",
        "x_api_key",
        "x_api_token",
        "x_auth_key",
    }
)


def sanitize_log_metadata(value: Any) -> Any:
    """Return a fail-closed copy containing only analytics-safe log metadata."""

    if isinstance(value, dict):
        cleaned: dict[str, Any] = {}
        for key, child in value.items():
            normalized = _normalize_key(key)
            if normalized in BODY_FIELD_KEYS:
                continue
            if normalized == "timings" and isinstance(child, dict):
                timings = {
                    timing_key: timing_value
                    for timing_key, timing_value in child.items()
                    if _normalize_key(timing_key) in TIMING_FIELD_KEYS and _is_numeric(timing_value)
                }
                if timings:
                    cleaned[key] = timings
                continue
            if normalized in LOG_METADATA_SCALAR_KEYS and _is_scalar(child):
                cleaned[key] = child
        return cleaned
    if isinstance(value, list):
        return [sanitize_log_metadata(item) for item in value]
    return value


def sanitize_gateway_metadata(value: Any) -> Any:
    """Return gateway config metadata with secrets redacted but policy shape preserved."""

    if isinstance(value, dict):
        cleaned: dict[str, Any] = {}
        for key, child in value.items():
            if _is_gateway_secret_key(key):
                cleaned[key] = REDACTED
            else:
                cleaned[key] = sanitize_gateway_metadata(child)
        return cleaned
    if isinstance(value, list):
        return [sanitize_gateway_metadata(item) for item in value]
    return value


def _normalize_key(value: Any) -> str:
    text = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", str(value))
    text = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", text)
    return text.replace("-", "_").replace(" ", "_").lower()


def _is_scalar(value: Any) -> bool:
    return value is None or isinstance(value, (str, int, float, bool))


def _is_numeric(value: Any) -> bool:
    if value is None or isinstance(value, bool):
        return False
    try:
        return isfinite(float(value))
    except (TypeError, ValueError):
        return False


def _is_gateway_secret_key(value: Any) -> bool:
    normalized = _normalize_key(value)
    if normalized in GATEWAY_SECRET_KEYS:
        return True
    return normalized.endswith(
        (
            "_api_key",
            "_authorization",
            "_authorization_header",
            "_auth_key",
            "_cookie",
            "_credentials",
            "_headers",
            "_password",
            "_private_key",
            "_secret",
            "_secret_key",
            "_token",
        )
    )
