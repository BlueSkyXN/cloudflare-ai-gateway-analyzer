"""Tests for analytics aggregations."""

from __future__ import annotations

from pathlib import Path

import pytest

from cf_aigw_analyzer.analytics import AnalyticsFilters, build_analytics, list_gateway_scopes
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
        db.logs.upsert_usage(
            "acct",
            "gw",
            "small-1",
            UsageFields(input_tokens=100, output_tokens=50, total_tokens=150, cached_tokens=40),
            FetchStatus.PARSED,
            200,
            None,
        )
        db.logs.upsert_usage(
            "acct",
            "gw",
            "small-2",
            UsageFields(input_tokens=200, output_tokens=80, total_tokens=280, cached_tokens=20),
            FetchStatus.PARSED,
            200,
            None,
        )
        db.logs.upsert_usage(
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


def test_unified_analytics_payload(populated_db: Path) -> None:
    with open_readonly_connection(populated_db) as conn:
        payload = build_analytics(
            conn, AnalyticsFilters(account_id="acct", gateway_id="gw"), limit=2
        )

    summary = payload["summary"]
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
    assert summary["avg_input_tps"] == pytest.approx((500 + (200 / 0.3) + 120_000) / 3)
    assert summary["p95_total_ms"] is not None
    assert summary["usage_statuses"]["parsed"] == 3

    assert [item["hour"] for item in payload["timeseries"]] == [
        "2026-05-22T00:00:00Z",
        "2026-05-22T01:00:00Z",
    ]
    assert payload["timeseries"][0]["requests"] == 2
    assert payload["timeseries"][0]["rpm"] == pytest.approx(2 / 60, rel=1e-3)
    assert payload["timeseries"][0]["avg_input_tps"] == pytest.approx((500 + (200 / 0.3)) / 2)

    assert [item["model"] for item in payload["by_model"]] == ["model-fast", "model-deep"]
    fast = payload["by_model"][0]
    assert fast["requests"] == 2
    assert fast["success_rate"] == 1.0
    assert fast["cache_ratio"] == pytest.approx(60 / 300, rel=1e-3)
    assert fast["avg_input_tps"] == pytest.approx((500 + (200 / 0.3)) / 2)
    assert fast["providers"] == ["openai"]

    assert payload["filter_options"]["providers"] == [
        {"provider": "openai", "requests": 2},
        {"provider": "anthropic", "requests": 1},
    ]
    assert payload["filter_options"]["models"][0] == {
        "model": "model-fast",
        "providers": ["openai"],
        "requests": 2,
    }

    assert len(payload["events"]) == 2
    assert payload["events"][0]["log_id"] == "big-1"
    assert payload["events"][0]["input_tps"] == pytest.approx(120_000)
    assert "raw_json" not in payload["events"][0]


def test_analytics_supports_custom_timeseries_buckets(populated_db: Path) -> None:
    with open_readonly_connection(populated_db) as conn:
        payload = build_analytics(
            conn,
            AnalyticsFilters(account_id="acct", gateway_id="gw", timeseries_bucket_hours=4),
            limit=2,
        )

    assert [item["hour"] for item in payload["timeseries"]] == ["2026-05-22T00:00:00Z"]
    assert payload["timeseries"][0]["requests"] == 3
    assert payload["timeseries"][0]["rpm"] == pytest.approx(3 / 240, rel=1e-3)


def test_analytics_time_filters_include_iso_millisecond_boundaries(populated_db: Path) -> None:
    with open_readonly_connection(populated_db) as conn:
        payload = build_analytics(
            conn,
            AnalyticsFilters(
                account_id="acct",
                gateway_id="gw",
                start_date="2026-05-22T00:30:00.000Z",
                end_date="2026-05-22T01:10:00.000Z",
            ),
            limit=10,
        )

    assert payload["summary"]["requests"] == 2
    assert payload["summary"]["first_log_at"] == "2026-05-22T00:30:00Z"
    assert payload["summary"]["last_log_at"] == "2026-05-22T01:10:00Z"
    assert [event["log_id"] for event in payload["events"]] == ["big-1", "small-2"]


def test_summary_empty_when_no_data(tmp_path: Path) -> None:
    path = tmp_path / "empty.sqlite"
    with AnalyzerDatabase(path):
        pass
    with open_readonly_connection(path) as conn:
        payload = build_analytics(conn, AnalyticsFilters())
    assert payload["summary"]["requests"] == 0
    assert payload["summary"]["total_tokens"] == 0
