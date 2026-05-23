"""Analytics response schemas."""

from __future__ import annotations

from typing import Any

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
    p50_total_ms: float | None
    p95_total_ms: float | None
    p99_total_ms: float | None
    avg_latency_ms: float | None
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
    avg_output_tps: float | None
    avg_visible_output_tps: float | None


class ModelStats(BaseModel):
    model: str
    providers: list[str]
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
    avg_output_tps: float | None
    avg_visible_output_tps: float | None
    p95_total_ms: float | None = None


class ContextBucket(BaseModel):
    context_bucket: str
    requests: int
    success_count: int
    success_rate: float | None
    avg_input_tokens: float | None
    avg_output_tokens: float | None
    total_tokens: int
    cached_tokens: int
    cache_ratio: float | None
    avg_total_ms: float | None
    avg_output_tps: float | None
    avg_visible_output_tps: float | None


class InsightItem(BaseModel):
    level: str
    title: str
    detail: str


class AnalyticsResponse(BaseModel):
    summary: SummaryResponse
    timeseries: list[TimeseriesPoint]
    models: list[ModelStats]
    context_buckets: list[ContextBucket]
    insights: list[InsightItem]
    extra: dict[str, Any] = {}
