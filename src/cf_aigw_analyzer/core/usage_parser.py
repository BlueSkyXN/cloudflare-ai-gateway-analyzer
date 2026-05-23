"""Provider-aware usage parser.

Handles OpenAI-compatible, Anthropic, DeepSeek, Gemini, and Cloudflare-wrapped
JSON (with optional SSE-formatted ``data:`` lines) payloads.
"""

from __future__ import annotations

import json
from typing import Any

from cf_aigw_analyzer.data.models import UsageFields


def parse_usage_from_response(payload: Any) -> UsageFields:
    """Extract normalized token usage fields from a provider response payload."""

    payload = _decode_payload(payload)
    candidates: list[tuple[str, dict[str, Any]]] = []
    _collect_usage_candidates(candidates, "", payload)

    if not candidates:
        return UsageFields()

    source, usage = max(candidates, key=lambda item: _usage_score(item[1]))

    prompt_details = usage.get("prompt_tokens_details") or usage.get("input_tokens_details") or {}
    completion_details = (
        usage.get("completion_tokens_details") or usage.get("output_tokens_details") or {}
    )
    if not isinstance(prompt_details, dict):
        prompt_details = {}
    if not isinstance(completion_details, dict):
        completion_details = {}

    input_tokens = _first_int(
        usage.get("input_tokens"),
        usage.get("prompt_tokens"),
        usage.get("promptTokenCount"),
    )
    output_tokens = _first_int(
        usage.get("output_tokens"),
        usage.get("completion_tokens"),
        usage.get("candidatesTokenCount"),
    )
    total_tokens = _first_int(usage.get("total_tokens"), usage.get("totalTokenCount"))

    if input_tokens is None and total_tokens is not None and output_tokens is not None:
        input_tokens = max(total_tokens - output_tokens, 0)
    if output_tokens is None and total_tokens is not None and input_tokens is not None:
        output_tokens = max(total_tokens - input_tokens, 0)
    if total_tokens is None and input_tokens is not None and output_tokens is not None:
        total_tokens = input_tokens + output_tokens

    return UsageFields(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        cached_tokens=_first_int(
            usage.get("cache_read_input_tokens"),
            prompt_details.get("cached_tokens"),
            usage.get("prompt_cache_hit_tokens"),
            usage.get("cachedContentTokenCount"),
        ),
        reasoning_tokens=_first_int(
            completion_details.get("reasoning_tokens"),
            usage.get("reasoning_tokens"),
            usage.get("thoughtsTokenCount"),
        ),
        cache_write_tokens=_first_int(usage.get("cache_creation_input_tokens")),
        source=source,
    )


def _collect_usage_candidates(
    candidates: list[tuple[str, dict[str, Any]]],
    prefix: str,
    payload: Any,
) -> None:
    payload = _decode_payload(payload)
    if not isinstance(payload, dict):
        return

    for key in ("usage", "usage_metadata", "usageMetadata"):
        value = payload.get(key)
        if isinstance(value, dict):
            candidates.append((f"{prefix}.{key}" if prefix else key, value))

    for child_key in ("result", "response"):
        child = payload.get(child_key)
        if child is not None:
            _collect_usage_candidates(
                candidates,
                f"{prefix}.{child_key}" if prefix else child_key,
                child,
            )

    streamed_data = payload.get("streamed_data")
    if isinstance(streamed_data, list):
        for item in reversed(streamed_data):
            if isinstance(item, dict):
                _collect_usage_candidates(
                    candidates,
                    f"{prefix}.streamed_data" if prefix else "streamed_data",
                    item,
                )


def _decode_payload(payload: Any) -> Any:
    if not isinstance(payload, str):
        return payload
    text = payload.strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    events: list[dict[str, Any]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("data:"):
            continue
        event_text = line[5:].strip()
        if not event_text or event_text == "[DONE]":
            continue
        try:
            event = json.loads(event_text)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict):
            events.append(event)
    if events:
        return {"streamed_data": events}
    return None


def _usage_score(usage: dict[str, Any]) -> int:
    keys = (
        "input_tokens",
        "output_tokens",
        "total_tokens",
        "prompt_tokens",
        "completion_tokens",
        "promptTokenCount",
        "candidatesTokenCount",
        "totalTokenCount",
    )
    return sum(_as_int(usage.get(key)) or 0 for key in keys)


def _first_int(*values: Any) -> int | None:
    for value in values:
        parsed = _as_int(value)
        if parsed is not None:
            return parsed
    return None


def _as_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
