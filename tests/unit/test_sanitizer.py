"""Tests for sanitizer."""

from __future__ import annotations

from cf_aigw_analyzer.core.sanitizer import (
    REDACTED,
    sanitize_gateway_metadata,
    sanitize_log_metadata,
)


def test_removes_body_keys_recursively() -> None:
    payload = {
        "id": "log-1",
        "model": "gpt-test",
        "request": {"messages": ["hello"]},
        "response": "secret",
        "_request_content": "raw",
        "metadata": {
            "Messages": ["nested-secret"],
            "preserved": "ok",
            "Body": "drop",
        },
    }
    cleaned = sanitize_log_metadata(payload)

    assert cleaned == {
        "id": "log-1",
        "model": "gpt-test",
        "metadata": {"preserved": "ok"},
    }


def test_lists_are_walked() -> None:
    payload = {
        "events": [
            {"text": "drop", "type": "info"},
            {"type": "error", "details": {"message": "drop"}},
        ]
    }
    cleaned = sanitize_log_metadata(payload)
    assert cleaned == {"events": [{"type": "info"}, {"type": "error", "details": {}}]}


def test_non_dict_passes_through() -> None:
    assert sanitize_log_metadata(42) == 42
    assert sanitize_log_metadata("text") == "text"
    assert sanitize_log_metadata(None) is None


def test_case_insensitive_match() -> None:
    payload = {"REQUEST": "drop", "Body": "drop", "id": "1"}
    assert sanitize_log_metadata(payload) == {"id": "1"}


def test_gateway_metadata_redacts_secrets_but_keeps_policy_shape() -> None:
    payload = {
        "id": "open",
        "guardrails": {
            "prompt": {"S1": "BLOCK"},
            "response": {"S2": "FLAG"},
        },
        "otel": [
            {
                "url": "https://example.com",
                "headers": {"X-Api-Key": "secret"},
                "authorization": "Bearer secret",
            }
        ],
        "stripe": {"authorization": "stripe-secret", "usage_events": [{"payload": "usage"}]},
        "logpush_public_key": "public",
    }

    cleaned = sanitize_gateway_metadata(payload)

    assert cleaned == {
        "id": "open",
        "guardrails": {
            "prompt": {"S1": "BLOCK"},
            "response": {"S2": "FLAG"},
        },
        "otel": [
            {
                "url": "https://example.com",
                "headers": REDACTED,
                "authorization": REDACTED,
            }
        ],
        "stripe": {"authorization": REDACTED, "usage_events": [{"payload": "usage"}]},
        "logpush_public_key": "public",
    }
