"""`GET /api/v1/analytics/*`."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from cf_aigw_analyzer.analytics import (
    AnalyticsFilters,
    build_context_buckets,
    build_insights,
    build_model_stats,
    build_summary,
    build_timeseries,
)
from cf_aigw_analyzer.control.deps import readonly_conn
from cf_aigw_analyzer.control.schemas.analytics import (
    ContextBucket,
    InsightItem,
    ModelStats,
    SummaryResponse,
    TimeseriesPoint,
)

router = APIRouter(prefix="/analytics", tags=["analytics"])


def _filters(
    account_id: str | None = Query(default=None),
    gateway_id: str | None = Query(default=None),
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
    provider: str | None = Query(default=None),
    model: str | None = Query(default=None),
    success: bool | None = Query(default=None),
) -> AnalyticsFilters:
    return AnalyticsFilters(
        account_id=account_id,
        gateway_id=gateway_id,
        start_date=start_date,
        end_date=end_date,
        provider=provider,
        model=model,
        success=success,
    )


@router.get("/summary", response_model=SummaryResponse)
async def summary(
    filters: AnalyticsFilters = Depends(_filters),
    conn=Depends(readonly_conn),
) -> SummaryResponse:
    return SummaryResponse(**build_summary(conn, filters))


@router.get("/timeseries", response_model=list[TimeseriesPoint])
async def timeseries(
    filters: AnalyticsFilters = Depends(_filters),
    conn=Depends(readonly_conn),
) -> list[TimeseriesPoint]:
    return [TimeseriesPoint(**point) for point in build_timeseries(conn, filters)]


@router.get("/models", response_model=list[ModelStats])
async def models(
    filters: AnalyticsFilters = Depends(_filters),
    conn=Depends(readonly_conn),
) -> list[ModelStats]:
    return [ModelStats(**item) for item in build_model_stats(conn, filters)]


@router.get("/context-buckets", response_model=list[ContextBucket])
async def context_buckets(
    filters: AnalyticsFilters = Depends(_filters),
    conn=Depends(readonly_conn),
) -> list[ContextBucket]:
    return [ContextBucket(**item) for item in build_context_buckets(conn, filters)]


@router.get("/insights", response_model=list[InsightItem])
async def insights(
    filters: AnalyticsFilters = Depends(_filters),
    conn=Depends(readonly_conn),
) -> list[InsightItem]:
    return [InsightItem(**item) for item in build_insights(conn, filters)]
