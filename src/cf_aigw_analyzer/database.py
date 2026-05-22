"""SQLite repository for AI Gateway logs and usage."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Iterable

from .filters import parse_datetime
from .usage import UsageFields, as_int

SCHEMA_VERSION = 2
BODY_FIELD_KEYS = {
    "request",
    "response",
    "request_body",
    "response_body",
    "_request_content",
    "_response_content",
}


def utc_now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def as_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def as_bool_int(value: Any) -> int | None:
    if value is None:
        return None
    return 1 if bool(value) else 0


def json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def sanitize_log_metadata(value: Any) -> Any:
    """Remove request/response body-like values before storing metadata."""

    if isinstance(value, dict):
        return {
            key: sanitize_log_metadata(child)
            for key, child in value.items()
            if key not in BODY_FIELD_KEYS
        }
    if isinstance(value, list):
        return [sanitize_log_metadata(item) for item in value]
    return value


def log_detail_json(log: dict[str, Any]) -> str:
    """Serialize log metadata without request/response body values."""

    return json_dumps(sanitize_log_metadata(log))


def compute_log_metrics(log: dict[str, Any]) -> dict[str, float | int | None]:
    """Compute per-log derived metrics for the 1:1 metrics table."""

    timings = log.get("timings") if isinstance(log.get("timings"), dict) else {}
    duration_ms = as_float(log.get("duration"))
    total_ms = as_float(log.get("_total_ms")) or as_float(timings.get("total")) or duration_ms
    latency_ms = as_float(log.get("_latency_ms")) or as_float(timings.get("latency"))
    generation_ms = as_float(log.get("_generation_ms"))
    if generation_ms is None and total_ms is not None and latency_ms is not None:
        generation_ms = max(total_ms - latency_ms, 0.0)

    output_tokens = as_float(log.get("tokens_out"))
    reasoning_tokens = as_float(log.get("_reasoning_tokens"))
    output_tps = as_float(log.get("_output_tps"))
    ms_per_output_token = None
    if generation_ms and output_tokens and output_tokens > 0:
        output_tps = output_tps if output_tps is not None else output_tokens / (generation_ms / 1000)
        ms_per_output_token = generation_ms / output_tokens

    visible_output_tokens = None
    visible_output_tps = None
    if output_tokens is not None and reasoning_tokens is not None:
        visible_output_tokens = int(max(output_tokens - reasoning_tokens, 0))
        if generation_ms and generation_ms > 0:
            visible_output_tps = visible_output_tokens / (generation_ms / 1000)

    return {
        "duration_ms": duration_ms,
        "latency_ms": latency_ms,
        "total_ms": total_ms,
        "generation_ms": generation_ms,
        "output_tps": output_tps,
        "ms_per_output_token": ms_per_output_token,
        "visible_output_tokens": visible_output_tokens,
        "visible_output_tps": visible_output_tps,
    }


class AnalyzerDatabase:
    """Thin SQLite repository with explicit account/gateway scoping."""

    def __init__(self, path: str | Path):
        self.path = Path(path).expanduser().resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self._initialize()

    def __enter__(self) -> "AnalyzerDatabase":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def close(self) -> None:
        self.conn.close()

    def _initialize(self) -> None:
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA busy_timeout=5000")
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS gateways (
                account_id TEXT NOT NULL,
                gateway_id TEXT NOT NULL,
                name TEXT,
                collect_logs INTEGER,
                raw_json TEXT NOT NULL,
                fetched_at TEXT NOT NULL,
                PRIMARY KEY (account_id, gateway_id)
            );

            CREATE TABLE IF NOT EXISTS logs (
                account_id TEXT NOT NULL,
                gateway_id TEXT NOT NULL,
                log_id TEXT NOT NULL,
                created_at TEXT,
                provider TEXT,
                model TEXT,
                model_type TEXT,
                success INTEGER,
                cached INTEGER,
                status_code INTEGER,
                cost_usd REAL,
                tokens_in INTEGER,
                tokens_out INTEGER,
                raw_json TEXT NOT NULL,
                synced_at TEXT NOT NULL,
                PRIMARY KEY (account_id, gateway_id, log_id)
            );

            CREATE TABLE IF NOT EXISTS log_metrics (
                account_id TEXT NOT NULL,
                gateway_id TEXT NOT NULL,
                log_id TEXT NOT NULL,
                duration_ms REAL,
                latency_ms REAL,
                total_ms REAL,
                generation_ms REAL,
                output_tps REAL,
                ms_per_output_token REAL,
                visible_output_tokens INTEGER,
                visible_output_tps REAL,
                computed_at TEXT NOT NULL,
                PRIMARY KEY (account_id, gateway_id, log_id),
                FOREIGN KEY (account_id, gateway_id, log_id)
                    REFERENCES logs(account_id, gateway_id, log_id)
                    ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS log_usage (
                account_id TEXT NOT NULL,
                gateway_id TEXT NOT NULL,
                log_id TEXT NOT NULL,
                input_tokens INTEGER,
                output_tokens INTEGER,
                total_tokens INTEGER,
                cached_tokens INTEGER,
                reasoning_tokens INTEGER,
                cache_write_tokens INTEGER,
                source TEXT,
                fetch_status TEXT NOT NULL,
                http_status_code INTEGER,
                error_message TEXT,
                fetched_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (account_id, gateway_id, log_id),
                FOREIGN KEY (account_id, gateway_id, log_id)
                    REFERENCES logs(account_id, gateway_id, log_id)
                    ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS sync_runs (
                run_id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id TEXT,
                gateway_id TEXT,
                mode TEXT NOT NULL,
                params_json TEXT,
                logs_count INTEGER NOT NULL DEFAULT 0,
                usage_fetched INTEGER NOT NULL DEFAULT 0,
                usage_parsed INTEGER NOT NULL DEFAULT 0,
                usage_no_usage INTEGER NOT NULL DEFAULT 0,
                usage_failed INTEGER NOT NULL DEFAULT 0,
                started_at TEXT NOT NULL,
                finished_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_logs_scope_time
                ON logs(account_id, gateway_id, created_at);
            CREATE INDEX IF NOT EXISTS idx_logs_provider_model
                ON logs(account_id, gateway_id, provider, model);
            CREATE INDEX IF NOT EXISTS idx_usage_scope_status
                ON log_usage(account_id, gateway_id, fetch_status);
            CREATE INDEX IF NOT EXISTS idx_metrics_scope
                ON log_metrics(account_id, gateway_id);
            """
        )
        self.conn.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
        self.conn.commit()

    def upsert_gateways(self, account_id: str, gateways: Iterable[dict[str, Any]]) -> int:
        now = utc_now()
        count = 0
        with self.conn:
            for gateway in gateways:
                gateway_id = gateway.get("id") or gateway.get("gateway_id")
                if not gateway_id:
                    continue
                self.conn.execute(
                    """
                    INSERT INTO gateways (
                        account_id, gateway_id, name, collect_logs, raw_json, fetched_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(account_id, gateway_id) DO UPDATE SET
                        name=excluded.name,
                        collect_logs=excluded.collect_logs,
                        raw_json=excluded.raw_json,
                        fetched_at=excluded.fetched_at
                    """,
                    (
                        account_id,
                        str(gateway_id),
                        gateway.get("name"),
                        as_bool_int(gateway.get("collect_logs")),
                        json_dumps(gateway),
                        now,
                    ),
                )
                count += 1
        return count

    def upsert_logs(self, account_id: str, gateway_id: str, logs: Iterable[dict[str, Any]]) -> int:
        now = utc_now()
        count = 0
        with self.conn:
            for log in logs:
                log_id = log.get("id") or log.get("log_id")
                if not log_id:
                    continue
                metrics = compute_log_metrics(log)

                self.conn.execute(
                    """
                    INSERT INTO logs (
                        account_id, gateway_id, log_id, created_at, provider, model,
                        model_type, success, cached, status_code, cost_usd,
                        tokens_in, tokens_out, raw_json, synced_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                        raw_json=excluded.raw_json,
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
                        as_bool_int(log.get("success")),
                        as_bool_int(log.get("cached")),
                        as_int(log.get("status_code")),
                        as_float(log.get("cost")),
                        as_int(log.get("tokens_in")),
                        as_int(log.get("tokens_out")),
                        log_detail_json(log),
                        now,
                    ),
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
                        metrics["duration_ms"],
                        metrics["latency_ms"],
                        metrics["total_ms"],
                        metrics["generation_ms"],
                        metrics["output_tps"],
                        metrics["ms_per_output_token"],
                        metrics["visible_output_tokens"],
                        metrics["visible_output_tps"],
                        now,
                    ),
                )
                count += 1
        return count

    def upsert_usage(
        self,
        account_id: str,
        gateway_id: str,
        log_id: str,
        usage: UsageFields,
        fetch_status: str,
        http_status_code: int | None,
        error_message: str | None,
        fill_log_tokens: bool = True,
    ) -> None:
        now = utc_now()
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO log_usage (
                    account_id, gateway_id, log_id,
                    input_tokens, output_tokens, total_tokens, cached_tokens,
                    reasoning_tokens, cache_write_tokens, source, fetch_status,
                    http_status_code, error_message, fetched_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(account_id, gateway_id, log_id) DO UPDATE SET
                    input_tokens=excluded.input_tokens,
                    output_tokens=excluded.output_tokens,
                    total_tokens=excluded.total_tokens,
                    cached_tokens=excluded.cached_tokens,
                    reasoning_tokens=excluded.reasoning_tokens,
                    cache_write_tokens=excluded.cache_write_tokens,
                    source=excluded.source,
                    fetch_status=excluded.fetch_status,
                    http_status_code=excluded.http_status_code,
                    error_message=excluded.error_message,
                    fetched_at=excluded.fetched_at,
                    updated_at=excluded.updated_at
                """,
                (
                    account_id,
                    gateway_id,
                    log_id,
                    usage.input_tokens,
                    usage.output_tokens,
                    usage.total_tokens,
                    usage.cached_tokens,
                    usage.reasoning_tokens,
                    usage.cache_write_tokens,
                    usage.source,
                    fetch_status,
                    http_status_code,
                    error_message,
                    now,
                    now,
                ),
            )
            if fill_log_tokens:
                self.conn.execute(
                    """
                    UPDATE logs
                    SET
                        tokens_in=COALESCE(NULLIF(tokens_in, 0), ?),
                        tokens_out=COALESCE(NULLIF(tokens_out, 0), ?),
                        synced_at=?
                    WHERE account_id=? AND gateway_id=? AND log_id=?
                    """,
                    (usage.input_tokens, usage.output_tokens, now, account_id, gateway_id, log_id),
                )
            self._refresh_usage_dependent_metrics(account_id, gateway_id, log_id, usage, now)

    def _refresh_usage_dependent_metrics(
        self,
        account_id: str,
        gateway_id: str,
        log_id: str,
        usage: UsageFields,
        computed_at: str,
    ) -> None:
        row = self.conn.execute(
            """
            SELECT l.tokens_out, m.generation_ms
            FROM logs l
            LEFT JOIN log_metrics m
              ON l.account_id = m.account_id
             AND l.gateway_id = m.gateway_id
             AND l.log_id = m.log_id
            WHERE l.account_id=? AND l.gateway_id=? AND l.log_id=?
            """,
            (account_id, gateway_id, log_id),
        ).fetchone()
        if not row:
            return

        output_tokens = as_float(row["tokens_out"] if row["tokens_out"] is not None else usage.output_tokens)
        generation_ms = as_float(row["generation_ms"])
        reasoning_tokens = as_float(usage.reasoning_tokens)

        output_tps = None
        ms_per_output_token = None
        if output_tokens and generation_ms and generation_ms > 0:
            output_tps = output_tokens / (generation_ms / 1000)
            ms_per_output_token = generation_ms / output_tokens

        visible_output_tokens = None
        visible_output_tps = None
        if output_tokens is not None and reasoning_tokens is not None:
            visible_output_tokens = int(max(output_tokens - reasoning_tokens, 0))
            if generation_ms and generation_ms > 0:
                visible_output_tps = visible_output_tokens / (generation_ms / 1000)

        self.conn.execute(
            """
            UPDATE log_metrics
            SET
                output_tps=COALESCE(?, output_tps),
                ms_per_output_token=COALESCE(?, ms_per_output_token),
                visible_output_tokens=COALESCE(?, visible_output_tokens),
                visible_output_tps=COALESCE(?, visible_output_tps),
                computed_at=?
            WHERE account_id=? AND gateway_id=? AND log_id=?
            """,
            (
                output_tps,
                ms_per_output_token,
                visible_output_tokens,
                visible_output_tps,
                computed_at,
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
            WHERE {' AND '.join(clauses)}
            ORDER BY l.created_at DESC
        """
        if limit:
            sql += " LIMIT ?"
            params.append(limit)

        rows = self.conn.execute(sql, params).fetchall()
        return [str(row["log_id"]) for row in rows]

    def resolve_gateway_id(self, account_id: str, gateway_name_or_id: str) -> str | None:
        row = self.conn.execute(
            """
            SELECT gateway_id
            FROM gateways
            WHERE account_id=? AND (gateway_id=? OR name=?)
            ORDER BY CASE WHEN gateway_id=? THEN 0 ELSE 1 END
            LIMIT 1
            """,
            (account_id, gateway_name_or_id, gateway_name_or_id, gateway_name_or_id),
        ).fetchone()
        return str(row["gateway_id"]) if row else None

    def query_logs(
        self,
        account_id: str,
        gateway_id: str,
        start_date: str | None = None,
        end_date: str | None = None,
        provider: str | None = None,
        model: str | None = None,
        model_type: str | None = None,
        success: bool | None = None,
        cached: bool | None = None,
        search: str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        clauses = ["l.account_id = ?", "l.gateway_id = ?"]
        params: list[Any] = [account_id, gateway_id]

        if start_date:
            clauses.append("l.created_at >= ?")
            params.append(parse_datetime(start_date))
        if end_date:
            clauses.append("l.created_at <= ?")
            params.append(parse_datetime(end_date))
        if provider:
            clauses.append("l.provider = ?")
            params.append(provider)
        if model:
            clauses.append("l.model = ?")
            params.append(model)
        if model_type:
            clauses.append("l.model_type = ?")
            params.append(model_type)
        if success is not None:
            clauses.append("l.success = ?")
            params.append(as_bool_int(success))
        if cached is not None:
            clauses.append("l.cached = ?")
            params.append(as_bool_int(cached))
        if search:
            clauses.append("l.raw_json LIKE ?")
            params.append(f"%{search}%")

        sql = f"""
            SELECT
                l.*,
                u.input_tokens AS usage_input_tokens,
                u.output_tokens AS usage_output_tokens,
                u.total_tokens AS usage_total_tokens,
                u.cached_tokens AS usage_cached_tokens,
                u.reasoning_tokens AS usage_reasoning_tokens,
                u.cache_write_tokens AS usage_cache_write_tokens,
                u.source AS usage_source,
                u.fetch_status AS usage_fetch_status,
                u.error_message AS usage_error_message,
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
            WHERE {' AND '.join(clauses)}
            ORDER BY l.created_at DESC
        """
        if limit:
            sql += " LIMIT ?"
            params.append(limit)

        rows = self.conn.execute(sql, params).fetchall()
        return [dict(row) for row in rows]

    def summary(self, account_id: str | None = None, gateway_id: str | None = None) -> dict[str, Any]:
        clauses: list[str] = []
        params: list[Any] = []
        if account_id:
            clauses.append("account_id = ?")
            params.append(account_id)
        if gateway_id:
            clauses.append("gateway_id = ?")
            params.append(gateway_id)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""

        logs = self.conn.execute(
            f"""
            SELECT COUNT(*) AS total_logs, MIN(created_at) AS first_log_at, MAX(created_at) AS last_log_at
            FROM logs
            {where}
            """,
            params,
        ).fetchone()

        usage_where = where
        usage_rows = self.conn.execute(
            f"""
            SELECT fetch_status, COUNT(*) AS count
            FROM log_usage
            {usage_where}
            GROUP BY fetch_status
            """,
            params,
        ).fetchall()
        usage_counts = {row["fetch_status"]: row["count"] for row in usage_rows}

        run_clauses = list(clauses)
        run_params = list(params)
        run_where = f"WHERE {' AND '.join(run_clauses)}" if run_clauses else ""
        last_run = self.conn.execute(
            f"""
            SELECT mode, logs_count, usage_fetched, usage_parsed, usage_failed, finished_at
            FROM sync_runs
            {run_where}
            ORDER BY run_id DESC
            LIMIT 1
            """,
            run_params,
        ).fetchone()

        return {
            "database": str(self.path),
            "database_bytes": self.path.stat().st_size if self.path.exists() else 0,
            "total_logs": logs["total_logs"],
            "first_log_at": logs["first_log_at"],
            "last_log_at": logs["last_log_at"],
            "usage_parsed": usage_counts.get("parsed", 0),
            "usage_no_usage": usage_counts.get("no_usage", 0),
            "usage_failed": usage_counts.get("failed", 0),
            "last_run": dict(last_run) if last_run else None,
        }

    def record_run(
        self,
        account_id: str | None,
        gateway_id: str | None,
        mode: str,
        params: dict[str, Any] | None,
        logs_count: int = 0,
        usage_fetched: int = 0,
        usage_parsed: int = 0,
        usage_no_usage: int = 0,
        usage_failed: int = 0,
        started_at: str | None = None,
    ) -> None:
        finished_at = utc_now()
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO sync_runs (
                    account_id, gateway_id, mode, params_json, logs_count,
                    usage_fetched, usage_parsed, usage_no_usage, usage_failed,
                    started_at, finished_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    account_id,
                    gateway_id,
                    mode,
                    json_dumps(params or {}),
                    logs_count,
                    usage_fetched,
                    usage_parsed,
                    usage_no_usage,
                    usage_failed,
                    started_at or finished_at,
                    finished_at,
                ),
            )

    def vacuum(self) -> None:
        self.conn.execute("VACUUM")
