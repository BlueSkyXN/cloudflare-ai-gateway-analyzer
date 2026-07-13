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
from cf_aigw_analyzer.data.models import UsageFields
from cf_aigw_analyzer.data.repository import SyncLockBusy
from cf_aigw_analyzer.models.enums import FetchStatus


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
    seen_queries: list[dict[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_queries.append(dict(request.url.params))
        return httpx.Response(
            200, json={"success": True, "result_info": {"total_count": 0}, "result": []}
        )

    settings = _make_settings()
    async with _mock_client(handler) as client:
        engine = SyncEngine(settings, db, client=client)
        await engine.sync_logs("acct", "gw", LogFilters(per_page=2), incremental=True)

    assert seen_queries == [
        {
            "page": "1",
            "per_page": "2",
            "order_by": "created_at",
            "order_by_direction": "asc",
            "start_date": "2026-05-22T09:50:00Z",
        }
    ]
    runs = db.sync_runs.list_recent("acct", "gw")
    params = json.loads(runs[0]["params_json"])
    assert params["incremental"] is True
    assert params["start_date"] == "2026-05-22T09:50:00Z"


@pytest.mark.asyncio
async def test_sync_logs_checkpoint_ignores_invalid_created_at_and_normalizes_utc(
    db: AnalyzerDatabase,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "success": True,
                "result_info": {"total_count": 2},
                "result": [
                    {"id": "valid", "created_at": "2026-07-01T08:00:00+08:00"},
                    {"id": "invalid", "created_at": "unknown"},
                ],
            },
        )

    settings = _make_settings()
    async with _mock_client(handler) as client:
        engine = SyncEngine(settings, db, client=client)
        result = await engine.sync_logs("acct", "gw", LogFilters(per_page=2))

    assert result.logs_count == 2
    state = db.sync_state.get("acct", "gw", "sync")
    assert state is not None
    assert state["last_seen_created_at"] == "2026-07-01T00:00:00Z"
    assert state["last_seen_log_id"] == "valid"


@pytest.mark.asyncio
async def test_sync_logs_checkpoint_only_uses_persisted_rows(db: AnalyzerDatabase) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "success": True,
                "result_info": {"total_count": 6},
                "result": [
                    {"id": "persisted-a", "created_at": "2026-07-01T00:00:00Z"},
                    {
                        "id": None,
                        "log_id": "persisted-z",
                        "created_at": "2026-07-01T00:00:00Z",
                    },
                    {
                        "id": "",
                        "log_id": "persisted-y",
                        "created_at": "2026-07-01T00:00:00Z",
                    },
                    {"created_at": "2099-01-01T00:00:00Z"},
                    {"id": None, "created_at": "2099-01-02T00:00:00Z"},
                    {"id": "", "created_at": "2099-01-03T00:00:00Z"},
                ],
            },
        )

    settings = _make_settings()
    async with _mock_client(handler) as client:
        engine = SyncEngine(settings, db, client=client)
        result = await engine.sync_logs("acct", "gw", LogFilters(per_page=10))

    assert result.logs_count == 3
    stored = db.conn.execute("SELECT log_id FROM log_events ORDER BY log_id").fetchall()
    assert [row["log_id"] for row in stored] == [
        "persisted-a",
        "persisted-y",
        "persisted-z",
    ]
    state = db.sync_state.get("acct", "gw", "sync")
    assert state is not None
    assert state["last_seen_created_at"] == "2026-07-01T00:00:00Z"
    assert state["last_seen_log_id"] == "persisted-z"
    runs = db.sync_runs.list_recent("acct", "gw")
    assert runs[0]["logs_count"] == 3


@pytest.mark.asyncio
async def test_invalid_incremental_checkpoint_fails_before_upstream_and_full_sync_repairs_it(
    db: AnalyzerDatabase,
) -> None:
    db.conn.execute(
        """
        INSERT INTO sync_state (
            account_id, gateway_id, mode, last_success_at,
            last_seen_created_at, last_seen_log_id, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "acct",
            "gw",
            "sync",
            "2026-07-01T00:00:00Z",
            "unknown",
            "bad",
            "2026-07-01T00:00:00Z",
        ),
    )
    seen_queries: list[dict[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_queries.append(dict(request.url.params))
        return httpx.Response(
            200,
            json={
                "success": True,
                "result_info": {"total_count": 1},
                "result": [{"id": "valid", "created_at": "2026-07-01T08:00:00+08:00"}],
            },
        )

    settings = _make_settings()
    async with _mock_client(handler) as client:
        engine = SyncEngine(settings, db, client=client)
        with pytest.raises(ValueError, match="invalid incremental checkpoint"):
            await engine.sync_logs("acct", "gw", LogFilters(per_page=2), incremental=True)
        assert seen_queries == []

        result = await engine.sync_logs("acct", "gw", LogFilters(per_page=2))

    assert result.logs_count == 1
    assert len(seen_queries) == 1
    state = db.sync_state.get("acct", "gw", "sync")
    assert state is not None
    assert state["last_seen_created_at"] == "2026-07-01T00:00:00Z"
    assert state["last_seen_log_id"] == "valid"


@pytest.mark.asyncio
async def test_incremental_sync_rejects_limit(db: AnalyzerDatabase) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("unsafe incremental+limit must fail before calling upstream")

    settings = _make_settings()
    async with _mock_client(handler) as client:
        engine = SyncEngine(settings, db, client=client)
        with pytest.raises(ValueError, match="cannot be combined with limit"):
            await engine.sync_logs(
                "acct",
                "gw",
                LogFilters(per_page=2),
                incremental=True,
                limit=10,
            )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "filter_overrides",
    [
        pytest.param({"page": 2}, id="page"),
        pytest.param({"model": "gpt-4o"}, id="model"),
        pytest.param({"provider": "openai"}, id="provider"),
        pytest.param({"model_type": "chat"}, id="model-type"),
        pytest.param({"search": "needle"}, id="search"),
        pytest.param({"cached": False}, id="cached-false"),
        pytest.param({"success": False}, id="success-false"),
        pytest.param({"feedback": 0}, id="feedback-zero"),
        pytest.param({"min_cost": 0.0}, id="min-cost-zero"),
        pytest.param({"max_cost": 1.0}, id="max-cost"),
        pytest.param({"min_duration": 0.0}, id="min-duration-zero"),
        pytest.param({"max_duration": 1.0}, id="max-duration"),
        pytest.param({"min_tokens_in": 0}, id="min-tokens-in-zero"),
        pytest.param({"max_tokens_in": 1}, id="max-tokens-in"),
        pytest.param({"min_tokens_out": 0}, id="min-tokens-out-zero"),
        pytest.param({"max_tokens_out": 1}, id="max-tokens-out"),
        pytest.param({"min_total_tokens": 0}, id="min-total-tokens-zero"),
        pytest.param({"max_total_tokens": 1}, id="max-total-tokens"),
    ],
)
async def test_incremental_sync_rejects_result_narrowing_filters(
    db: AnalyzerDatabase,
    filter_overrides: dict[str, object],
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("filtered incremental sync must fail before calling upstream")

    settings = _make_settings()
    async with _mock_client(handler) as client:
        engine = SyncEngine(settings, db, client=client)
        with pytest.raises(ValueError, match="cannot be combined with result filters"):
            await engine.sync_logs(
                "acct",
                "gw",
                LogFilters(per_page=7, meta_info=True, **filter_overrides),
                incremental=True,
            )


@pytest.mark.asyncio
async def test_incremental_sync_allows_page_size_and_meta_info(db: AnalyzerDatabase) -> None:
    seen_queries: list[dict[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_queries.append(dict(request.url.params))
        return httpx.Response(
            200, json={"success": True, "result_info": {"total_count": 0}, "result": []}
        )

    settings = _make_settings()
    async with _mock_client(handler) as client:
        engine = SyncEngine(settings, db, client=client)
        await engine.sync_logs(
            "acct",
            "gw",
            LogFilters(page=1, per_page=7, meta_info=True),
            incremental=True,
        )

    assert seen_queries == [
        {
            "page": "1",
            "per_page": "7",
            "order_by": "created_at",
            "order_by_direction": "asc",
            "meta_info": "true",
        }
    ]


@pytest.mark.asyncio
async def test_incremental_sync_rejects_unsafe_order(db: AnalyzerDatabase) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("unsafe incremental ordering must fail before calling upstream")

    settings = _make_settings()
    async with _mock_client(handler) as client:
        engine = SyncEngine(settings, db, client=client)
        with pytest.raises(ValueError, match="created_at ascending"):
            await engine.sync_logs(
                "acct",
                "gw",
                LogFilters(per_page=2, order_by="created_at", direction="desc"),
                incremental=True,
            )


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
async def test_sync_usage_uses_config_retry_failed_default(db: AnalyzerDatabase) -> None:
    db.logs.upsert_many("acct", "gw", [{"id": "failed"}, {"id": "missing"}])
    db.logs.upsert_usage("acct", "gw", "failed", UsageFields(), FetchStatus.FAILED, 500, "boom")
    requested: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(request.url.path)
        return httpx.Response(200, json={"usage": {"input_tokens": 1, "output_tokens": 1}})

    settings = _make_settings(
        sync=SyncConfig(
            per_page=2,
            log_throttle_ms=0,
            usage_workers=2,
            usage_batch_size=1,
            retry_failed=False,
        )
    )
    async with _mock_client(handler) as client:
        engine = SyncEngine(settings, db, client=client)
        result = await engine.sync_usage("acct", "gw")

    assert result.targets == 1
    assert requested == ["/client/v4/accounts/acct/ai-gateway/gateways/gw/logs/missing/response"]


@pytest.mark.asyncio
async def test_sync_usage_retries_previous_run_failure_started_in_same_second(
    db: AnalyzerDatabase,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db.logs.upsert_many(
        "acct",
        "gw",
        [{"id": "failed", "created_at": "2026-07-01T00:00:00Z"}],
    )
    monkeypatch.setattr(
        "cf_aigw_analyzer.core.sync_engine.utc_now",
        lambda: "2026-07-01T12:00:00Z",
    )
    monkeypatch.setattr(
        "cf_aigw_analyzer.data.repository.events.utc_now",
        lambda: "2026-07-01T12:00:00Z",
    )
    precise_times = iter(
        [
            "2026-07-01T12:00:00.000100Z",
            "2026-07-01T12:00:00.000200Z",
            "2026-07-01T12:00:00.000300Z",
            "2026-07-01T12:00:00.000400Z",
        ]
    )

    def precise_now() -> str:
        return next(precise_times)

    monkeypatch.setattr(
        "cf_aigw_analyzer.core.sync_engine.utc_now_precise",
        precise_now,
        raising=False,
    )
    monkeypatch.setattr(
        "cf_aigw_analyzer.data.repository.events.utc_now_precise",
        precise_now,
        raising=False,
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"success": False, "errors": [{"message": "boom"}]})

    settings = _make_settings(
        sync=SyncConfig(
            per_page=2,
            log_throttle_ms=0,
            usage_workers=1,
            usage_batch_size=1,
            retry_failed=True,
        )
    )
    async with _mock_client(handler) as client:
        engine = SyncEngine(settings, db, client=client)
        first = await engine.sync_usage("acct", "gw", retry_failed=True)
        second = await engine.sync_usage("acct", "gw", retry_failed=True)

    assert first.targets == 1
    assert first.failed == 1
    assert second.targets == 1
    assert second.failed == 1


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
