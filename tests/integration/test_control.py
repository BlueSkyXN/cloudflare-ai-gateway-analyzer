"""Integration tests for the FastAPI control plane using ASGI transport."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest
from pydantic import SecretStr

from cf_aigw_analyzer.config.settings import (
    CloudflareConfig,
    ControlConfig,
    Settings,
    StorageConfig,
)
from cf_aigw_analyzer.control.app import build_app
from cf_aigw_analyzer.control.lifecycle import AppState
from cf_aigw_analyzer.data import UsageFields
from cf_aigw_analyzer.data.db import AnalyzerDatabase
from cf_aigw_analyzer.models.enums import FetchStatus


@pytest.fixture
def state(tmp_path: Path) -> AppState:
    settings = Settings(
        cloudflare=CloudflareConfig(api_token=SecretStr("tok-test")),
        storage=StorageConfig(data_dir=tmp_path, db_filename="control.sqlite"),
        control=ControlConfig(static_dir=tmp_path / "missing-panel"),
    )
    db = AnalyzerDatabase(tmp_path / "control.sqlite")
    db.gateways.upsert_many("acct", [{"id": "gw", "name": "main"}])
    db.logs.upsert_many(
        "acct",
        "gw",
        [
            {
                "id": "log-1",
                "created_at": "2026-05-22T00:10:00Z",
                "provider": "openai",
                "model": "gpt-4o-mini",
                "success": True,
                "tokens_in": 100,
                "tokens_out": 30,
                "timings": {"total": 900, "latency": 200},
            },
            {
                "id": "log-2",
                "created_at": "2026-05-22T01:15:00Z",
                "provider": "anthropic",
                "model": "claude-3-haiku",
                "success": False,
                "tokens_in": 120_000,
                "tokens_out": 20,
                "timings": {"total": 5000, "latency": 800},
            },
        ],
    )
    db.logs.upsert_usage(
        "acct",
        "gw",
        "log-1",
        UsageFields(input_tokens=100, output_tokens=30, total_tokens=130, cached_tokens=40),
        FetchStatus.PARSED,
        200,
        None,
    )
    db.logs.upsert_usage("acct", "gw", "log-2", UsageFields(), FetchStatus.NO_USAGE, 404, "missing")
    state = AppState(settings=settings, db=db)
    yield state
    db.close()


@pytest.fixture
async def client(state: AppState) -> AsyncIterator[httpx.AsyncClient]:
    app = build_app(settings=state.settings, state=state)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.mark.asyncio
async def test_health(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["has_credentials"] is True


@pytest.mark.asyncio
async def test_scopes(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/v1/scopes")
    assert response.status_code == 200
    scopes = response.json()
    assert scopes[0]["gateway_id"] == "gw"
    assert scopes[0]["logs"] == 2


@pytest.mark.asyncio
async def test_analytics(client: httpx.AsyncClient) -> None:
    response = await client.get(
        "/api/v1/analytics", params={"account_id": "acct", "gateway_id": "gw", "limit": 10}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["summary"]["requests"] == 2
    assert body["summary"]["success_count"] == 1
    assert body["summary"]["total_tokens"] == 120_150
    assert body["summary"]["avg_input_tps"] == pytest.approx((500 + 150_000) / 2)
    assert isinstance(body["timeseries"], list)
    assert isinstance(body["by_model"], list)
    assert body["filter_options"]["providers"] == [
        {"provider": "anthropic", "requests": 1},
        {"provider": "openai", "requests": 1},
    ]
    assert {item["log_id"] for item in body["events"]} == {"log-1", "log-2"}


@pytest.mark.asyncio
async def test_analytics_timeseries_bucket_options(client: httpx.AsyncClient) -> None:
    response = await client.get(
        "/api/v1/analytics",
        params={
            "account_id": "acct",
            "gateway_id": "gw",
            "timeseries_bucket_hours": 4,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body["timeseries"]) == 1
    point = body["timeseries"][0]
    assert point["hour"] == "2026-05-22T00:00:00Z"
    assert point["requests"] == 2
    assert point["rpm"] == pytest.approx(2 / 240, rel=1e-6)
    assert point["tpm"] == pytest.approx(120_150 / 240, rel=1e-6)
    assert point["avg_input_tps"] == pytest.approx((500 + 150_000) / 2)


@pytest.mark.asyncio
async def test_status(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/v1/status", params={"account_id": "acct", "gateway_id": "gw"})
    assert response.status_code == 200
    body = response.json()
    assert body["total_logs"] == 2
    assert body["usage_parsed"] == 1
    assert body["usage_no_usage"] == 1


@pytest.mark.asyncio
async def test_config_is_redacted(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/v1/config")
    assert response.status_code == 200
    body = response.json()
    assert body["cloudflare"]["api_token"] == "***"


@pytest.mark.parametrize(
    ("path", "payload"),
    [
        ("/api/v1/sync/logs", {"account_id": "acct", "gateway_id": "gw", "limit": 0}),
        ("/api/v1/sync/logs", {"account_id": "acct", "gateway_id": "gw", "usage_limit": 0}),
        ("/api/v1/sync/logs", {"account_id": "acct", "gateway_id": "gw", "usage_workers": 0}),
        ("/api/v1/sync/usage", {"account_id": "acct", "gateway_id": "gw", "limit": 0}),
        ("/api/v1/sync/usage", {"account_id": "acct", "gateway_id": "gw", "workers": 0}),
    ],
)
@pytest.mark.asyncio
async def test_sync_triggers_reject_non_positive_limits_and_workers(
    client: httpx.AsyncClient,
    path: str,
    payload: dict[str, object],
) -> None:
    response = await client.post(path, json=payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_auth_required_when_token_set(tmp_path: Path) -> None:
    settings = Settings(
        cloudflare=CloudflareConfig(api_token=SecretStr("tok-test")),
        control=ControlConfig(
            auth_token=SecretStr("hunter2"),
            static_dir=tmp_path / "missing",
        ),
        storage=StorageConfig(data_dir=tmp_path, db_filename="auth.sqlite"),
    )
    db = AnalyzerDatabase(tmp_path / "auth.sqlite")
    try:
        state = AppState(settings=settings, db=db)
        app = build_app(settings=settings, state=state)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/health")
            assert resp.status_code == 401

            resp = await client.get("/api/v1/health", headers={"Authorization": "Bearer wrong"})
            assert resp.status_code == 403

            resp = await client.get("/api/v1/health", headers={"Authorization": "Bearer hunter2"})
            assert resp.status_code == 200

            # /docs, /redoc, /openapi.json must be gated the same way.
            for path in ("/docs", "/redoc", "/openapi.json"):
                resp = await client.get(path)
                assert resp.status_code == 401, f"{path} should require auth"
                resp = await client.get(path, headers={"Authorization": "Bearer wrong"})
                assert resp.status_code == 403, f"{path} should reject wrong token"
                resp = await client.get(path, headers={"Authorization": "Bearer hunter2"})
                assert resp.status_code == 200, f"{path} should accept correct token"
    finally:
        db.close()


@pytest.mark.asyncio
async def test_static_panel_serves_index_and_blocks_traversal(tmp_path: Path) -> None:
    """The panel mount serves index.html for SPA paths and refuses traversal."""

    panel_dir = tmp_path / "panel"
    panel_dir.mkdir()
    (panel_dir / "index.html").write_text(
        "<html><body>panel-marker</body></html>", encoding="utf-8"
    )

    secret_file = tmp_path / "secret.txt"
    secret_file.write_text("THIS-IS-SECRET", encoding="utf-8")

    settings = Settings(
        cloudflare=CloudflareConfig(api_token=SecretStr("tok-test")),
        control=ControlConfig(static_dir=panel_dir),
        storage=StorageConfig(data_dir=tmp_path, db_filename="static.sqlite"),
    )
    db = AnalyzerDatabase(tmp_path / "static.sqlite")
    try:
        state = AppState(settings=settings, db=db)
        app = build_app(settings=settings, state=state)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/")
            assert resp.status_code == 200
            assert "panel-marker" in resp.text

            # SPA route falls back to index.html via StaticFiles(html=True).
            resp = await client.get("/models")
            assert resp.status_code == 200
            assert "panel-marker" in resp.text

            # Traversal must NOT return the sensitive file content.
            resp = await client.get("/../secret.txt")
            assert "THIS-IS-SECRET" not in resp.text

            # API routes still work even with the SPA mount.
            resp = await client.get("/api/v1/health")
            assert resp.status_code == 200
    finally:
        db.close()


@pytest.mark.asyncio
async def test_sync_run_endpoints(client: httpx.AsyncClient, state: AppState) -> None:
    run_id = state.db.sync_runs.record(
        "acct",
        "gw",
        mode="seed",
        params={"foo": "bar"},
        logs_count=10,
        started_at="2026-05-22T00:00:00Z",
    )

    response = await client.get("/api/v1/sync/runs", params={"account_id": "acct"})
    assert response.status_code == 200
    runs = response.json()
    assert runs[0]["run_id"] == run_id

    response = await client.get(f"/api/v1/sync/runs/{run_id}")
    assert response.status_code == 200
    assert response.json()["mode"] == "seed"

    response = await client.get("/api/v1/sync/runs/99999")
    assert response.status_code == 404
