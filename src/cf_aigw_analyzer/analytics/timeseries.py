"""Hourly time-series aggregation."""

from __future__ import annotations

import sqlite3
from typing import Any

from cf_aigw_analyzer.analytics.queries import AnalyticsFilters, build_where


def build_timeseries(conn: sqlite3.Connection, filters: AnalyticsFilters) -> list[dict[str, Any]]:
    where, params = build_where(filters)
    sql = f"""
        SELECT
            substr(l.created_at, 1, 13) || ':00:00Z' AS hour,
            COUNT(*) AS requests,
            SUM(CASE WHEN l.success = 1 THEN 1 ELSE 0 END) AS success_count,
            SUM(COALESCE(u.input_tokens, l.tokens_in, 0))   AS input_tokens,
            SUM(COALESCE(u.output_tokens, l.tokens_out, 0)) AS output_tokens,
            SUM(COALESCE(u.total_tokens,
                COALESCE(u.input_tokens, l.tokens_in, 0) +
                COALESCE(u.output_tokens, l.tokens_out, 0), 0)) AS total_tokens,
            AVG(m.total_ms)              AS avg_total_ms,
            AVG(m.latency_ms)            AS avg_latency_ms,
            AVG(m.output_tps)            AS avg_output_tps,
            AVG(m.visible_output_tps)    AS avg_visible_output_tps
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
        GROUP BY substr(l.created_at, 1, 13)
        ORDER BY hour ASC
    """
    rows = conn.execute(sql, params).fetchall()
    output: list[dict[str, Any]] = []
    for row in rows:
        requests = int(row["requests"] or 0)
        total_tokens = int(row["total_tokens"] or 0)
        output.append(
            {
                "hour": row["hour"],
                "requests": requests,
                "success_count": int(row["success_count"] or 0),
                "input_tokens": int(row["input_tokens"] or 0),
                "output_tokens": int(row["output_tokens"] or 0),
                "total_tokens": total_tokens,
                "rpm": requests / 60.0,
                "tpm": total_tokens / 60.0,
                "avg_total_ms": _maybe_float(row["avg_total_ms"]),
                "avg_latency_ms": _maybe_float(row["avg_latency_ms"]),
                "avg_output_tps": _maybe_float(row["avg_output_tps"]),
                "avg_visible_output_tps": _maybe_float(row["avg_visible_output_tps"]),
            }
        )
    return output


def _maybe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
