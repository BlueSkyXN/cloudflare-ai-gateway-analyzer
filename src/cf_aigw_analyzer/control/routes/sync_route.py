"""`POST /api/v1/sync/{logs,usage}` + job status."""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from cf_aigw_analyzer.control.deps import get_jobs, get_state
from cf_aigw_analyzer.control.schemas.sync import (
    SyncJobSnapshot,
    SyncTriggerRequest,
    SyncTriggerResponse,
    SyncUsageTriggerRequest,
)
from cf_aigw_analyzer.control.tasks import JobRegistry
from cf_aigw_analyzer.core.cloudflare import CloudflareClient, LogFilters
from cf_aigw_analyzer.core.sync_engine import SyncEngine

router = APIRouter(prefix="/sync", tags=["sync"])


@router.post("/logs", response_model=SyncTriggerResponse)
async def trigger_sync_logs(
    payload: SyncTriggerRequest,
    background_tasks: BackgroundTasks,
    state=Depends(get_state),
    jobs: JobRegistry = Depends(get_jobs),
) -> SyncTriggerResponse:
    job = jobs.create(mode="sync-logs")
    background_tasks.add_task(_run_sync_logs, state, jobs, job.job_id, payload)
    return SyncTriggerResponse(job_id=job.job_id, status=job.status, mode=job.mode)


@router.post("/usage", response_model=SyncTriggerResponse)
async def trigger_sync_usage(
    payload: SyncUsageTriggerRequest,
    background_tasks: BackgroundTasks,
    state=Depends(get_state),
    jobs: JobRegistry = Depends(get_jobs),
) -> SyncTriggerResponse:
    job = jobs.create(mode="sync-usage")
    background_tasks.add_task(_run_sync_usage, state, jobs, job.job_id, payload)
    return SyncTriggerResponse(job_id=job.job_id, status=job.status, mode=job.mode)


@router.get("/jobs", response_model=list[SyncJobSnapshot])
async def list_jobs(jobs: JobRegistry = Depends(get_jobs)) -> list[SyncJobSnapshot]:
    return [SyncJobSnapshot(**job.to_dict()) for job in jobs.list()]


@router.get("/jobs/{job_id}", response_model=SyncJobSnapshot)
async def job_status(job_id: str, jobs: JobRegistry = Depends(get_jobs)) -> SyncJobSnapshot:
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    return SyncJobSnapshot(**job.to_dict())


async def _resolve_gateway(
    client: CloudflareClient,
    state,
    account_id: str,
    gateway_id: str | None,
    gateway_name: str | None,
) -> str:
    if gateway_id:
        return gateway_id
    if gateway_name:
        local = state.db.gateways.resolve_gateway_id(account_id, gateway_name)
        if local:
            return local
        remote = await client.resolve_gateway_id(account_id, gateway_name)
        if remote:
            return remote
    raise HTTPException(
        status_code=400, detail="gateway_id or gateway_name required and resolvable"
    )


async def _run_sync_logs(
    state,
    jobs: JobRegistry,
    job_id: str,
    payload: SyncTriggerRequest,
) -> None:
    try:
        client = CloudflareClient(state.settings.cloudflare)
        try:
            gateway = await _resolve_gateway(
                client, state, payload.account_id, payload.gateway_id, payload.gateway_name
            )
            engine = SyncEngine(state.settings, state.db, client=client)
            filters = LogFilters(
                per_page=state.settings.sync.per_page, **_coerce_filters(payload.filters)
            )
            meta = await engine.sync_logs(
                payload.account_id,
                gateway,
                filters,
                limit=payload.limit,
                incremental=payload.incremental,
            )
            updates: dict[str, Any] = {
                "logs_count": meta.logs_count,
                "run_id": meta.run_id,
            }
            if payload.with_usage:
                usage = await engine.sync_usage(
                    payload.account_id,
                    gateway,
                    missing_only=payload.missing_only,
                    refresh=payload.refresh_usage,
                    retry_failed=not payload.no_retry_failed,
                    workers=payload.usage_workers,
                    limit=payload.usage_limit,
                )
                updates.update(
                    targets=usage.targets,
                    usage_fetched=usage.fetched,
                    usage_parsed=usage.parsed,
                    usage_no_usage=usage.no_usage,
                    usage_failed=usage.failed,
                    run_id=usage.run_id or meta.run_id,
                )
            jobs.mark_done(job_id, **updates)
        finally:
            await client.aclose()
    except asyncio.CancelledError:  # pragma: no cover - shutdown path
        raise
    except Exception as exc:
        jobs.mark_done(job_id, error=str(exc))


async def _run_sync_usage(
    state,
    jobs: JobRegistry,
    job_id: str,
    payload: SyncUsageTriggerRequest,
) -> None:
    try:
        client = CloudflareClient(state.settings.cloudflare)
        try:
            gateway = await _resolve_gateway(
                client, state, payload.account_id, payload.gateway_id, payload.gateway_name
            )
            engine = SyncEngine(state.settings, state.db, client=client)
            usage = await engine.sync_usage(
                payload.account_id,
                gateway,
                missing_only=payload.missing_only,
                refresh=payload.refresh,
                retry_failed=not payload.no_retry_failed,
                workers=payload.workers,
                limit=payload.limit,
            )
            jobs.mark_done(
                job_id,
                targets=usage.targets,
                usage_fetched=usage.fetched,
                usage_parsed=usage.parsed,
                usage_no_usage=usage.no_usage,
                usage_failed=usage.failed,
                run_id=usage.run_id,
            )
        finally:
            await client.aclose()
    except asyncio.CancelledError:  # pragma: no cover
        raise
    except Exception as exc:
        jobs.mark_done(job_id, error=str(exc))


def _coerce_filters(filters: dict[str, Any]) -> dict[str, Any]:
    """Whitelist the keys allowed onto LogFilters from user-supplied JSON."""

    allowed = {
        "order_by",
        "direction",
        "start_date",
        "end_date",
        "model",
        "provider",
        "model_type",
        "search",
        "cached",
        "success",
        "feedback",
        "min_cost",
        "max_cost",
        "min_duration",
        "max_duration",
        "min_tokens_in",
        "max_tokens_in",
        "min_tokens_out",
        "max_tokens_out",
        "min_total_tokens",
        "max_total_tokens",
    }
    return {key: value for key, value in filters.items() if key in allowed}
