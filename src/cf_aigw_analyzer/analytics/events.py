"""Recent events listing (capped to keep the payload small)."""

from __future__ import annotations

import sqlite3
from typing import Any

from cf_aigw_analyzer.analytics.queries import AnalyticsFilters, build_where


def build_recent_events(
    conn: sqlite3.Connection,
    filters: AnalyticsFilters,
    *,
    limit: int = 500,
) -> list[dict[str, Any]]:
    safe_limit = max(1, min(limit, 5_000))
    where, params = build_where(filters)
    sql = f"""
        SELECT
            l.log_id,
            l.created_at,
            l.provider,
            l.model,
            l.model_type,
            l.success,
            l.cached,
            l.status_code,
            COALESCE(u.input_tokens, l.tokens_in)   AS input_tokens,
            COALESCE(u.output_tokens, l.tokens_out) AS output_tokens,
            COALESCE(u.total_tokens,
                COALESCE(u.input_tokens, l.tokens_in, 0) +
                COALESCE(u.output_tokens, l.tokens_out, 0)) AS total_tokens,
            u.cached_tokens,
            u.reasoning_tokens,
            u.fetch_status AS usage_fetch_status,
            m.duration_ms,
            m.latency_ms,
            m.total_ms,
            m.generation_ms,
            m.output_tps,
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
        {where}
        ORDER BY l.created_at DESC
        LIMIT ?
    """
    rows = conn.execute(sql, [*params, safe_limit]).fetchall()
    return [_normalize(dict(row)) for row in rows]


def _normalize(row: dict[str, Any]) -> dict[str, Any]:
    if row.get("success") is not None:
        row["success"] = bool(row["success"])
    if row.get("cached") is not None:
        row["cached"] = bool(row["cached"])
    return row
