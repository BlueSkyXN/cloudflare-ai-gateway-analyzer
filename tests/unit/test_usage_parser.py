"""Tests for the multi-provider usage parser."""

from __future__ import annotations

from cf_aigw_analyzer.core.usage_parser import parse_usage_from_response


def test_openai_usage_with_details() -> None:
    usage = parse_usage_from_response(
        {
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 7,
                "total_tokens": 17,
                "prompt_tokens_details": {"cached_tokens": 4},
                "completion_tokens_details": {"reasoning_tokens": 2},
            }
        }
    )

    assert usage.input_tokens == 10
    assert usage.output_tokens == 7
    assert usage.total_tokens == 17
    assert usage.cached_tokens == 4
    assert usage.reasoning_tokens == 2
    assert usage.has_numeric_data is True


def test_anthropic_usage_with_cache() -> None:
    usage = parse_usage_from_response(
        {
            "usage": {
                "input_tokens": 100,
                "output_tokens": 20,
                "cache_read_input_tokens": 30,
                "cache_creation_input_tokens": 5,
            }
        }
    )

    assert usage.input_tokens == 100
    assert usage.output_tokens == 20
    assert usage.total_tokens == 120
    assert usage.cached_tokens == 30
    assert usage.cache_write_tokens == 5


def test_gemini_usage_metadata() -> None:
    usage = parse_usage_from_response(
        {
            "usageMetadata": {
                "promptTokenCount": 8,
                "candidatesTokenCount": 12,
                "totalTokenCount": 20,
                "cachedContentTokenCount": 3,
                "thoughtsTokenCount": 6,
            }
        }
    )

    assert usage.input_tokens == 8
    assert usage.output_tokens == 12
    assert usage.total_tokens == 20
    assert usage.cached_tokens == 3
    assert usage.reasoning_tokens == 6


def test_sse_format_extracts_terminal_usage() -> None:
    usage = parse_usage_from_response(
        'data: {"choices":[{"delta":{"content":"x"}}]}\n\n'
        'data: {"usage":{"prompt_tokens":2,"completion_tokens":3}}\n\n'
        "data: [DONE]\n"
    )
    assert usage.input_tokens == 2
    assert usage.output_tokens == 3
    assert usage.total_tokens == 5


def test_cloudflare_wrapped_json_string_result() -> None:
    usage = parse_usage_from_response(
        {
            "success": True,
            "result": '{"usage":{"input_tokens":15,"output_tokens":5,"total_tokens":20}}',
        }
    )
    assert usage.input_tokens == 15
    assert usage.output_tokens == 5
    assert usage.total_tokens == 20


def test_empty_payload_returns_empty_fields() -> None:
    usage = parse_usage_from_response(None)
    assert usage.has_numeric_data is False
    usage = parse_usage_from_response({"foo": "bar"})
    assert usage.has_numeric_data is False


def test_multiple_candidates_pick_highest_score() -> None:
    """When several ``usage`` objects appear, choose the one with most token info."""

    usage = parse_usage_from_response(
        {
            "usage": {"prompt_tokens": 0, "completion_tokens": 0},
            "result": {"usage": {"prompt_tokens": 50, "completion_tokens": 25, "total_tokens": 75}},
        }
    )
    assert usage.input_tokens == 50
    assert usage.output_tokens == 25
    assert usage.total_tokens == 75


def test_derive_missing_total_from_components() -> None:
    usage = parse_usage_from_response({"usage": {"input_tokens": 7, "output_tokens": 3}})
    assert usage.total_tokens == 10


def test_derive_missing_output_from_total_and_input() -> None:
    usage = parse_usage_from_response({"usage": {"input_tokens": 10, "total_tokens": 15}})
    assert usage.output_tokens == 5
