"""Sync-related schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class SyncTriggerRequest(BaseModel):
    account_id: str
    gateway_id: str | None = None
    gateway_name: str | None = None
    limit: int | None = Field(default=None, ge=1)
    with_usage: bool = False
    missing_only: bool = False
    refresh_usage: bool = False
    no_retry_failed: bool = False
    usage_workers: int | None = Field(default=None, ge=1, le=64)
    usage_limit: int | None = Field(default=None, ge=1)
    filters: dict[str, Any] = Field(default_factory=dict)


class SyncUsageTriggerRequest(BaseModel):
    account_id: str
    gateway_id: str | None = None
    gateway_name: str | None = None
    missing_only: bool = False
    refresh: bool = False
    no_retry_failed: bool = False
    workers: int | None = Field(default=None, ge=1, le=64)
    limit: int | None = Field(default=None, ge=1)


class SyncTriggerResponse(BaseModel):
    job_id: str
    status: str  # running | done | failed
    mode: str


class SyncJobSnapshot(BaseModel):
    job_id: str
    status: str
    mode: str
    started_at: str
    finished_at: str | None = None
    logs_count: int = 0
    usage_fetched: int = 0
    usage_parsed: int = 0
    usage_no_usage: int = 0
    usage_failed: int = 0
    targets: int = 0
    error: str | None = None
    run_id: int | None = None


class SyncRunSnapshot(BaseModel):
    run_id: int
    account_id: str | None
    gateway_id: str | None
    mode: str
    params: dict[str, Any]
    logs_count: int
    usage_fetched: int
    usage_parsed: int
    usage_no_usage: int
    usage_failed: int
    started_at: str
    finished_at: str
