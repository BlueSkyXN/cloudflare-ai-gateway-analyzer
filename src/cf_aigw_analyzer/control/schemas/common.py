"""Shared response schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str
    database: str
    database_bytes: int
    has_credentials: bool


class ScopeItem(BaseModel):
    account_id: str
    gateway_id: str
    name: str
    logs: int
    first_log_at: str | None = None
    last_log_at: str | None = None


class GatewayItem(BaseModel):
    account_id: str
    gateway_id: str
    name: str | None = None
    collect_logs: bool | None = None
    fetched_at: str


class ScopeFilters(BaseModel):
    """Standardised query filters reused by analytics routes."""

    account_id: str | None = Field(default=None)
    gateway_id: str | None = Field(default=None)
    start_date: str | None = Field(default=None)
    end_date: str | None = Field(default=None)
    provider: str | None = Field(default=None)
    model: str | None = Field(default=None)
    success: bool | None = Field(default=None)
