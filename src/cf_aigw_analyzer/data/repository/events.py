"""Event repository: one analytics-ready row per Cloudflare AI Gateway log."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable, Iterator
from typing import Any

from cf_aigw_analyzer.core.metrics import compute_log_metrics
from cf_aigw_analyzer.core.sanitizer import sanitize_log_metadata
from cf_aigw_analyzer.data.db import json_dumps, transaction
from cf_aigw_analyzer.data.models import LogQueryFilters, UsageFields
from cf_aigw_analyzer.models.enums import FetchStatus
from cf_aigw_analyzer.utils.time import parse_datetime_input, utc_now


class EventRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def upsert_many(
        self,
        account_id: str,
        gateway_id: str,
        logs: Iterable[dict[str, Any]],
    ) -> int:
        rows = list(logs)
        if not rows:
            return 0
        now = utc_now()
        count = 0
        with transaction(self.conn):
            for log in rows:
                log_id = log.get("id") or log.get("log_id")
                if not log_id:
                    continue
                input_tokens = _as_int(log.get("input_tokens", log.get("tokens_in")))
                output_tokens = _as_int(log.get("output_tokens", log.get("tokens_out")))
                total_tokens = _coalesce_total(
                    _as_int(log.get("total_tokens")), input_tokens, output_tokens
                )
                metrics = compute_log_metrics(log)
                sanitized = sanitize_log_metadata(log)
                self.conn.execute(
                    """
                    INSERT INTO log_events (
                        account_id, gateway_id, log_id, created_at, provider, model,
                        model_type, success, cached, status_code, cost_usd,
                        input_tokens, output_tokens, total_tokens, duration_ms,
                        latency_ms, total_ms, generation_ms, input_tps, output_tps,
                        ms_per_output_token, visible_output_tokens, visible_output_tps,
                        synced_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(account_id, gateway_id, log_id) DO UPDATE SET
                        created_at=excluded.created_at,
                        provider=excluded.provider,
                        model=excluded.model,
                        model_type=excluded.model_type,
                        success=excluded.success,
                        cached=excluded.cached,
                        status_code=excluded.status_code,
                        cost_usd=excluded.cost_usd,
                        input_tokens=CASE
                            WHEN log_events.usage_fetch_status='parsed'
                            THEN COALESCE(log_events.input_tokens, excluded.input_tokens)
                            ELSE excluded.input_tokens
                        END,
                        output_tokens=CASE
                            WHEN log_events.usage_fetch_status='parsed'
                            THEN COALESCE(log_events.output_tokens, excluded.output_tokens)
                            ELSE excluded.output_tokens
                        END,
                        total_tokens=CASE
                            WHEN log_events.usage_fetch_status='parsed'
                            THEN COALESCE(log_events.total_tokens, excluded.total_tokens)
                            ELSE excluded.total_tokens
                        END,
                        duration_ms=excluded.duration_ms,
                        latency_ms=excluded.latency_ms,
                        total_ms=excluded.total_ms,
                        generation_ms=excluded.generation_ms,
                        input_tps=CASE
                            WHEN log_events.usage_fetch_status='parsed'
                              AND COALESCE(log_events.input_tokens, excluded.input_tokens) > 0
                              AND excluded.latency_ms > 0
                            THEN COALESCE(log_events.input_tokens, excluded.input_tokens)
                                 / (excluded.latency_ms / 1000.0)
                            WHEN log_events.usage_fetch_status='parsed' THEN NULL
                            ELSE excluded.input_tps
                        END,
                        output_tps=CASE
                            WHEN log_events.usage_fetch_status='parsed'
                              AND COALESCE(log_events.output_tokens, excluded.output_tokens) > 0
                              AND excluded.generation_ms > 0
                            THEN COALESCE(log_events.output_tokens, excluded.output_tokens)
                                 / (excluded.generation_ms / 1000.0)
                            WHEN log_events.usage_fetch_status='parsed' THEN NULL
                            ELSE excluded.output_tps
                        END,
                        ms_per_output_token=CASE
                            WHEN log_events.usage_fetch_status='parsed'
                              AND COALESCE(log_events.output_tokens, excluded.output_tokens) > 0
                              AND excluded.generation_ms > 0
                            THEN excluded.generation_ms
                                 / COALESCE(log_events.output_tokens, excluded.output_tokens)
                            WHEN log_events.usage_fetch_status='parsed' THEN NULL
                            ELSE excluded.ms_per_output_token
                        END,
                        visible_output_tokens=CASE
                            WHEN log_events.usage_fetch_status='parsed'
                              AND COALESCE(log_events.output_tokens, excluded.output_tokens) IS NOT NULL
                              AND log_events.reasoning_tokens IS NOT NULL
                            THEN MAX(
                                COALESCE(log_events.output_tokens, excluded.output_tokens)
                                    - log_events.reasoning_tokens,
                                0
                            )
                            WHEN log_events.usage_fetch_status='parsed' THEN NULL
                            ELSE excluded.visible_output_tokens
                        END,
                        visible_output_tps=CASE
                            WHEN log_events.usage_fetch_status='parsed'
                              AND COALESCE(log_events.output_tokens, excluded.output_tokens) IS NOT NULL
                              AND log_events.reasoning_tokens IS NOT NULL
                              AND excluded.generation_ms > 0
                            THEN MAX(
                                COALESCE(log_events.output_tokens, excluded.output_tokens)
                                    - log_events.reasoning_tokens,
                                0
                            ) / (excluded.generation_ms / 1000.0)
                            WHEN log_events.usage_fetch_status='parsed' THEN NULL
                            ELSE excluded.visible_output_tps
                        END,
                        synced_at=excluded.synced_at,
                        updated_at=excluded.updated_at
                    """,
                    (
                        account_id,
                        gateway_id,
                        str(log_id),
                        log.get("created_at"),
                        log.get("provider"),
                        log.get("model"),
                        log.get("model_type"),
                        _as_bool_int(log.get("success")),
                        _as_bool_int(log.get("cached")),
                        _as_int(log.get("status_code")),
                        _as_float(log.get("cost", log.get("cost_usd"))),
                        input_tokens,
                        output_tokens,
                        total_tokens,
                        metrics.duration_ms,
                        metrics.latency_ms,
                        metrics.total_ms,
                        metrics.generation_ms,
                        metrics.input_tps,
                        metrics.output_tps,
                        metrics.ms_per_output_token,
                        metrics.visible_output_tokens,
                        metrics.visible_output_tps,
                        now,
                        now,
                    ),
                )
                self.conn.execute(
                    """
                    INSERT INTO log_raw (account_id, gateway_id, log_id, raw_json, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(account_id, gateway_id, log_id) DO UPDATE SET
                        raw_json=excluded.raw_json,
                        updated_at=excluded.updated_at
                    """,
                    (account_id, gateway_id, str(log_id), json_dumps(sanitized), now),
                )
                count += 1
        return count

    def upsert_usage(
        self,
        account_id: str,
        gateway_id: str,
        log_id: str,
        usage: UsageFields,
        fetch_status: FetchStatus,
        http_status_code: int | None,
        error_message: str | None,
    ) -> None:
        now = utc_now()
        status_value = fetch_status.value if isinstance(fetch_status, FetchStatus) else fetch_status
        with transaction(self.conn):
            row = self.conn.execute(
                """
                SELECT * FROM log_events
                WHERE account_id=? AND gateway_id=? AND log_id=?
                """,
                (account_id, gateway_id, log_id),
            ).fetchone()
            if row is None:
                return

            input_tokens = row["input_tokens"]
            output_tokens = row["output_tokens"]
            total_tokens = row["total_tokens"]
            cached_tokens = row["cached_tokens"]
            reasoning_tokens = row["reasoning_tokens"]
            cache_write_tokens = row["cache_write_tokens"]
            input_tps = row["input_tps"]
            output_tps = row["output_tps"]
            ms_per_output_token = row["ms_per_output_token"]
            visible_output_tokens = row["visible_output_tokens"]
            visible_output_tps = row["visible_output_tps"]

            if fetch_status == FetchStatus.PARSED:
                input_tokens = _prefer(usage.input_tokens, input_tokens)
                output_tokens = _prefer(usage.output_tokens, output_tokens)
                total_tokens = _prefer(
                    usage.total_tokens,
                    _coalesce_total(None, input_tokens, output_tokens),
                    total_tokens,
                )
                cached_tokens = _prefer(usage.cached_tokens, cached_tokens)
                reasoning_tokens = _prefer(usage.reasoning_tokens, reasoning_tokens)
                cache_write_tokens = _prefer(usage.cache_write_tokens, cache_write_tokens)
                metric_updates = _usage_metric_updates(
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    reasoning_tokens=reasoning_tokens,
                    latency_ms=row["latency_ms"],
                    generation_ms=row["generation_ms"],
                )
                input_tps = _prefer(metric_updates["input_tps"], input_tps)
                output_tps = _prefer(metric_updates["output_tps"], output_tps)
                ms_per_output_token = _prefer(
                    metric_updates["ms_per_output_token"], ms_per_output_token
                )
                visible_output_tokens = _prefer(
                    metric_updates["visible_output_tokens"], visible_output_tokens
                )
                visible_output_tps = _prefer(
                    metric_updates["visible_output_tps"], visible_output_tps
                )

            self.conn.execute(
                """
                UPDATE log_events
                SET
                    input_tokens=?,
                    output_tokens=?,
                    total_tokens=?,
                    cached_tokens=?,
                    reasoning_tokens=?,
                    cache_write_tokens=?,
                    input_tps=?,
                    output_tps=?,
                    ms_per_output_token=?,
                    visible_output_tokens=?,
                    visible_output_tps=?,
                    usage_source=?,
                    usage_fetch_status=?,
                    usage_http_status_code=?,
                    usage_error_message=?,
                    usage_fetched_at=?,
                    updated_at=?
                WHERE account_id=? AND gateway_id=? AND log_id=?
                """,
                (
                    input_tokens,
                    output_tokens,
                    total_tokens,
                    cached_tokens,
                    reasoning_tokens,
                    cache_write_tokens,
                    input_tps,
                    output_tps,
                    ms_per_output_token,
                    visible_output_tokens,
                    visible_output_tps,
                    usage.source if fetch_status == FetchStatus.PARSED else row["usage_source"],
                    status_value,
                    http_status_code,
                    error_message,
                    now,
                    now,
                    account_id,
                    gateway_id,
                    log_id,
                ),
            )

    def usage_targets(
        self,
        account_id: str,
        gateway_id: str,
        missing_only: bool = False,
        refresh: bool = False,
        retry_failed: bool = True,
        limit: int | None = None,
    ) -> list[str]:
        clauses = ["account_id = ?", "gateway_id = ?"]
        params: list[Any] = [account_id, gateway_id]

        if not refresh:
            status_clauses = ["usage_fetch_status IS NULL"]
            if retry_failed and not missing_only:
                status_clauses.append("usage_fetch_status = 'failed'")
            clauses.append(f"({' OR '.join(status_clauses)})")

        sql = f"""
            SELECT log_id
            FROM log_events
            WHERE {" AND ".join(clauses)}
            ORDER BY
                CASE WHEN usage_fetch_status IS NULL THEN 0 ELSE 1 END,
                created_at DESC,
                log_id DESC
        """
        if limit is not None:
            sql += " LIMIT ?"
            params.append(limit)

        rows = self.conn.execute(sql, params).fetchall()
        return [str(row["log_id"]) for row in rows]

    def iter_usage_target_batches(
        self,
        account_id: str,
        gateway_id: str,
        *,
        missing_only: bool = False,
        refresh: bool = False,
        retry_failed: bool = True,
        batch_size: int = 50,
        limit: int | None = None,
        failed_before: str | None = None,
    ) -> Iterator[list[str]]:
        """Yield a stable, memory-bounded snapshot of usage targets.

        Missing rows are always processed before failed rows. A row that fails
        during the current run is excluded from the failed phase via
        ``failed_before`` so it is not retried twice in the same invocation.
        ``rowid`` keyset pagination avoids OFFSET drift as statuses are updated.
        """

        safe_batch_size = max(1, int(batch_size))
        remaining = max(0, int(limit)) if limit is not None else None
        if remaining == 0:
            return

        snapshot = self.conn.execute(
            """
            SELECT MAX(rowid) AS max_rowid
            FROM log_events
            WHERE account_id=? AND gateway_id=?
            """,
            (account_id, gateway_id),
        ).fetchone()
        max_rowid = int(snapshot["max_rowid"]) if snapshot and snapshot["max_rowid"] else None
        if max_rowid is None:
            return

        phases: list[str]
        if refresh:
            phases = ["all"]
        else:
            phases = ["missing"]
            if retry_failed and not missing_only:
                phases.append("failed")

        for phase in phases:
            before_rowid = max_rowid + 1
            while remaining is None or remaining > 0:
                clauses = [
                    "account_id = ?",
                    "gateway_id = ?",
                    "rowid <= ?",
                    "rowid < ?",
                ]
                params: list[Any] = [account_id, gateway_id, max_rowid, before_rowid]
                if phase == "missing":
                    clauses.append("usage_fetch_status IS NULL")
                elif phase == "failed":
                    clauses.append("usage_fetch_status = 'failed'")
                    if failed_before is not None:
                        clauses.append("(usage_fetched_at IS NULL OR usage_fetched_at < ?)")
                        params.append(failed_before)

                query_limit = (
                    safe_batch_size if remaining is None else min(safe_batch_size, remaining)
                )
                params.append(query_limit)
                rows = self.conn.execute(
                    f"""
                    SELECT rowid, log_id
                    FROM log_events
                    WHERE {" AND ".join(clauses)}
                    ORDER BY rowid DESC
                    LIMIT ?
                    """,
                    params,
                ).fetchall()
                if not rows:
                    break

                yield [str(row["log_id"]) for row in rows]
                before_rowid = int(rows[-1]["rowid"])
                if remaining is not None:
                    remaining -= len(rows)
            if remaining == 0:
                break

    def query(self, filters: LogQueryFilters) -> list[dict[str, Any]]:
        clauses = ["e.account_id = ?", "e.gateway_id = ?"]
        params: list[Any] = [filters.account_id, filters.gateway_id]

        if filters.start_date:
            clauses.append("julianday(e.created_at) >= julianday(?)")
            params.append(parse_datetime_input(filters.start_date))
        if filters.end_date:
            clauses.append("julianday(e.created_at) <= julianday(?)")
            params.append(parse_datetime_input(filters.end_date))
        if filters.provider:
            clauses.append("e.provider = ?")
            params.append(filters.provider)
        if filters.model:
            clauses.append("e.model = ?")
            params.append(filters.model)
        if filters.model_type:
            clauses.append("e.model_type = ?")
            params.append(filters.model_type)
        if filters.success is not None:
            clauses.append("e.success = ?")
            params.append(1 if filters.success else 0)
        if filters.cached is not None:
            clauses.append("e.cached = ?")
            params.append(1 if filters.cached else 0)
        if filters.search:
            clauses.append(
                """
                EXISTS (
                    SELECT 1 FROM log_raw r
                    WHERE r.account_id=e.account_id
                      AND r.gateway_id=e.gateway_id
                      AND r.log_id=e.log_id
                      AND r.raw_json LIKE ?
                )
                """
            )
            params.append(f"%{filters.search}%")

        sql = f"""
            SELECT e.*
            FROM log_events e
            WHERE {" AND ".join(clauses)}
            ORDER BY e.created_at DESC
        """
        if filters.limit:
            sql += " LIMIT ?"
            params.append(filters.limit)
        rows = self.conn.execute(sql, params).fetchall()
        return [dict(row) for row in rows]

    def summary(
        self, account_id: str | None = None, gateway_id: str | None = None
    ) -> dict[str, Any]:
        clauses: list[str] = []
        params: list[Any] = []
        if account_id:
            clauses.append("account_id = ?")
            params.append(account_id)
        if gateway_id:
            clauses.append("gateway_id = ?")
            params.append(gateway_id)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""

        row = self.conn.execute(
            """
            SELECT COUNT(*) AS total_logs,
                   MIN(created_at) AS first_log_at,
                   MAX(created_at) AS last_log_at
            FROM log_events
            """
            + where,
            params,
        ).fetchone()
        return dict(row) if row else {"total_logs": 0, "first_log_at": None, "last_log_at": None}

    def status_counts(self, account_id: str | None, gateway_id: str | None) -> dict[str, int]:
        clauses = ["usage_fetch_status IS NOT NULL"]
        params: list[object] = []
        if account_id:
            clauses.append("account_id = ?")
            params.append(account_id)
        if gateway_id:
            clauses.append("gateway_id = ?")
            params.append(gateway_id)
        rows = self.conn.execute(
            f"""
            SELECT usage_fetch_status, COUNT(*) AS n
            FROM log_events
            WHERE {" AND ".join(clauses)}
            GROUP BY usage_fetch_status
            """,
            params,
        ).fetchall()
        return {row["usage_fetch_status"]: int(row["n"]) for row in rows}

    def get_raw(self, account_id: str, gateway_id: str, log_id: str) -> str | None:
        row = self.conn.execute(
            """
            SELECT raw_json FROM log_raw
            WHERE account_id=? AND gateway_id=? AND log_id=?
            """,
            (account_id, gateway_id, log_id),
        ).fetchone()
        return str(row["raw_json"]) if row else None


def _usage_metric_updates(
    *,
    input_tokens: int | None,
    output_tokens: int | None,
    reasoning_tokens: int | None,
    latency_ms: Any,
    generation_ms: Any,
) -> dict[str, float | int | None]:
    latency = _as_float(latency_ms)
    generation = _as_float(generation_ms)
    input_value = float(input_tokens) if input_tokens is not None else None
    output_value = float(output_tokens) if output_tokens is not None else None
    input_tps: float | None = None
    output_tps: float | None = None
    ms_per_output_token: float | None = None
    visible_output_tokens: int | None = None
    visible_output_tps: float | None = None

    if input_value and latency and latency > 0:
        input_tps = input_value / (latency / 1000.0)
    if output_value and generation and generation > 0:
        output_tps = output_value / (generation / 1000.0)
        ms_per_output_token = generation / output_value
    if output_value is not None and reasoning_tokens is not None:
        visible_output_tokens = int(max(output_value - reasoning_tokens, 0))
        if generation and generation > 0:
            visible_output_tps = visible_output_tokens / (generation / 1000.0)
    return {
        "input_tps": input_tps,
        "output_tps": output_tps,
        "ms_per_output_token": ms_per_output_token,
        "visible_output_tokens": visible_output_tokens,
        "visible_output_tps": visible_output_tps,
    }


def _prefer(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


def _coalesce_total(
    explicit: int | None, input_tokens: int | None, output_tokens: int | None
) -> int | None:
    if explicit is not None:
        return explicit
    if input_tokens is not None and output_tokens is not None:
        return input_tokens + output_tokens
    return None


def _as_bool_int(value: Any) -> int | None:
    if value is None:
        return None
    return 1 if bool(value) else 0


def _as_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _as_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
