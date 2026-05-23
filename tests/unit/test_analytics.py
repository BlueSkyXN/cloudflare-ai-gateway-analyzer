"""Tests for analytics aggregations."""

from __future__ import annotations

from pathlib import Path

import pytest

from cf_aigw_analyzer.analytics import (
    AnalyticsFilters,
    build_context_buckets,
    build_insights,
    build_model_stats,
    build_recent_events,
    build_summary,
    build_timeseries,
    list_gateway_scopes,
)
from cf_aigw_analyzer.data import AnalyzerDatabase, UsageFields
from cf_aigw_analyzer.data.db import open_readonly_connection
from cf_aigw_analyzer.models.enums import FetchStatus


@pytest.fixture
def populated_db(tmp_path: Path) -> Path:
    path = tmp_path / "analytics.sqlite"
    with AnalyzerDatabase(path) as db:
        db.gateways.upsert_many("acct", [{"id": "gw", "name": "main"}])
        db.logs.upsert_many(
            "acct",
            "gw",
            [
                {
                    "id": "small-1",
                    "created_at": "2026-05-22T00:00:00Z",
                    "provider": "openai",
                    "model": "model-fast",
                    "success": True,
                    "tokens_in": 100,
                    "tokens_out": 50,
                    "timings": {"total": 800, "latency": 200},
                },
                {
                    "id": "small-2",
                    "created_at": "2026-05-22T00:30:00Z",
                    "provider": "openai",
                    "model": "model-fast",
                    "success": True,
                    "tokens_in": 200,
                    "tokens_out": 80,
                    "timings": {"total": 1200, "latency": 300},
                },
                {
                    "id": "big-1",
                    "created_at": "2026-05-22T01:10:00Z",
                    "provider": "anthropic",
                    "model": "model-deep",
                    "success": False,
                    "tokens_in": 120_000,
                    "tokens_out": 20,
                    "timings": {"total": 6000, "latency": 1000},
                },
            ],
        )
        db.usage.upsert(
            "acct",
            "gw",
            "small-1",
            UsageFields(input_tokens=100, output_tokens=50, total_tokens=150, cached_tokens=40),
            FetchStatus.PARSED,
            200,
            None,
        )
        db.usage.upsert(
            "acct",
            "gw",
            "small-2",
            UsageFields(input_tokens=200, output_tokens=80, total_tokens=280, cached_tokens=20),
            FetchStatus.PARSED,
            200,
            None,
        )
        db.usage.upsert(
            "acct",
            "gw",
            "big-1",
            UsageFields(input_tokens=120_000, output_tokens=20, total_tokens=120_020),
            FetchStatus.PARSED,
            200,
            None,
        )
    return path


def test_list_gateway_scopes(populated_db: Path) -> None:
    with open_readonly_connection(populated_db) as conn:
        scopes = list_gateway_scopes(conn)
    assert scopes == [
        {
            "account_id": "acct",
            "gateway_id": "gw",
            "name": "main",
            "logs": 3,
            "first_log_at": "2026-05-22T00:00:00Z",
            "last_log_at": "2026-05-22T01:10:00Z",
        }
    ]


def test_summary_aggregates(populated_db: Path) -> None:
    with open_readonly_connection(populated_db) as conn:
        summary = build_summary(conn, AnalyticsFilters(account_id="acct", gateway_id="gw"))

    assert summary["requests"] == 3
    assert summary["success_count"] == 2
    assert summary["failed_count"] == 1
    assert summary["models"] == 2
    assert summary["providers"] == 2
    assert summary["input_tokens"] == 120_300
    assert summary["output_tokens"] == 150
    assert summary["total_tokens"] == 120_450
    assert summary["cached_tokens"] == 60
    assert summary["success_rate"] == pytest.approx(2 / 3, rel=1e-3)
    assert summary["cache_ratio"] == pytest.approx(60 / 120_300, rel=1e-3)
    assert summary["p95_total_ms"] is not None
    assert summary["usage_statuses"]["parsed"] == 3


def test_timeseries_groups_by_hour(populated_db: Path) -> None:
    with open_readonly_connection(populated_db) as conn:
        timeseries = build_timeseries(conn, AnalyticsFilters(account_id="acct", gateway_id="gw"))

    assert [item["hour"] for item in timeseries] == [
        "2026-05-22T00:00:00Z",
        "2026-05-22T01:00:00Z",
    ]
    first = timeseries[0]
    assert first["requests"] == 2
    assert first["rpm"] == pytest.approx(2 / 60, rel=1e-3)


def test_model_stats_ordered_by_requests(populated_db: Path) -> None:
    with open_readonly_connection(populated_db) as conn:
        models = build_model_stats(conn, AnalyticsFilters(account_id="acct", gateway_id="gw"))

    assert [item["model"] for item in models] == ["model-fast", "model-deep"]
    fast = models[0]
    assert fast["requests"] == 2
    assert fast["success_rate"] == 1.0
    assert fast["cache_ratio"] == pytest.approx(60 / 300, rel=1e-3)
    assert fast["providers"] == ["openai"]


def test_context_buckets(populated_db: Path) -> None:
    with open_readonly_connection(populated_db) as conn:
        buckets = build_context_buckets(conn, AnalyticsFilters(account_id="acct", gateway_id="gw"))

    labels = [item["context_bucket"] for item in buckets]
    assert "<1k" in labels
    assert "100k-500k" in labels


def test_recent_events_capped_to_limit(populated_db: Path) -> None:
    with open_readonly_connection(populated_db) as conn:
        events = build_recent_events(
            conn,
            AnalyticsFilters(account_id="acct", gateway_id="gw"),
            limit=2,
        )
    assert len(events) == 2
    assert events[0]["log_id"] == "big-1"
    assert "raw_json" not in events[0]


def test_insights_basic(populated_db: Path) -> None:
    with open_readonly_connection(populated_db) as conn:
        insights = build_insights(conn, AnalyticsFilters(account_id="acct", gateway_id="gw"))
    titles = [item["title"] for item in insights]
    assert "主力模型" in titles
    assert "请求峰值时段" in titles


def test_summary_empty_when_no_data(tmp_path: Path) -> None:
    path = tmp_path / "empty.sqlite"
    with AnalyzerDatabase(path):
        pass
    with open_readonly_connection(path) as conn:
        summary = build_summary(conn, AnalyticsFilters())
    assert summary["requests"] == 0
    assert summary["total_tokens"] == 0
