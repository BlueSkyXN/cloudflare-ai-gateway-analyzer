"""Tests for the data layer repositories."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cf_aigw_analyzer.data import AnalyzerDatabase, LogQueryFilters, UsageFields
from cf_aigw_analyzer.data.repository import SyncLockBusy
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


# ---- log_events upsert (raw_json split + metrics) -----------------------------


def test_upsert_logs_stores_event_metrics_and_split_raw(db: AnalyzerDatabase) -> None:
    inserted = db.logs.upsert_many("acct", "gw", [_sample_log()])
    assert inserted == 1

    event_row = db.conn.execute("SELECT * FROM log_events").fetchone()
    assert event_row["model"] == "gpt-test"
    assert event_row["cost_usd"] == 0.0042
    assert event_row["total_ms"] == 2500.0
    assert event_row["latency_ms"] == 400.0
    assert event_row["generation_ms"] == 2100.0
    assert "raw_json" not in event_row

    raw_row = db.conn.execute("SELECT raw_json FROM log_raw").fetchone()
    payload = json.loads(raw_row["raw_json"])
    assert "request" not in payload
    assert "response" not in payload
    assert "Messages" not in payload


def test_upsert_logs_is_idempotent(db: AnalyzerDatabase) -> None:
    db.logs.upsert_many("acct", "gw", [_sample_log()])
    db.logs.upsert_many("acct", "gw", [_sample_log(model="gpt-newer")])
    rows = db.conn.execute("SELECT model FROM log_events").fetchall()
    assert len(rows) == 1
    assert rows[0]["model"] == "gpt-newer"


# ---- usage_targets ------------------------------------------------------------


def test_usage_targets_lists_logs_without_usage(db: AnalyzerDatabase) -> None:
    db.logs.upsert_many("acct", "gw", [_sample_log("a"), _sample_log("b")])
    assert sorted(db.logs.usage_targets("acct", "gw")) == ["a", "b"]


def test_usage_targets_retry_failed_toggles(db: AnalyzerDatabase) -> None:
    db.logs.upsert_many("acct", "gw", [_sample_log("a"), _sample_log("b")])
    db.logs.upsert_usage("acct", "gw", "a", UsageFields(), FetchStatus.FAILED, 500, "boom")

    assert db.logs.usage_targets("acct", "gw", retry_failed=False) == ["b"]
    assert sorted(db.logs.usage_targets("acct", "gw", retry_failed=True)) == ["a", "b"]


def test_usage_targets_missing_only_skips_no_usage(db: AnalyzerDatabase) -> None:
    db.logs.upsert_many("acct", "gw", [_sample_log("a"), _sample_log("b")])
    db.logs.upsert_usage("acct", "gw", "a", UsageFields(), FetchStatus.NO_USAGE, 200, None)

    assert db.logs.usage_targets("acct", "gw", missing_only=True) == ["b"]


def test_usage_targets_missing_only_skips_parsed_usage(db: AnalyzerDatabase) -> None:
    db.logs.upsert_many("acct", "gw", [_sample_log("a")])
    db.logs.upsert_usage(
        "acct",
        "gw",
        "a",
        UsageFields(input_tokens=10, output_tokens=5, total_tokens=15),
        FetchStatus.PARSED,
        200,
        None,
    )
    assert db.logs.usage_targets("acct", "gw", missing_only=True) == []


# ---- query --------------------------------------------------------------------


def test_query_reads_unified_usage_and_metrics(db: AnalyzerDatabase) -> None:
    db.logs.upsert_many("acct", "gw", [_sample_log("a")])
    db.logs.upsert_usage(
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
    assert row["input_tokens"] == 10
    assert row["output_tokens"] == 20
    assert row["total_tokens"] == 30
    assert row["usage_fetch_status"] == "parsed"
    assert row["generation_ms"] == 2100.0
    assert pytest.approx(row["input_tps"], rel=1e-3) == 25.0


def test_query_search_uses_raw_json_table(db: AnalyzerDatabase) -> None:
    db.logs.upsert_many("acct", "gw", [_sample_log("a", model="gpt-magic")])
    filters = LogQueryFilters(account_id="acct", gateway_id="gw", search="gpt-magic")
    assert len(db.logs.query(filters)) == 1
    filters_miss = LogQueryFilters(account_id="acct", gateway_id="gw", search="nothing-like-this")
    assert db.logs.query(filters_miss) == []


# ---- usage backfill ------------------------------------------------------------


def test_upsert_usage_fills_tokens_and_metrics(db: AnalyzerDatabase) -> None:
    db.logs.upsert_many("acct", "gw", [_sample_log("a")])
    db.logs.upsert_usage(
        "acct",
        "gw",
        "a",
        UsageFields(input_tokens=10, output_tokens=21, total_tokens=31, reasoning_tokens=7),
        FetchStatus.PARSED,
        200,
        None,
    )

    row = db.conn.execute("SELECT * FROM log_events WHERE log_id='a'").fetchone()
    assert row["input_tokens"] == 10
    assert row["output_tokens"] == 21
    assert row["total_tokens"] == 31
    assert row["usage_fetch_status"] == "parsed"
    assert pytest.approx(row["input_tps"], rel=1e-3) == 25.0
    assert pytest.approx(row["output_tps"], rel=1e-3) == 10.0
    assert pytest.approx(row["ms_per_output_token"], rel=1e-3) == 100.0
    assert row["visible_output_tokens"] == 14
    assert pytest.approx(row["visible_output_tps"], rel=1e-3) == 14 / 2.1


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


# ---- sync_state / sync_locks --------------------------------------------------


def test_sync_state_records_checkpoint_without_erasing_seen_markers(
    db: AnalyzerDatabase,
) -> None:
    db.sync_state.record_success(
        "acct",
        "gw",
        "sync",
        last_seen_created_at="2026-05-22T01:00:00Z",
        last_seen_log_id="log-1",
    )
    db.sync_state.record_success("acct", "gw", "sync")

    state = db.sync_state.get("acct", "gw", "sync")
    assert state is not None
    assert state["last_success_at"] is not None
    assert state["last_seen_created_at"] == "2026-05-22T01:00:00Z"
    assert state["last_seen_log_id"] == "log-1"


def test_sync_state_checkpoint_only_moves_forward(db: AnalyzerDatabase) -> None:
    db.sync_state.record_success(
        "acct",
        "gw",
        "sync",
        last_seen_created_at="2026-05-22T10:00:00Z",
        last_seen_log_id="log-b",
    )
    db.sync_state.record_success(
        "acct",
        "gw",
        "sync",
        last_seen_created_at="2026-05-22T09:55:00Z",
        last_seen_log_id="log-old",
    )
    db.sync_state.record_success(
        "acct",
        "gw",
        "sync",
        last_seen_created_at="2026-05-22T10:00:00Z",
        last_seen_log_id="log-c",
    )

    state = db.sync_state.get("acct", "gw", "sync")
    assert state is not None
    assert state["last_seen_created_at"] == "2026-05-22T10:00:00Z"
    assert state["last_seen_log_id"] == "log-c"


def test_sync_locks_reject_duplicate_owner_and_release(db: AnalyzerDatabase) -> None:
    db.sync_locks.acquire("acct", "gw", "sync", "owner-a", ttl_seconds=60)
    with pytest.raises(SyncLockBusy):
        db.sync_locks.acquire("acct", "gw", "sync", "owner-b", ttl_seconds=60)

    db.sync_locks.release("acct", "gw", "sync", "owner-a")
    db.sync_locks.acquire("acct", "gw", "sync", "owner-b", ttl_seconds=60)
    assert db.sync_locks.get("acct", "gw", "sync")["owner"] == "owner-b"


# ---- raw lookup ---------------------------------------------------------------


def test_raw_lookup_returns_sanitized_json(db: AnalyzerDatabase) -> None:
    db.logs.upsert_many("acct", "gw", [_sample_log("a")])
    raw = db.logs.get_raw("acct", "gw", "a")
    assert raw is not None
    parsed = json.loads(raw)
    assert "request" not in parsed
    assert parsed["model"] == "gpt-test"
    assert db.logs.get_raw("acct", "gw", "missing") is None


# ---- migrations ---------------------------------------------------------------


def test_migrations_recorded(db: AnalyzerDatabase) -> None:
    versions = [
        row["version"]
        for row in db.conn.execute("SELECT version FROM migrations ORDER BY version").fetchall()
    ]
    assert versions == [5, 6]
    version = db.conn.execute("PRAGMA user_version").fetchone()[0]
    assert version == 6
