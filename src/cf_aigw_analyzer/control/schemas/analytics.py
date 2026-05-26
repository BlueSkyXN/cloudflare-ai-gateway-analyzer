"""Analytics response schemas."""

from __future__ import annotations

from pydantic import BaseModel


class SummaryResponse(BaseModel):
    requests: int
    success_count: int
    failed_count: int
    success_rate: float | None
    models: int
    providers: int
    first_log_at: str | None
    last_log_at: str | None
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cached_tokens: int
    reasoning_tokens: int
    cache_ratio: float | None
    avg_total_ms: float | None
    avg_latency_ms: float | None
    avg_generation_ms: float | None
    p50_total_ms: float | None
    p95_total_ms: float | None
    p99_total_ms: float | None
    avg_input_tps: float | None
    avg_output_tps: float | None
    avg_visible_output_tps: float | None
    usage_statuses: dict[str, int]


class TimeseriesPoint(BaseModel):
    hour: str
    requests: int
    success_count: int
    input_tokens: int
    output_tokens: int
    total_tokens: int
    rpm: float
    tpm: float
    avg_total_ms: float | None
    avg_latency_ms: float | None
    avg_generation_ms: float | None
    avg_input_tps: float | None
    avg_output_tps: float | None
    avg_visible_output_tps: float | None


class BreakdownStats(BaseModel):
    requests: int
    success_count: int
    success_rate: float | None
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cached_tokens: int
    reasoning_tokens: int
    cache_ratio: float | None
    tokens_per_request: float | None
    avg_input_tokens: float | None
    avg_output_tokens: float | None
    avg_total_ms: float | None
    avg_latency_ms: float | None
    avg_generation_ms: float | None
    avg_input_tps: float | None
    avg_output_tps: float | None
    avg_visible_output_tps: float | None


class ProviderStats(BreakdownStats):
    provider: str
    providers: list[str]


class ModelStats(BreakdownStats):
    model: str
    providers: list[str]
    p95_total_ms: float | None = None


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
    cache_write_tokens: int | None = None
    cost_usd: float | None = None
    duration_ms: float | None = None
    latency_ms: float | None = None
    total_ms: float | None = None
    generation_ms: float | None = None
    input_tps: float | None = None
    output_tps: float | None = None
    ms_per_output_token: float | None = None
    visible_output_tokens: int | None = None
    visible_output_tps: float | None = None
    usage_fetch_status: str | None = None
    usage_error_message: str | None = None


class ProviderOption(BaseModel):
    provider: str
    requests: int


class ModelOption(BaseModel):
    model: str
    providers: list[str]
    requests: int


class FilterOptionsResponse(BaseModel):
    providers: list[ProviderOption]
    models: list[ModelOption]


class AnalyticsResponse(BaseModel):
    summary: SummaryResponse
    timeseries: list[TimeseriesPoint]
    by_provider: list[ProviderStats]
    by_model: list[ModelStats]
    events: list[EventItem]
    filter_options: FilterOptionsResponse
