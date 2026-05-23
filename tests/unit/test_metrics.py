"""Tests for log metrics computation."""

from __future__ import annotations

import pytest

from cf_aigw_analyzer.core.metrics import compute_log_metrics


def test_full_metric_chain_from_timings() -> None:
    metrics = compute_log_metrics(
        {
            "duration": 1500.0,
            "timings": {"total": 2500.0, "latency": 400.0},
            "tokens_out": 21,
            "_reasoning_tokens": 7,
        }
    )
    assert metrics.total_ms == 2500.0
    assert metrics.latency_ms == 400.0
    assert metrics.generation_ms == 2100.0
    assert pytest.approx(metrics.output_tps, rel=1e-3) == 10.0
    assert pytest.approx(metrics.ms_per_output_token, rel=1e-3) == 100.0
    assert metrics.visible_output_tokens == 14
    assert pytest.approx(metrics.visible_output_tps, rel=1e-3) == 14 / 2.1


def test_zero_generation_ms_skips_tps() -> None:
    metrics = compute_log_metrics(
        {"timings": {"total": 500.0, "latency": 500.0}, "tokens_out": 100}
    )
    assert metrics.generation_ms == 0.0
    assert metrics.output_tps is None
    assert metrics.ms_per_output_token is None


def test_missing_timings_falls_back_to_duration() -> None:
    metrics = compute_log_metrics({"duration": 800.0})
    assert metrics.total_ms == 800.0
    assert metrics.latency_ms is None
    assert metrics.generation_ms is None


def test_handles_string_numeric_fields() -> None:
    metrics = compute_log_metrics(
        {"timings": {"total": "1000", "latency": "100"}, "tokens_out": "10"}
    )
    assert metrics.total_ms == 1000.0
    assert metrics.latency_ms == 100.0
    assert metrics.generation_ms == 900.0
    assert pytest.approx(metrics.output_tps, rel=1e-3) == 10 / 0.9


def test_explicit_overrides_win() -> None:
    metrics = compute_log_metrics(
        {
            "_total_ms": 3000,
            "_latency_ms": 500,
            "_generation_ms": 2500,
            "_output_tps": 7.5,
            "tokens_out": 25,
        }
    )
    assert metrics.total_ms == 3000.0
    assert metrics.latency_ms == 500.0
    assert metrics.generation_ms == 2500.0
    assert metrics.output_tps == 7.5
    assert metrics.ms_per_output_token == 100.0
