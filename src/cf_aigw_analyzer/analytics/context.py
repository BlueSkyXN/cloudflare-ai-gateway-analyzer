"""Context-length bucket aggregation."""

from __future__ import annotations

import sqlite3
from typing import Any

from cf_aigw_analyzer.analytics.queries import AnalyticsFilters, build_where

# (label, min_inclusive, max_exclusive)
BUCKETS: tuple[tuple[str, int | None, int | None], ...] = (
    ("<1k", None, 1_000),
    ("1k-10k", 1_000, 10_000),
    ("10k-100k", 10_000, 100_000),
    ("100k-500k", 100_000, 500_000),
    ("500k+", 500_000, None),
)


def build_context_buckets(
    conn: sqlite3.Connection, filters: AnalyticsFilters
) -> list[dict[str, Any]]:
    where, params = build_where(filters)
    cases = "CASE\n"
    for label, lo, hi in BUCKETS:
        conds: list[str] = ["input_tokens IS NOT NULL"]
        if lo is not None:
            conds.append(f"input_tokens >= {lo}")
        if hi is not None:
            conds.append(f"input_tokens < {hi}")
        cases += f"  WHEN {' AND '.join(conds)} THEN '{label}'\n"
    cases += "  ELSE 'unknown'\nEND"

    sql = f"""
        WITH joined AS (
            SELECT
                l.success,
                COALESCE(u.input_tokens, l.tokens_in) AS input_tokens,
                COALESCE(u.output_tokens, l.tokens_out) AS output_tokens,
                COALESCE(u.total_tokens,
                    COALESCE(u.input_tokens, l.tokens_in, 0) +
                    COALESCE(u.output_tokens, l.tokens_out, 0)) AS total_tokens,
                COALESCE(u.cached_tokens, 0) AS cached_tokens,
                m.total_ms,
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
        )
        SELECT
            {cases} AS bucket,
            COUNT(*) AS requests,
            SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) AS success_count,
            AVG(input_tokens)  AS avg_input_tokens,
            AVG(output_tokens) AS avg_output_tokens,
            SUM(total_tokens)  AS total_tokens,
            SUM(cached_tokens) AS cached_tokens,
            SUM(COALESCE(input_tokens, 0)) AS input_tokens_sum,
            AVG(total_ms)              AS avg_total_ms,
            AVG(output_tps)            AS avg_output_tps,
            AVG(visible_output_tps)    AS avg_visible_output_tps
        FROM joined
        GROUP BY bucket
    """
    rows = conn.execute(sql, params).fetchall()

    by_label: dict[str, dict[str, Any]] = {}
    for row in rows:
        label = row["bucket"]
        if not label:
            continue
        requests = int(row["requests"] or 0)
        cached = int(row["cached_tokens"] or 0)
        input_sum = int(row["input_tokens_sum"] or 0)
        success_count = int(row["success_count"] or 0)
        by_label[label] = {
            "context_bucket": label,
            "requests": requests,
            "success_count": success_count,
            "success_rate": _safe_div(success_count, requests),
            "avg_input_tokens": _maybe_float(row["avg_input_tokens"]),
            "avg_output_tokens": _maybe_float(row["avg_output_tokens"]),
            "total_tokens": int(row["total_tokens"] or 0),
            "cached_tokens": cached,
            "cache_ratio": _safe_div(cached, input_sum),
            "avg_total_ms": _maybe_float(row["avg_total_ms"]),
            "avg_output_tps": _maybe_float(row["avg_output_tps"]),
            "avg_visible_output_tps": _maybe_float(row["avg_visible_output_tps"]),
        }

    ordered_labels = [label for label, _, _ in BUCKETS] + ["unknown"]
    return [by_label[label] for label in ordered_labels if label in by_label]


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
