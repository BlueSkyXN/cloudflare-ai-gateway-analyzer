"""Scope-level summary aggregations (counts, percentiles, tokens, cache ratio)."""

from __future__ import annotations

import sqlite3
from typing import Any

from cf_aigw_analyzer.analytics.queries import AnalyticsFilters, build_where


def build_summary(conn: sqlite3.Connection, filters: AnalyticsFilters) -> dict[str, Any]:
    where, params = build_where(filters)
    base_join = f"""
        FROM logs l
        LEFT JOIN log_usage u
          ON l.account_id = u.account_id
         AND l.gateway_id = u.gateway_id
         AND l.log_id = u.log_id
        LEFT JOIN log_metrics m
          ON l.account_id = m.account_id
         AND l.gateway_id = m.gateway_id
         AND l.log_id = m.log_id
        {where}
    """

    aggregates = conn.execute(
        f"""
        SELECT
            COUNT(*) AS requests,
            SUM(CASE WHEN l.success = 1 THEN 1 ELSE 0 END) AS success_count,
            SUM(CASE WHEN l.success = 0 THEN 1 ELSE 0 END) AS failed_count,
            COUNT(DISTINCT l.model)    AS model_count,
            COUNT(DISTINCT l.provider) AS provider_count,
            MIN(l.created_at) AS first_log_at,
            MAX(l.created_at) AS last_log_at,
            SUM(COALESCE(u.input_tokens, l.tokens_in, 0))   AS input_tokens,
            SUM(COALESCE(u.output_tokens, l.tokens_out, 0)) AS output_tokens,
            SUM(COALESCE(u.total_tokens,
                COALESCE(u.input_tokens, l.tokens_in, 0) +
                COALESCE(u.output_tokens, l.tokens_out, 0), 0)) AS total_tokens,
            SUM(COALESCE(u.cached_tokens, 0))    AS cached_tokens,
            SUM(COALESCE(u.reasoning_tokens, 0)) AS reasoning_tokens,
            AVG(m.total_ms)                 AS avg_total_ms,
            AVG(m.latency_ms)               AS avg_latency_ms,
            AVG(m.output_tps)               AS avg_output_tps,
            AVG(m.visible_output_tps)       AS avg_visible_output_tps
        {base_join}
        """,
        params,
    ).fetchone()

    percentiles = _percentiles(conn, base_join, params, "m.total_ms", (0.5, 0.95, 0.99))

    statuses_rows = conn.execute(
        f"""
        SELECT COALESCE(u.fetch_status, 'missing') AS status, COUNT(*) AS n
        {base_join}
        GROUP BY COALESCE(u.fetch_status, 'missing')
        """,
        params,
    ).fetchall()
    usage_statuses = {row["status"]: int(row["n"]) for row in statuses_rows}

    requests = int(aggregates["requests"] or 0)
    success_count = int(aggregates["success_count"] or 0)
    failed_count = int(aggregates["failed_count"] or 0)
    input_tokens = int(aggregates["input_tokens"] or 0)
    output_tokens = int(aggregates["output_tokens"] or 0)
    total_tokens = int(aggregates["total_tokens"] or 0)
    cached_tokens = int(aggregates["cached_tokens"] or 0)
    reasoning_tokens = int(aggregates["reasoning_tokens"] or 0)

    return {
        "requests": requests,
        "success_count": success_count,
        "failed_count": failed_count,
        "success_rate": _safe_div(success_count, requests),
        "models": int(aggregates["model_count"] or 0),
        "providers": int(aggregates["provider_count"] or 0),
        "first_log_at": aggregates["first_log_at"],
        "last_log_at": aggregates["last_log_at"],
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "cached_tokens": cached_tokens,
        "reasoning_tokens": reasoning_tokens,
        "cache_ratio": _safe_div(cached_tokens, input_tokens),
        "avg_total_ms": _maybe_float(aggregates["avg_total_ms"]),
        "p50_total_ms": percentiles[0],
        "p95_total_ms": percentiles[1],
        "p99_total_ms": percentiles[2],
        "avg_latency_ms": _maybe_float(aggregates["avg_latency_ms"]),
        "avg_output_tps": _maybe_float(aggregates["avg_output_tps"]),
        "avg_visible_output_tps": _maybe_float(aggregates["avg_visible_output_tps"]),
        "usage_statuses": usage_statuses,
    }


def _percentiles(
    conn: sqlite3.Connection,
    base_join: str,
    params: list[Any],
    column: str,
    quantiles: tuple[float, ...],
) -> tuple[float | None, ...]:
    """Order-by + offset based percentile (acceptable for analyzer scale)."""

    total_row = (
        conn.execute(
            f"SELECT COUNT(*) AS n {base_join} AND {column} IS NOT NULL",
            params,
        ).fetchone()
        if "WHERE" in base_join
        else conn.execute(
            f"SELECT COUNT(*) AS n {base_join} WHERE {column} IS NOT NULL",
            params,
        ).fetchone()
    )

    total = int(total_row["n"] or 0)
    if total == 0:
        return tuple(None for _ in quantiles)

    sorted_join = base_join
    if "WHERE" in sorted_join:
        sorted_join = f"{sorted_join} AND {column} IS NOT NULL"
    else:
        sorted_join = f"{sorted_join} WHERE {column} IS NOT NULL"
    results: list[float | None] = []
    for quantile in quantiles:
        index = max(0, min(total - 1, int((total - 1) * quantile)))
        row = conn.execute(
            f"SELECT {column} AS value {sorted_join} ORDER BY {column} ASC LIMIT 1 OFFSET ?",
            [*params, index],
        ).fetchone()
        results.append(_maybe_float(row["value"]) if row else None)
    return tuple(results)


def _safe_div(numerator: int | float | None, denominator: int | float | None) -> float | None:
    if numerator is None or denominator in (None, 0):
        return None
    return float(numerator) / float(denominator)


def _maybe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
