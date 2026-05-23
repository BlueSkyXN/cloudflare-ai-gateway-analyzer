"""Logs repository: metadata + raw_json split + query."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from typing import Any

from cf_aigw_analyzer.core.metrics import compute_log_metrics
from cf_aigw_analyzer.core.sanitizer import sanitize_log_metadata
from cf_aigw_analyzer.data.db import json_dumps, transaction
from cf_aigw_analyzer.data.models import LogQueryFilters
from cf_aigw_analyzer.utils.time import parse_datetime_input, utc_now


class LogsRepository:
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
                sanitized = sanitize_log_metadata(log)
                metrics = compute_log_metrics(log)
                self.conn.execute(
                    """
                    INSERT INTO logs (
                        account_id, gateway_id, log_id, created_at, provider, model,
                        model_type, success, cached, status_code, cost_usd,
                        tokens_in, tokens_out, synced_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(account_id, gateway_id, log_id) DO UPDATE SET
                        created_at=excluded.created_at,
                        provider=excluded.provider,
                        model=excluded.model,
                        model_type=excluded.model_type,
                        success=excluded.success,
                        cached=excluded.cached,
                        status_code=excluded.status_code,
                        cost_usd=excluded.cost_usd,
                        tokens_in=excluded.tokens_in,
                        tokens_out=excluded.tokens_out,
                        synced_at=excluded.synced_at
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
                        _as_float(log.get("cost")),
                        _as_int(log.get("tokens_in")),
                        _as_int(log.get("tokens_out")),
                        now,
                    ),
                )
                self.conn.execute(
                    """
                    INSERT INTO logs_raw (account_id, gateway_id, log_id, raw_json, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(account_id, gateway_id, log_id) DO UPDATE SET
                        raw_json=excluded.raw_json,
                        updated_at=excluded.updated_at
                    """,
                    (account_id, gateway_id, str(log_id), json_dumps(sanitized), now),
                )
                self.conn.execute(
                    """
                    INSERT INTO log_metrics (
                        account_id, gateway_id, log_id, duration_ms, latency_ms,
                        total_ms, generation_ms, output_tps, ms_per_output_token,
                        visible_output_tokens, visible_output_tps, computed_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(account_id, gateway_id, log_id) DO UPDATE SET
                        duration_ms=excluded.duration_ms,
                        latency_ms=excluded.latency_ms,
                        total_ms=excluded.total_ms,
                        generation_ms=excluded.generation_ms,
                        output_tps=excluded.output_tps,
                        ms_per_output_token=excluded.ms_per_output_token,
                        visible_output_tokens=excluded.visible_output_tokens,
                        visible_output_tps=excluded.visible_output_tps,
                        computed_at=excluded.computed_at
                    """,
                    (
                        account_id,
                        gateway_id,
                        str(log_id),
                        metrics.duration_ms,
                        metrics.latency_ms,
                        metrics.total_ms,
                        metrics.generation_ms,
                        metrics.output_tps,
                        metrics.ms_per_output_token,
                        metrics.visible_output_tokens,
                        metrics.visible_output_tps,
                        now,
                    ),
                )
                count += 1
        return count

    def usage_targets(
        self,
        account_id: str,
        gateway_id: str,
        missing_only: bool = False,
        refresh: bool = False,
        retry_failed: bool = True,
        limit: int | None = None,
    ) -> list[str]:
        clauses = ["l.account_id = ?", "l.gateway_id = ?"]
        params: list[Any] = [account_id, gateway_id]

        if not refresh:
            failed_clause = " OR u.fetch_status = 'failed'" if retry_failed else ""
            if missing_only:
                clauses.append(
                    f"""
                    (
                        u.log_id IS NULL
                        {failed_clause}
                        OR (
                            u.fetch_status = 'parsed'
                            AND (
                                ((l.tokens_in IS NULL OR l.tokens_in = 0) AND u.input_tokens IS NOT NULL)
                                OR ((l.tokens_out IS NULL OR l.tokens_out = 0) AND u.output_tokens IS NOT NULL)
                            )
                        )
                    )
                    """
                )
            else:
                clauses.append(f"(u.log_id IS NULL{failed_clause})")

        sql = f"""
            SELECT l.log_id
            FROM logs l
            LEFT JOIN log_usage u
              ON l.account_id = u.account_id
             AND l.gateway_id = u.gateway_id
             AND l.log_id = u.log_id
            WHERE {" AND ".join(clauses)}
            ORDER BY l.created_at DESC
        """
        if limit:
            sql += " LIMIT ?"
            params.append(limit)

        rows = self.conn.execute(sql, params).fetchall()
        return [str(row["log_id"]) for row in rows]

    def query(self, filters: LogQueryFilters) -> list[dict[str, Any]]:
        clauses = ["l.account_id = ?", "l.gateway_id = ?"]
        params: list[Any] = [filters.account_id, filters.gateway_id]

        if filters.start_date:
            clauses.append("l.created_at >= ?")
            params.append(parse_datetime_input(filters.start_date))
        if filters.end_date:
            clauses.append("l.created_at <= ?")
            params.append(parse_datetime_input(filters.end_date))
        if filters.provider:
            clauses.append("l.provider = ?")
            params.append(filters.provider)
        if filters.model:
            clauses.append("l.model = ?")
            params.append(filters.model)
        if filters.model_type:
            clauses.append("l.model_type = ?")
            params.append(filters.model_type)
        if filters.success is not None:
            clauses.append("l.success = ?")
            params.append(1 if filters.success else 0)
        if filters.cached is not None:
            clauses.append("l.cached = ?")
            params.append(1 if filters.cached else 0)
        if filters.search:
            clauses.append(
                "EXISTS (SELECT 1 FROM logs_raw r WHERE r.account_id=l.account_id AND r.gateway_id=l.gateway_id AND r.log_id=l.log_id AND r.raw_json LIKE ?)"
            )
            params.append(f"%{filters.search}%")

        sql = f"""
            SELECT
                l.*,
                u.input_tokens   AS usage_input_tokens,
                u.output_tokens  AS usage_output_tokens,
                u.total_tokens   AS usage_total_tokens,
                u.cached_tokens  AS usage_cached_tokens,
                u.reasoning_tokens AS usage_reasoning_tokens,
                u.cache_write_tokens AS usage_cache_write_tokens,
                u.source         AS usage_source,
                u.fetch_status   AS usage_fetch_status,
                u.error_message  AS usage_error_message,
                m.duration_ms,
                m.latency_ms,
                m.total_ms,
                m.generation_ms,
                m.output_tps,
                m.ms_per_output_token,
                m.visible_output_tokens,
                m.visible_output_tps
            FROM logs l
            LEFT JOIN log_usage u
              ON l.account_id = u.account_id
             AND l.gateway_id = u.gateway_id
             AND l.log_id = u.log_id
            LEFT JOIN log_metrics m
              ON l.account_id = m.account_id
             AND l.gateway_id = m.gateway_id
             AND l.log_id = m.log_id
            WHERE {" AND ".join(clauses)}
            ORDER BY l.created_at DESC
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
            f"SELECT COUNT(*) AS total_logs, MIN(created_at) AS first_log_at, MAX(created_at) AS last_log_at FROM logs {where}",
            params,
        ).fetchone()
        return dict(row) if row else {"total_logs": 0, "first_log_at": None, "last_log_at": None}

    def update_tokens_from_usage(
        self,
        account_id: str,
        gateway_id: str,
        log_id: str,
        input_tokens: int | None,
        output_tokens: int | None,
    ) -> None:
        """Backfill ``logs.tokens_in/out`` with parsed usage values when missing or zero."""

        self.conn.execute(
            """
            UPDATE logs
            SET
                tokens_in  = COALESCE(NULLIF(tokens_in, 0), ?),
                tokens_out = COALESCE(NULLIF(tokens_out, 0), ?),
                synced_at  = ?
            WHERE account_id=? AND gateway_id=? AND log_id=?
            """,
            (input_tokens, output_tokens, utc_now(), account_id, gateway_id, log_id),
        )


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
