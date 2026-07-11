"""Sync orchestration: metadata + response-usage workflows."""

from __future__ import annotations

import asyncio
import contextlib
import uuid
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta, timezone
from itertools import chain
from typing import Any

import httpx

from cf_aigw_analyzer.config.settings import Settings
from cf_aigw_analyzer.core.cloudflare import CloudflareApiError, CloudflareClient, LogFilters
from cf_aigw_analyzer.core.usage_parser import parse_usage_from_response
from cf_aigw_analyzer.data.db import AnalyzerDatabase, transaction
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
        incremental: bool = False,
    ) -> SyncMetadataResult:
        if incremental and limit is not None:
            raise ValueError("incremental sync cannot be combined with limit")
        owner = _lock_owner()
        self.db.sync_locks.acquire(account_id, gateway_id, "sync", owner)
        started_at = utc_now()
        try:
            effective_filters = self._apply_incremental_state(
                account_id, gateway_id, filters, incremental
            )
            batch: list[dict[str, Any]] = []
            flush_size = max(50, self.settings.sync.usage_batch_size)
            logs_count = 0
            latest_created_at: str | None = None
            latest_log_id: str | None = None

            async for log in self.client.iter_logs(
                account_id,
                gateway_id,
                effective_filters,
                limit=limit,
                throttle_ms=self.settings.sync.log_throttle_ms,
            ):
                batch.append(log)
                latest_created_at, latest_log_id = _choose_latest_seen(
                    latest_created_at, latest_log_id, log
                )
                if len(batch) >= flush_size:
                    logs_count += self.db.logs.upsert_many(account_id, gateway_id, batch)
                    batch.clear()

            if batch:
                logs_count += self.db.logs.upsert_many(account_id, gateway_id, batch)

            self.db.sync_state.record_success(
                account_id,
                gateway_id,
                "sync",
                last_seen_created_at=latest_created_at,
                last_seen_log_id=latest_log_id,
            )
            finished_at = utc_now()
            run_id = self.db.sync_runs.record(
                account_id,
                gateway_id,
                mode="sync",
                params={
                    **effective_filters.to_query(),
                    "limit": limit,
                    "incremental": incremental,
                },
                logs_count=logs_count,
                started_at=started_at,
            )
            return SyncMetadataResult(
                logs_count=logs_count,
                started_at=started_at,
                finished_at=finished_at,
                run_id=run_id,
            )
        finally:
            self.db.sync_locks.release(account_id, gateway_id, "sync", owner)

    async def sync_usage(
        self,
        account_id: str,
        gateway_id: str,
        *,
        missing_only: bool = False,
        refresh: bool = False,
        retry_failed: bool | None = None,
        workers: int | None = None,
        limit: int | None = None,
    ) -> SyncUsageResult:
        owner = _lock_owner()
        self.db.sync_locks.acquire(account_id, gateway_id, "sync-usage", owner)
        started_at = utc_now()
        try:
            effective_retry_failed = (
                self.settings.sync.retry_failed if retry_failed is None else retry_failed
            )
            worker_count = workers if workers is not None else self.settings.sync.usage_workers
            worker_count = min(64, max(1, worker_count))
            batch_size = self.settings.sync.usage_batch_size
            batches = self.db.logs.iter_usage_target_batches(
                account_id,
                gateway_id,
                missing_only=missing_only,
                refresh=refresh,
                retry_failed=effective_retry_failed,
                batch_size=batch_size,
                limit=limit,
                failed_before=started_at,
            )
            first_batch = next(batches, None)
            if not first_batch:
                self.db.sync_state.record_success(account_id, gateway_id, "sync-usage")
                run_id = self.db.sync_runs.record(
                    account_id,
                    gateway_id,
                    mode="sync-usage",
                    params={
                        "missing_only": missing_only,
                        "refresh": refresh,
                        "retry_failed": effective_retry_failed,
                        "workers": worker_count,
                        "batch_size": batch_size,
                        "limit": limit,
                    },
                    started_at=started_at,
                )
                return SyncUsageResult(
                    targets=0, started_at=started_at, finished_at=utc_now(), run_id=run_id
                )

            semaphore = asyncio.Semaphore(worker_count)
            errors: list[str] = []
            counters = SyncUsageResult(started_at=started_at)

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
                            parse_usage_from_response(payload)
                            if payload is not None
                            else UsageFields()
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
                for targets in chain((first_batch,), batches):
                    counters.targets += len(targets)
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
                        "retry_failed": effective_retry_failed,
                        "workers": worker_count,
                        "batch_size": batch_size,
                        "limit": limit,
                    },
                    usage_fetched=counters.fetched,
                    usage_parsed=counters.parsed,
                    usage_no_usage=counters.no_usage,
                    usage_failed=counters.failed,
                    started_at=started_at,
                )
            self.db.sync_state.record_success(account_id, gateway_id, "sync-usage")
            return counters
        finally:
            self.db.sync_locks.release(account_id, gateway_id, "sync-usage", owner)

    def _apply_incremental_state(
        self,
        account_id: str,
        gateway_id: str,
        filters: LogFilters,
        incremental: bool,
    ) -> LogFilters:
        if not incremental:
            return filters
        if filters.start_date or filters.end_date:
            raise ValueError("incremental sync cannot be combined with explicit start/end dates")
        if filters.order_by not in (None, "created_at") or (
            filters.direction is not None and filters.direction.lower() != "asc"
        ):
            raise ValueError("incremental sync requires created_at ascending order")
        safe_query_fields = {
            "page",
            "per_page",
            "order_by",
            "order_by_direction",
            "start_date",
            "end_date",
            "meta_info",
        }
        result_filters = sorted(set(filters.to_query()) - safe_query_fields)
        if filters.page != 1:
            result_filters.insert(0, "page")
        if result_filters:
            raise ValueError(
                "incremental sync cannot be combined with result filters: "
                + ", ".join(result_filters)
            )
        effective_filters = replace(filters, order_by="created_at", direction="asc")
        state = self.db.sync_state.get(account_id, gateway_id, "sync")
        if not state or not state.get("last_seen_created_at"):
            return effective_filters
        start_date = _minus_minutes(
            str(state["last_seen_created_at"]),
            self.settings.sync.incremental_overlap_minutes,
        )
        return replace(effective_filters, start_date=start_date)

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
        """Persist parsed usage onto the log event fact row.

        The sync engine invokes this from inside a ``process`` coroutine; the
        writes here MUST stay synchronous (no ``await``) because all coroutines
        share the process-wide :class:`sqlite3.Connection`.
        """

        with transaction(self.db.conn):
            self.db.logs.upsert_usage(
                account_id,
                gateway_id,
                log_id,
                usage,
                status,
                http_status,
                error,
            )


def _lock_owner() -> str:
    return f"sync-engine:{uuid.uuid4().hex}"


def _choose_latest_seen(
    latest_created_at: str | None,
    latest_log_id: str | None,
    log: dict[str, Any],
) -> tuple[str | None, str | None]:
    created_at = log.get("created_at")
    log_id = log.get("id") or log.get("log_id")
    if not isinstance(created_at, str) or not created_at:
        return latest_created_at, latest_log_id
    if latest_created_at is None or created_at > latest_created_at:
        return created_at, str(log_id) if log_id is not None else latest_log_id
    if created_at == latest_created_at and log_id is not None:
        latest_log_id = max(latest_log_id or "", str(log_id))
    return latest_created_at, latest_log_id


def _minus_minutes(value: str, minutes: int) -> str:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return value
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    shifted = parsed.astimezone(timezone.utc) - timedelta(minutes=max(0, minutes))
    return shifted.strftime("%Y-%m-%dT%H:%M:%SZ")
