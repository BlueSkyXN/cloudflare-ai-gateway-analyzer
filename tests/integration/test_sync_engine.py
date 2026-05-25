"""Integration tests for SyncEngine end-to-end with mocked Cloudflare."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
from pydantic import SecretStr

from cf_aigw_analyzer.config.settings import CloudflareConfig, Settings, SyncConfig
from cf_aigw_analyzer.core.cloudflare import CloudflareClient, LogFilters
from cf_aigw_analyzer.core.http_client import HttpClient
from cf_aigw_analyzer.core.sync_engine import SyncEngine
from cf_aigw_analyzer.data.db import AnalyzerDatabase
from cf_aigw_analyzer.data.repository import SyncLockBusy


@pytest.fixture
def db(tmp_path: Path) -> AnalyzerDatabase:
    instance = AnalyzerDatabase(tmp_path / "engine.sqlite")
    yield instance
    instance.close()


def _make_settings(**overrides) -> Settings:
    base = Settings(
        cloudflare=CloudflareConfig(api_token=SecretStr("tok-test"), retries=2),
        sync=SyncConfig(per_page=2, log_throttle_ms=0, usage_workers=2, usage_batch_size=2),
    )
    return base.model_copy(update=overrides) if overrides else base


def _mock_client(handler) -> CloudflareClient:
    transport = httpx.MockTransport(handler)
    inner = httpx.AsyncClient(base_url="https://api.cloudflare.com/client/v4", transport=transport)
    http = HttpClient(
        base_url="https://api.cloudflare.com/client/v4",
        headers={"Authorization": "Bearer tok-test"},
        retries=2,
        client=inner,
    )
    return CloudflareClient(
        CloudflareConfig(api_token=SecretStr("tok-test")),
        http=http,
    )


@pytest.mark.asyncio
async def test_sync_logs_paginates_and_persists(db: AnalyzerDatabase) -> None:
    pages = {
        "1": {
            "success": True,
            "result_info": {"total_count": 3},
            "result": [
                {"id": "log-1", "model": "gpt-4o-mini", "tokens_in": 100, "tokens_out": 50},
                {"id": "log-2", "model": "gpt-4o", "tokens_in": 200, "tokens_out": 80},
            ],
        },
        "2": {
            "success": True,
            "result_info": {"total_count": 3},
            "result": [{"id": "log-3", "model": "gpt-4o", "tokens_in": 30, "tokens_out": 20}],
        },
    }

    def handler(request: httpx.Request) -> httpx.Response:
        page = request.url.params.get("page", "1")
        return httpx.Response(200, json=pages[page])

    settings = _make_settings()
    async with _mock_client(handler) as client:
        engine = SyncEngine(settings, db, client=client)
        result = await engine.sync_logs(
            "acct",
            "gw",
            LogFilters(per_page=2),
        )
    assert result.logs_count == 3
    stored = db.conn.execute("SELECT log_id FROM log_events ORDER BY log_id").fetchall()
    assert [row["log_id"] for row in stored] == ["log-1", "log-2", "log-3"]
    state = db.sync_state.get("acct", "gw", "sync")
    assert state is not None
    assert state["last_success_at"] is not None


@pytest.mark.asyncio
async def test_incremental_sync_uses_checkpoint_overlap(db: AnalyzerDatabase) -> None:
    db.sync_state.record_success(
        "acct",
        "gw",
        "sync",
        last_seen_created_at="2026-05-22T10:00:00Z",
        last_seen_log_id="log-old",
    )
    seen_start_dates: list[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_start_dates.append(request.url.params.get("start_date"))
        return httpx.Response(
            200, json={"success": True, "result_info": {"total_count": 0}, "result": []}
        )

    settings = _make_settings()
    async with _mock_client(handler) as client:
        engine = SyncEngine(settings, db, client=client)
        await engine.sync_logs("acct", "gw", LogFilters(per_page=2), incremental=True)

    assert seen_start_dates == ["2026-05-22T09:50:00Z"]
    runs = db.sync_runs.list_recent("acct", "gw")
    params = json.loads(runs[0]["params_json"])
    assert params["incremental"] is True
    assert params["start_date"] == "2026-05-22T09:50:00Z"


@pytest.mark.asyncio
async def test_sync_logs_rejects_existing_lock(db: AnalyzerDatabase) -> None:
    db.sync_locks.acquire("acct", "gw", "sync", "already-running", ttl_seconds=60)

    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("locked sync must not call upstream")

    settings = _make_settings()
    async with _mock_client(handler) as client:
        engine = SyncEngine(settings, db, client=client)
        with pytest.raises(SyncLockBusy):
            await engine.sync_logs("acct", "gw", LogFilters(per_page=2))


@pytest.mark.asyncio
async def test_sync_usage_classifies_responses(db: AnalyzerDatabase) -> None:
    # Seed 3 logs without usage
    db.logs.upsert_many(
        "acct",
        "gw",
        [
            {"id": "log-a"},
            {"id": "log-b"},
            {"id": "log-c"},
        ],
    )

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/log-a/response"):
            return httpx.Response(
                200, json={"usage": {"prompt_tokens": 10, "completion_tokens": 5}}
            )
        if path.endswith("/log-b/response"):
            return httpx.Response(404, json={"success": False, "errors": [{"message": "no body"}]})
        if path.endswith("/log-c/response"):
            return httpx.Response(500, text="boom")
        raise AssertionError(f"unexpected path: {path}")

    settings = _make_settings()
    async with _mock_client(handler) as client:
        engine = SyncEngine(settings, db, client=client)
        result = await engine.sync_usage("acct", "gw", retry_failed=True)

    assert result.targets == 3
    assert result.parsed == 1
    assert result.no_usage == 1
    assert result.failed == 1

    usage_rows = {
        row["log_id"]: row for row in db.conn.execute("SELECT * FROM log_events").fetchall()
    }
    assert usage_rows["log-a"]["usage_fetch_status"] == "parsed"
    assert usage_rows["log-a"]["input_tokens"] == 10
    assert usage_rows["log-b"]["usage_fetch_status"] == "no_usage"
    assert usage_rows["log-c"]["usage_fetch_status"] == "failed"

    # tokens_in/out backfilled
    log_a = db.conn.execute(
        "SELECT input_tokens, output_tokens FROM log_events WHERE log_id='log-a'"
    ).fetchone()
    assert log_a["input_tokens"] == 10
    assert log_a["output_tokens"] == 5


@pytest.mark.asyncio
async def test_sync_usage_records_run_even_when_no_targets(db: AnalyzerDatabase) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("should not call upstream when no targets")

    settings = _make_settings()
    async with _mock_client(handler) as client:
        engine = SyncEngine(settings, db, client=client)
        result = await engine.sync_usage("acct", "gw")
    assert result.targets == 0
    assert result.run_id is not None
    runs = db.sync_runs.list_recent("acct", "gw")
    assert runs and runs[0]["mode"] == "sync-usage"


@pytest.mark.asyncio
async def test_parsed_with_zero_tokens_treated_as_no_usage(db: AnalyzerDatabase) -> None:
    db.logs.upsert_many("acct", "gw", [{"id": "log-x"}])

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"id": "log-x", "result": "no usage object here"})

    settings = _make_settings()
    async with _mock_client(handler) as client:
        engine = SyncEngine(settings, db, client=client)
        result = await engine.sync_usage("acct", "gw")
    assert result.no_usage == 1
    row = db.conn.execute(
        "SELECT usage_fetch_status FROM log_events WHERE log_id='log-x'"
    ).fetchone()
    assert row["usage_fetch_status"] == "no_usage"


@pytest.mark.asyncio
async def test_sync_logs_records_run_with_filter_params(db: AnalyzerDatabase) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"success": True, "result_info": {"total_count": 0}, "result": []}
        )

    settings = _make_settings()
    async with _mock_client(handler) as client:
        engine = SyncEngine(settings, db, client=client)
        await engine.sync_logs("acct", "gw", LogFilters(model="gpt-4o", per_page=2), limit=5)

    runs = db.sync_runs.list_recent("acct", "gw")
    assert runs
    params = json.loads(runs[0]["params_json"])
    assert params["model"] == "gpt-4o"
    assert params["limit"] == 5
