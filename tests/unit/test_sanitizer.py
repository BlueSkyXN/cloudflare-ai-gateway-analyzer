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
        "requestBody": "secret",
        "payload": {"conversation": "secret"},
        "metadata": '{"messages":["secret"]}',
        "_request_content": "raw",
        "timings": {
            "total": 1000,
            "latency": 100,
            "generation": "not-a-number",
            "message": "drop",
            "unknown": "drop",
        },
    }
    cleaned = sanitize_log_metadata(payload)

    assert cleaned == {
        "id": "log-1",
        "model": "gpt-test",
        "timings": {"total": 1000, "latency": 100},
    }


def test_lists_are_walked() -> None:
    payload = {
        "events": [
            {"text": "drop", "type": "info"},
            {"type": "error", "details": {"message": "drop"}},
        ]
    }
    cleaned = sanitize_log_metadata(payload)
    assert cleaned == {}


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
        "oauth": {
            "clientSecret": "secret",
            "access_token": "secret",
            "credentials": {"username": "user", "password": "secret"},
        },
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
        "oauth": {
            "clientSecret": REDACTED,
            "access_token": REDACTED,
            "credentials": REDACTED,
        },
        "logpush_public_key": "public",
    }
