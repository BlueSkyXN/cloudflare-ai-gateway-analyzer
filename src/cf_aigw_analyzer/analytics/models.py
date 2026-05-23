"""Model-level aggregation."""

from __future__ import annotations

import sqlite3
from typing import Any

from cf_aigw_analyzer.analytics.queries import AnalyticsFilters, build_where


def build_model_stats(conn: sqlite3.Connection, filters: AnalyticsFilters) -> list[dict[str, Any]]:
    where, params = build_where(filters)
    sql = f"""
        SELECT
            COALESCE(l.model, '(unknown)') AS model,
            GROUP_CONCAT(DISTINCT COALESCE(l.provider, '(unknown)')) AS providers,
            COUNT(*) AS requests,
            SUM(CASE WHEN l.success = 1 THEN 1 ELSE 0 END) AS success_count,
            SUM(COALESCE(u.input_tokens, l.tokens_in, 0))   AS input_tokens,
            SUM(COALESCE(u.output_tokens, l.tokens_out, 0)) AS output_tokens,
            SUM(COALESCE(u.total_tokens,
                COALESCE(u.input_tokens, l.tokens_in, 0) +
                COALESCE(u.output_tokens, l.tokens_out, 0), 0)) AS total_tokens,
            SUM(COALESCE(u.cached_tokens, 0))    AS cached_tokens,
            SUM(COALESCE(u.reasoning_tokens, 0)) AS reasoning_tokens,
            AVG(m.total_ms)              AS avg_total_ms,
            AVG(m.output_tps)            AS avg_output_tps,
            AVG(m.visible_output_tps)    AS avg_visible_output_tps,
            AVG(COALESCE(u.input_tokens, l.tokens_in))   AS avg_input_tokens,
            AVG(COALESCE(u.output_tokens, l.tokens_out)) AS avg_output_tokens
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
        GROUP BY COALESCE(l.model, '(unknown)')
        ORDER BY requests DESC
    """
    rows = conn.execute(sql, params).fetchall()
    output: list[dict[str, Any]] = []
    for row in rows:
        requests = int(row["requests"] or 0)
        success_count = int(row["success_count"] or 0)
        input_tokens = int(row["input_tokens"] or 0)
        cached_tokens = int(row["cached_tokens"] or 0)
        total_tokens = int(row["total_tokens"] or 0)
        output.append(
            {
                "model": row["model"],
                "providers": _split_unique(row["providers"]),
                "requests": requests,
                "success_count": success_count,
                "success_rate": _safe_div(success_count, requests),
                "input_tokens": input_tokens,
                "output_tokens": int(row["output_tokens"] or 0),
                "total_tokens": total_tokens,
                "cached_tokens": cached_tokens,
                "reasoning_tokens": int(row["reasoning_tokens"] or 0),
                "cache_ratio": _safe_div(cached_tokens, input_tokens),
                "tokens_per_request": _safe_div(total_tokens, requests),
                "avg_input_tokens": _maybe_float(row["avg_input_tokens"]),
                "avg_output_tokens": _maybe_float(row["avg_output_tokens"]),
                "avg_total_ms": _maybe_float(row["avg_total_ms"]),
                "avg_output_tps": _maybe_float(row["avg_output_tps"]),
                "avg_visible_output_tps": _maybe_float(row["avg_visible_output_tps"]),
            }
        )
    # Compute p95 per model only for the top N to keep cost bounded.
    top = output[:25]
    if top:
        for item in top:
            item["p95_total_ms"] = _p95_for_model(conn, filters, item["model"])
    return output


def _p95_for_model(
    conn: sqlite3.Connection,
    filters: AnalyticsFilters,
    model: str,
) -> float | None:
    where, params = build_where(filters)
    if where:
        where += " AND l.model = ? AND m.total_ms IS NOT NULL"
    else:
        where = "WHERE l.model = ? AND m.total_ms IS NOT NULL"
    params.append(model if model != "(unknown)" else None)
    if model == "(unknown)":
        where = where.replace("l.model = ?", "l.model IS NULL")
        params.pop()

    sql_count = f"""
        SELECT COUNT(*) AS n
        FROM logs l
        LEFT JOIN log_metrics m
          ON l.account_id = m.account_id
         AND l.gateway_id = m.gateway_id
         AND l.log_id = m.log_id
        {where}
    """
    total_row = conn.execute(sql_count, params).fetchone()
    total = int(total_row["n"] or 0)
    if total == 0:
        return None
    index = max(0, min(total - 1, int((total - 1) * 0.95)))
    sql_value = f"""
        SELECT m.total_ms AS value
        FROM logs l
        LEFT JOIN log_metrics m
          ON l.account_id = m.account_id
         AND l.gateway_id = m.gateway_id
         AND l.log_id = m.log_id
        {where}
        ORDER BY m.total_ms ASC
        LIMIT 1 OFFSET ?
    """
    row = conn.execute(sql_value, [*params, index]).fetchone()
    return _maybe_float(row["value"]) if row else None


def _split_unique(value: Any) -> list[str]:
    if not value:
        return []
    return sorted({part for part in str(value).split(",") if part})


def _maybe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_div(num: int | float | None, denom: int | float | None) -> float | None:
    if num is None or denom in (None, 0):
        return None
    return float(num) / float(denom)
