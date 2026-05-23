"""`GET /api/v1/events`."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from cf_aigw_analyzer.analytics import build_recent_events
from cf_aigw_analyzer.analytics.queries import AnalyticsFilters
from cf_aigw_analyzer.control.deps import readonly_conn
from cf_aigw_analyzer.control.schemas.events import EventItem, EventsResponse

router = APIRouter(prefix="/events", tags=["events"])


@router.get("", response_model=EventsResponse)
async def list_events(
    account_id: str | None = Query(default=None),
    gateway_id: str | None = Query(default=None),
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
    provider: str | None = Query(default=None),
    model: str | None = Query(default=None),
    success: bool | None = Query(default=None),
    limit: int = Query(default=500, ge=1, le=5000),
    conn=Depends(readonly_conn),
) -> EventsResponse:
    filters = AnalyticsFilters(
        account_id=account_id,
        gateway_id=gateway_id,
        start_date=start_date,
        end_date=end_date,
        provider=provider,
        model=model,
        success=success,
    )
    rows = build_recent_events(conn, filters, limit=limit)
    return EventsResponse(events=[EventItem(**row) for row in rows], count=len(rows))
