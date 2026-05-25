"""`GET /api/v1/status` + `/api/v1/sync/runs/*`."""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from cf_aigw_analyzer.control.deps import get_state
from cf_aigw_analyzer.control.schemas.sync import SyncRunSnapshot

router = APIRouter(tags=["status"])


@router.get("/status")
async def status_endpoint(
    account_id: str | None = Query(default=None),
    gateway_id: str | None = Query(default=None),
    state=Depends(get_state),
) -> dict[str, Any]:
    summary = state.db.logs.summary(account_id, gateway_id)
    usage_counts = state.db.logs.status_counts(account_id, gateway_id)
    last_run = state.db.sync_runs.last(account_id, gateway_id)
    return {
        "database": str(state.db.path),
        "database_bytes": state.db.database_bytes,
        "total_logs": summary["total_logs"],
        "first_log_at": summary["first_log_at"],
        "last_log_at": summary["last_log_at"],
        "usage_parsed": usage_counts.get("parsed", 0),
        "usage_no_usage": usage_counts.get("no_usage", 0),
        "usage_failed": usage_counts.get("failed", 0),
        "last_run": _normalize_run(last_run) if last_run else None,
    }


@router.get("/sync/runs", response_model=list[SyncRunSnapshot])
async def sync_runs(
    account_id: str | None = Query(default=None),
    gateway_id: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=200),
    state=Depends(get_state),
) -> list[SyncRunSnapshot]:
    runs = state.db.sync_runs.list_recent(account_id, gateway_id, limit=limit)
    return [SyncRunSnapshot(**_normalize_run(run)) for run in runs]


@router.get("/sync/runs/{run_id}", response_model=SyncRunSnapshot)
async def sync_run_detail(run_id: int, state=Depends(get_state)) -> SyncRunSnapshot:
    run = state.db.sync_runs.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="run not found")
    return SyncRunSnapshot(**_normalize_run(run))


def _normalize_run(run: dict[str, Any]) -> dict[str, Any]:
    payload = dict(run)
    raw = payload.pop("params_json", None) or "{}"
    try:
        payload["params"] = json.loads(raw)
    except json.JSONDecodeError:
        payload["params"] = {}
    return payload
