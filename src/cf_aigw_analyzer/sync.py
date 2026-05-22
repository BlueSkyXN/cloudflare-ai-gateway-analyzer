"""Sync orchestration."""

from __future__ import annotations

from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass
from typing import Any

from .cloudflare import CloudflareApiError, CloudflareClient
from .database import AnalyzerDatabase, utc_now
from .filters import LogFilters
from .usage import UsageFields, parse_usage_from_response


@dataclass(slots=True)
class SyncUsageStats:
    targets: int = 0
    fetched: int = 0
    parsed: int = 0
    no_usage: int = 0
    failed: int = 0


def sync_gateways(db: AnalyzerDatabase, client: CloudflareClient, account_id: str) -> int:
    gateways = list(client.iter_gateways(account_id))
    count = db.upsert_gateways(account_id, gateways)
    db.record_run(account_id, None, "gateways", {}, logs_count=0)
    return count


def sync_logs(
    db: AnalyzerDatabase,
    client: CloudflareClient,
    account_id: str,
    gateway_id: str,
    filters: LogFilters,
    limit: int | None = None,
) -> int:
    started_at = utc_now()
    count = 0
    batch: list[dict[str, Any]] = []
    for log in client.iter_logs(account_id, gateway_id, filters, limit=limit):
        batch.append(log)
        if len(batch) >= 200:
            count += db.upsert_logs(account_id, gateway_id, batch)
            batch.clear()
            print(f"已同步 metadata: {count}", end="\r")

    if batch:
        count += db.upsert_logs(account_id, gateway_id, batch)

    db.record_run(
        account_id,
        gateway_id,
        "sync",
        filters.to_api_params() | {"limit": limit},
        logs_count=count,
        started_at=started_at,
    )
    return count


def sync_usage(
    db: AnalyzerDatabase,
    client: CloudflareClient,
    account_id: str,
    gateway_id: str,
    missing_only: bool = False,
    refresh: bool = False,
    retry_failed: bool = True,
    workers: int = 8,
    limit: int | None = None,
) -> SyncUsageStats:
    started_at = utc_now()
    targets = db.usage_targets(
        account_id,
        gateway_id,
        missing_only=missing_only,
        refresh=refresh,
        retry_failed=retry_failed,
        limit=limit,
    )
    stats = SyncUsageStats(targets=len(targets))
    if not targets:
        db.record_run(
            account_id,
            gateway_id,
            "sync-usage",
            {"missing_only": missing_only, "refresh": refresh, "retry_failed": retry_failed, "limit": limit},
            started_at=started_at,
        )
        return stats

    workers = max(1, workers)

    def fetch(log_id: str) -> tuple[str, UsageFields, str, int | None, str | None]:
        try:
            response = client.fetch_log_response(account_id, gateway_id, log_id)
            usage = parse_usage_from_response(response.data)
            status = "parsed" if usage.has_numeric_data else "no_usage"
            return log_id, usage, status, response.status_code, None
        except CloudflareApiError as exc:
            if exc.status_code == 404:
                return log_id, UsageFields(), "no_usage", exc.status_code, str(exc)
            return log_id, UsageFields(), "failed", exc.status_code, str(exc)
        except Exception as exc:
            return log_id, UsageFields(), "failed", None, str(exc)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        iterator = iter(targets)
        pending: set[Future[tuple[str, UsageFields, str, int | None, str | None]]] = set()

        def submit_until_full() -> None:
            while len(pending) < workers * 4:
                try:
                    log_id = next(iterator)
                except StopIteration:
                    return
                pending.add(pool.submit(fetch, log_id))

        submit_until_full()
        while pending:
            done, pending = wait(pending, return_when=FIRST_COMPLETED)
            submit_until_full()
            for future in done:
                log_id, usage, status, http_status, error = future.result()
                db.upsert_usage(
                    account_id,
                    gateway_id,
                    log_id,
                    usage,
                    fetch_status=status,
                    http_status_code=http_status,
                    error_message=error,
                )
                stats.fetched += 1
                if status == "parsed":
                    stats.parsed += 1
                elif status == "no_usage":
                    stats.no_usage += 1
                else:
                    stats.failed += 1

                if stats.fetched % 10 == 0 or stats.fetched == stats.targets:
                    print(f"已同步 usage: {stats.fetched}/{stats.targets}", end="\r")

    db.record_run(
        account_id,
        gateway_id,
        "sync-usage",
        {
            "missing_only": missing_only,
            "refresh": refresh,
            "retry_failed": retry_failed,
            "workers": workers,
            "limit": limit,
        },
        usage_fetched=stats.fetched,
        usage_parsed=stats.parsed,
        usage_no_usage=stats.no_usage,
        usage_failed=stats.failed,
        started_at=started_at,
    )
    return stats
