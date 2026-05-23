"""Sync orchestration: metadata + response-usage workflows."""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

import httpx

from cf_aigw_analyzer.config.settings import Settings
from cf_aigw_analyzer.core.cloudflare import CloudflareApiError, CloudflareClient, LogFilters
from cf_aigw_analyzer.core.usage_parser import parse_usage_from_response
from cf_aigw_analyzer.data.db import AnalyzerDatabase
from cf_aigw_analyzer.data.models import UsageFields
from cf_aigw_analyzer.models.enums import FetchStatus
from cf_aigw_analyzer.utils.time import utc_now


@dataclass(slots=True)
class SyncMetadataResult:
    logs_count: int = 0
    started_at: str = ""
    finished_at: str = ""
    run_id: int | None = None


@dataclass(slots=True)
class SyncUsageResult:
    targets: int = 0
    fetched: int = 0
    parsed: int = 0
    no_usage: int = 0
    failed: int = 0
    started_at: str = ""
    finished_at: str = ""
    run_id: int | None = None
    errors: list[str] = field(default_factory=list)


class SyncEngine:
    """Compose CloudflareClient + AnalyzerDatabase into the sync workflows."""

    def __init__(
        self,
        settings: Settings,
        db: AnalyzerDatabase,
        *,
        client: CloudflareClient | None = None,
    ) -> None:
        self.settings = settings
        self.db = db
        self._client = client
        self._owns_client = client is None

    async def __aenter__(self) -> SyncEngine:
        return self

    async def __aexit__(self, *exc_info) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()

    @property
    def client(self) -> CloudflareClient:
        if self._client is None:
            self._client = CloudflareClient(self.settings.cloudflare)
        return self._client

    async def sync_gateways(self, account_id: str) -> int:
        gateways = [gw async for gw in self.client.iter_gateways(account_id)]
        return self.db.gateways.upsert_many(account_id, gateways)

    async def sync_logs(
        self,
        account_id: str,
        gateway_id: str,
        filters: LogFilters,
        *,
        limit: int | None = None,
    ) -> SyncMetadataResult:
        started_at = utc_now()
        batch: list[dict[str, Any]] = []
        flush_size = max(50, self.settings.sync.usage_batch_size)
        logs_count = 0

        async for log in self.client.iter_logs(
            account_id,
            gateway_id,
            filters,
            limit=limit,
            throttle_ms=self.settings.sync.log_throttle_ms,
        ):
            batch.append(log)
            if len(batch) >= flush_size:
                logs_count += self.db.logs.upsert_many(account_id, gateway_id, batch)
                batch.clear()

        if batch:
            logs_count += self.db.logs.upsert_many(account_id, gateway_id, batch)

        finished_at = utc_now()
        run_id = self.db.sync_runs.record(
            account_id,
            gateway_id,
            mode="sync",
            params={**filters.to_query(), "limit": limit},
            logs_count=logs_count,
            started_at=started_at,
        )
        return SyncMetadataResult(
            logs_count=logs_count,
            started_at=started_at,
            finished_at=finished_at,
            run_id=run_id,
        )

    async def sync_usage(
        self,
        account_id: str,
        gateway_id: str,
        *,
        missing_only: bool = False,
        refresh: bool = False,
        retry_failed: bool = True,
        workers: int | None = None,
        limit: int | None = None,
    ) -> SyncUsageResult:
        started_at = utc_now()
        targets = self.db.logs.usage_targets(
            account_id,
            gateway_id,
            missing_only=missing_only,
            refresh=refresh,
            retry_failed=retry_failed,
            limit=limit,
        )
        if not targets:
            run_id = self.db.sync_runs.record(
                account_id,
                gateway_id,
                mode="sync-usage",
                params={
                    "missing_only": missing_only,
                    "refresh": refresh,
                    "retry_failed": retry_failed,
                    "limit": limit,
                },
                started_at=started_at,
            )
            return SyncUsageResult(
                targets=0, started_at=started_at, finished_at=utc_now(), run_id=run_id
            )

        worker_count = workers or self.settings.sync.usage_workers
        semaphore = asyncio.Semaphore(max(1, worker_count))
        errors: list[str] = []
        counters = SyncUsageResult(targets=len(targets), started_at=started_at)

        async def process(log_id: str) -> None:
            """Fetch + parse + persist one log's usage.

            Any unexpected exception is caught and recorded as ``FAILED`` so a
            single bad row never poisons the rest of the batch. SQLite writes
            here must remain synchronous (no ``await`` between BEGIN and COMMIT)
            because all coroutines share the database connection.
            """

            async with semaphore:
                try:
                    status, http_status, payload, error = await self._fetch_usage_payload(
                        account_id, gateway_id, log_id
                    )
                    usage = (
                        parse_usage_from_response(payload) if payload is not None else UsageFields()
                    )
                    effective_status = status
                    if status == FetchStatus.PARSED and not usage.has_numeric_data:
                        effective_status = FetchStatus.NO_USAGE
                    self._persist_usage(
                        account_id,
                        gateway_id,
                        log_id,
                        usage,
                        effective_status,
                        http_status,
                        error,
                    )
                    counters.fetched += 1
                    if effective_status == FetchStatus.PARSED:
                        counters.parsed += 1
                    elif effective_status == FetchStatus.NO_USAGE:
                        counters.no_usage += 1
                    else:
                        counters.failed += 1
                        if error and len(errors) < 20:
                            errors.append(f"{log_id}: {error}")
                except Exception as exc:
                    counters.fetched += 1
                    counters.failed += 1
                    if len(errors) < 20:
                        errors.append(f"{log_id}: {exc!r}")
                    # Best-effort persist of the failure so the row is not lost.
                    with contextlib.suppress(Exception):
                        self._persist_usage(
                            account_id,
                            gateway_id,
                            log_id,
                            UsageFields(),
                            FetchStatus.FAILED,
                            None,
                            f"unhandled: {exc!r}",
                        )

        try:
            await asyncio.gather(
                *(process(log_id) for log_id in targets),
                return_exceptions=False,
            )
        finally:
            counters.errors = errors
            counters.finished_at = utc_now()
            counters.run_id = self.db.sync_runs.record(
                account_id,
                gateway_id,
                mode="sync-usage",
                params={
                    "missing_only": missing_only,
                    "refresh": refresh,
                    "retry_failed": retry_failed,
                    "workers": worker_count,
                    "limit": limit,
                },
                usage_fetched=counters.fetched,
                usage_parsed=counters.parsed,
                usage_no_usage=counters.no_usage,
                usage_failed=counters.failed,
                started_at=started_at,
            )
        return counters

    async def _fetch_usage_payload(
        self,
        account_id: str,
        gateway_id: str,
        log_id: str,
    ) -> tuple[FetchStatus, int | None, Any, str | None]:
        try:
            http_status, payload = await self.client.fetch_log_response(
                account_id, gateway_id, log_id
            )
        except CloudflareApiError as exc:
            if exc.status_code == 404:
                return FetchStatus.NO_USAGE, exc.status_code, None, str(exc)
            return FetchStatus.FAILED, exc.status_code, None, str(exc)
        except httpx.HTTPError as exc:
            return FetchStatus.FAILED, None, None, str(exc)

        if http_status == 404:
            return FetchStatus.NO_USAGE, http_status, None, "response body unavailable"
        if http_status >= 400:
            return FetchStatus.FAILED, http_status, payload, f"HTTP {http_status}"
        return FetchStatus.PARSED, http_status, payload, None

    def _persist_usage(
        self,
        account_id: str,
        gateway_id: str,
        log_id: str,
        usage: UsageFields,
        status: FetchStatus,
        http_status: int | None,
        error: str | None,
    ) -> None:
        self.db.usage.upsert(
            account_id,
            gateway_id,
            log_id,
            usage,
            status,
            http_status,
            error,
        )
        if status == FetchStatus.PARSED and (usage.input_tokens or usage.output_tokens):
            self.db.logs.update_tokens_from_usage(
                account_id,
                gateway_id,
                log_id,
                usage.input_tokens,
                usage.output_tokens,
            )
            self.db.metrics.refresh_usage_dependent(account_id, gateway_id, log_id, usage)


def chunk(iterable: Iterable[Any], size: int) -> Iterable[list[Any]]:
    """Yield ``iterable`` in fixed-size lists (used for batched persistence)."""

    batch: list[Any] = []
    for item in iterable:
        batch.append(item)
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch
