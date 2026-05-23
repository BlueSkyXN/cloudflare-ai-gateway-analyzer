"""Event response schemas."""

from __future__ import annotations

from pydantic import BaseModel


class EventItem(BaseModel):
    log_id: str
    created_at: str | None = None
    provider: str | None = None
    model: str | None = None
    model_type: str | None = None
    success: bool | None = None
    cached: bool | None = None
    status_code: int | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    cached_tokens: int | None = None
    reasoning_tokens: int | None = None
    usage_fetch_status: str | None = None
    duration_ms: float | None = None
    latency_ms: float | None = None
    total_ms: float | None = None
    generation_ms: float | None = None
    output_tps: float | None = None
    visible_output_tps: float | None = None


class EventsResponse(BaseModel):
    events: list[EventItem]
    count: int
