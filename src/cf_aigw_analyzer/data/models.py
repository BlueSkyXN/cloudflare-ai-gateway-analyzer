"""Row-level Pydantic models for the analyzer tables."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from cf_aigw_analyzer.models.enums import FetchStatus


class _Row(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)


class GatewayRow(_Row):
    account_id: str
    gateway_id: str
    name: str | None = None
    collect_logs: bool | None = None
    raw_json: str
    fetched_at: str


class LogEventRow(_Row):
    account_id: str
    gateway_id: str
    log_id: str
    created_at: str | None = None
    provider: str | None = None
    model: str | None = None
    model_type: str | None = None
    success: bool | None = None
    cached: bool | None = None
    status_code: int | None = None
    cost_usd: float | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    cached_tokens: int | None = None
    reasoning_tokens: int | None = None
    cache_write_tokens: int | None = None
    duration_ms: float | None = None
    latency_ms: float | None = None
    total_ms: float | None = None
    generation_ms: float | None = None
    output_tps: float | None = None
    ms_per_output_token: float | None = None
    visible_output_tokens: int | None = None
    visible_output_tps: float | None = None
    usage_source: str | None = None
    usage_fetch_status: FetchStatus | None = None
    usage_http_status_code: int | None = None
    usage_error_message: str | None = None
    usage_fetched_at: str | None = None
    synced_at: str
    updated_at: str


class SyncRunRow(_Row):
    run_id: int | None = None
    account_id: str | None = None
    gateway_id: str | None = None
    mode: str
    params: dict[str, Any] | None = None
    logs_count: int = 0
    usage_fetched: int = 0
    usage_parsed: int = 0
    usage_no_usage: int = 0
    usage_failed: int = 0
    started_at: str
    finished_at: str


class UsageFields(BaseModel):
    """Parser output: normalized token usage across providers."""

    model_config = ConfigDict(extra="ignore")

    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    cached_tokens: int | None = None
    reasoning_tokens: int | None = None
    cache_write_tokens: int | None = None
    source: str | None = None

    @property
    def has_numeric_data(self) -> bool:
        for key in (
            "input_tokens",
            "output_tokens",
            "total_tokens",
            "cached_tokens",
            "reasoning_tokens",
            "cache_write_tokens",
        ):
            if getattr(self, key) is not None:
                return True
        return False


class MetricsFields(BaseModel):
    """Computed metrics output."""

    model_config = ConfigDict(extra="ignore")

    duration_ms: float | None = None
    latency_ms: float | None = None
    total_ms: float | None = None
    generation_ms: float | None = None
    output_tps: float | None = None
    ms_per_output_token: float | None = None
    visible_output_tokens: int | None = None
    visible_output_tps: float | None = None


class LogQueryFilters(BaseModel):
    """Filter bundle for event queries."""

    model_config = ConfigDict(extra="forbid")

    account_id: str
    gateway_id: str
    start_date: str | None = None
    end_date: str | None = None
    provider: str | None = None
    model: str | None = None
    model_type: str | None = None
    success: bool | None = None
    cached: bool | None = None
    search: str | None = None
    limit: int | None = Field(default=None, ge=1, le=10_000)
