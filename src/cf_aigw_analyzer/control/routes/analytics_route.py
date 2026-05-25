"""`GET /api/v1/analytics`."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from cf_aigw_analyzer.analytics import AnalyticsFilters, build_analytics
from cf_aigw_analyzer.control.deps import readonly_conn
from cf_aigw_analyzer.control.schemas.analytics import AnalyticsResponse

router = APIRouter(tags=["analytics"])


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


@router.get("/analytics", response_model=AnalyticsResponse)
async def analytics(
    filters: AnalyticsFilters = Depends(_filters),
    limit: int = Query(default=500, ge=1, le=5000),
    conn=Depends(readonly_conn),
) -> AnalyticsResponse:
    return AnalyticsResponse(**build_analytics(conn, filters, limit=limit))
