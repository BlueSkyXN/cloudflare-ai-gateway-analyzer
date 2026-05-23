"""Tests for the data layer repositories."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cf_aigw_analyzer.data import AnalyzerDatabase, LogQueryFilters, UsageFields
from cf_aigw_analyzer.models.enums import FetchStatus


@pytest.fixture
def db(tmp_path: Path) -> AnalyzerDatabase:
    path = tmp_path / "analyzer.sqlite"
    instance = AnalyzerDatabase(path)
    yield instance
    instance.close()


def _sample_log(log_id: str = "log-1", **overrides) -> dict:
    base = {
        "id": log_id,
        "created_at": "2026-05-22T00:00:00Z",
        "provider": "openai",
        "model": "gpt-test",
        "model_type": "chat",
        "success": True,
        "cached": False,
        "status_code": 200,
        "cost": 0.0042,
        "tokens_in": 0,
        "tokens_out": None,
        "duration": 1500.0,
        "timings": {"total": 2500.0, "latency": 400.0},
        "request": {"messages": ["do not store this"]},
        "response": {"text": "should be scrubbed"},
        "Messages": [{"content": "also private"}],
    }
    base.update(overrides)
    return base


# ---- gateways -----------------------------------------------------------------


def test_upsert_and_resolve_gateway(db: AnalyzerDatabase) -> None:
    n = db.gateways.upsert_many("acct", [{"id": "gw-1", "name": "primary", "collect_logs": True}])
    assert n == 1
    assert db.gateways.resolve_gateway_id("acct", "primary") == "gw-1"
    assert db.gateways.resolve_gateway_id("acct", "gw-1") == "gw-1"
    assert db.gateways.resolve_gateway_id("acct", "missing") is None


def test_gateway_upsert_is_idempotent(db: AnalyzerDatabase) -> None:
    db.gateways.upsert_many("acct", [{"id": "gw-1", "name": "old"}])
    db.gateways.upsert_many("acct", [{"id": "gw-1", "name": "new", "collect_logs": True}])

    listing = db.gateways.list_for_account("acct")
    assert len(listing) == 1
    assert listing[0]["name"] == "new"
    assert listing[0]["collect_logs"] == 1


# ---- logs upsert (raw_json split + metrics) -----------------------------------


def test_upsert_logs_stores_metadata_metrics_and_split_raw(db: AnalyzerDatabase) -> None:
    inserted = db.logs.upsert_many("acct", "gw", [_sample_log()])
    assert inserted == 1

    log_row = db.conn.execute("SELECT * FROM logs").fetchone()
    assert log_row["model"] == "gpt-test"
    assert log_row["cost_usd"] == 0.0042
    assert "raw_json" not in log_row  # raw_json moved to logs_raw

    raw_row = db.conn.execute("SELECT raw_json FROM logs_raw").fetchone()
    payload = json.loads(raw_row["raw_json"])
    assert "request" not in payload
    assert "response" not in payload
    assert "Messages" not in payload

    metrics_row = db.conn.execute("SELECT * FROM log_metrics").fetchone()
    assert metrics_row["total_ms"] == 2500.0
    assert metrics_row["latency_ms"] == 400.0
    assert metrics_row["generation_ms"] == 2100.0


def test_upsert_logs_is_idempotent(db: AnalyzerDatabase) -> None:
    db.logs.upsert_many("acct", "gw", [_sample_log()])
    db.logs.upsert_many("acct", "gw", [_sample_log(model="gpt-newer")])
    rows = db.conn.execute("SELECT model FROM logs").fetchall()
    assert len(rows) == 1
    assert rows[0]["model"] == "gpt-newer"


# ---- usage_targets ------------------------------------------------------------


def test_usage_targets_lists_logs_without_usage(db: AnalyzerDatabase) -> None:
    db.logs.upsert_many("acct", "gw", [_sample_log("a"), _sample_log("b")])
    assert sorted(db.logs.usage_targets("acct", "gw")) == ["a", "b"]


def test_usage_targets_retry_failed_toggles(db: AnalyzerDatabase) -> None:
    db.logs.upsert_many("acct", "gw", [_sample_log("a"), _sample_log("b")])
    db.usage.upsert("acct", "gw", "a", UsageFields(), FetchStatus.FAILED, 500, "boom")

    assert db.logs.usage_targets("acct", "gw", retry_failed=False) == ["b"]
    assert sorted(db.logs.usage_targets("acct", "gw", retry_failed=True)) == ["a", "b"]


def test_usage_targets_missing_only_skips_no_usage(db: AnalyzerDatabase) -> None:
    db.logs.upsert_many("acct", "gw", [_sample_log("a"), _sample_log("b")])
    db.usage.upsert("acct", "gw", "a", UsageFields(), FetchStatus.NO_USAGE, 200, None)

    assert db.logs.usage_targets("acct", "gw", missing_only=True) == ["b"]


def test_usage_targets_missing_only_includes_parsed_with_zero_tokens(db: AnalyzerDatabase) -> None:
    """When usage is parsed but logs.tokens_* is still 0/NULL, the row is a backfill target."""

    db.logs.upsert_many("acct", "gw", [_sample_log("a")])  # tokens_in=0, tokens_out=NULL
    db.usage.upsert(
        "acct",
        "gw",
        "a",
        UsageFields(input_tokens=10, output_tokens=5, total_tokens=15),
        FetchStatus.PARSED,
        200,
        None,
    )
    assert db.logs.usage_targets("acct", "gw", missing_only=True) == ["a"]

    # After we propagate usage back into the logs table, the row is excluded.
    db.logs.update_tokens_from_usage("acct", "gw", "a", 10, 5)
    assert db.logs.usage_targets("acct", "gw", missing_only=True) == []


# ---- query --------------------------------------------------------------------


def test_query_joins_usage_and_metrics(db: AnalyzerDatabase) -> None:
    db.logs.upsert_many("acct", "gw", [_sample_log("a")])
    db.usage.upsert(
        "acct",
        "gw",
        "a",
        UsageFields(input_tokens=10, output_tokens=20, total_tokens=30, source="usage"),
        FetchStatus.PARSED,
        200,
        None,
    )
    rows = db.logs.query(LogQueryFilters(account_id="acct", gateway_id="gw"))
    assert len(rows) == 1
    row = rows[0]
    assert row["usage_input_tokens"] == 10
    assert row["usage_output_tokens"] == 20
    assert row["generation_ms"] == 2100.0


def test_query_search_uses_raw_json_table(db: AnalyzerDatabase) -> None:
    db.logs.upsert_many("acct", "gw", [_sample_log("a", model="gpt-magic")])
    filters = LogQueryFilters(account_id="acct", gateway_id="gw", search="gpt-magic")
    assert len(db.logs.query(filters)) == 1
    filters_miss = LogQueryFilters(account_id="acct", gateway_id="gw", search="nothing-like-this")
    assert db.logs.query(filters_miss) == []


# ---- token backfill -----------------------------------------------------------


def test_update_tokens_from_usage_fills_zeros(db: AnalyzerDatabase) -> None:
    db.logs.upsert_many("acct", "gw", [_sample_log("a")])  # tokens_in=0, tokens_out=None
    db.logs.update_tokens_from_usage("acct", "gw", "a", 11, 9)
    row = db.conn.execute("SELECT tokens_in, tokens_out FROM logs").fetchone()
    assert row["tokens_in"] == 11
    assert row["tokens_out"] == 9


# ---- summary ------------------------------------------------------------------


def test_summary_by_scope(db: AnalyzerDatabase) -> None:
    db.logs.upsert_many("acct", "gw-a", [_sample_log("a1"), _sample_log("a2")])
    db.logs.upsert_many("acct", "gw-b", [_sample_log("b1")])
    assert db.logs.summary("acct", "gw-a")["total_logs"] == 2
    assert db.logs.summary("acct", "gw-b")["total_logs"] == 1
    assert db.logs.summary("acct")["total_logs"] == 3


# ---- sync_runs ----------------------------------------------------------------


def test_record_and_list_sync_runs(db: AnalyzerDatabase) -> None:
    run_id = db.sync_runs.record(
        "acct", "gw", "sync", {"limit": 100}, logs_count=42, started_at="2026-05-22T01:00:00Z"
    )
    assert run_id > 0
    recent = db.sync_runs.list_recent("acct", "gw")
    assert recent[0]["logs_count"] == 42
    assert db.sync_runs.get(run_id)["mode"] == "sync"


# ---- metrics refresh ----------------------------------------------------------


def test_refresh_usage_dependent_metrics_fills_tps(db: AnalyzerDatabase) -> None:
    db.logs.upsert_many("acct", "gw", [_sample_log("a")])
    db.logs.update_tokens_from_usage("acct", "gw", "a", None, 21)  # tokens_out=21
    db.metrics.refresh_usage_dependent(
        "acct",
        "gw",
        "a",
        UsageFields(input_tokens=10, output_tokens=21, total_tokens=31, reasoning_tokens=7),
    )

    row = db.conn.execute("SELECT * FROM log_metrics WHERE log_id='a'").fetchone()
    # generation_ms is 2100, output_tokens=21 → 10 tps
    assert pytest.approx(row["output_tps"], rel=1e-3) == 10.0
    assert pytest.approx(row["ms_per_output_token"], rel=1e-3) == 100.0
    assert row["visible_output_tokens"] == 14
    assert pytest.approx(row["visible_output_tps"], rel=1e-3) == 14 / 2.1


# ---- raw lookup ---------------------------------------------------------------


def test_raw_lookup_returns_sanitized_json(db: AnalyzerDatabase) -> None:
    db.logs.upsert_many("acct", "gw", [_sample_log("a")])
    raw = db.raw.get("acct", "gw", "a")
    assert raw is not None
    parsed = json.loads(raw)
    assert "request" not in parsed
    assert parsed["model"] == "gpt-test"
    assert db.raw.get("acct", "gw", "missing") is None


# ---- migrations ---------------------------------------------------------------


def test_migrations_recorded(db: AnalyzerDatabase) -> None:
    versions = [
        row["version"]
        for row in db.conn.execute("SELECT version FROM migrations ORDER BY version").fetchall()
    ]
    assert versions == [3]
    version = db.conn.execute("PRAGMA user_version").fetchone()[0]
    assert version == 3
