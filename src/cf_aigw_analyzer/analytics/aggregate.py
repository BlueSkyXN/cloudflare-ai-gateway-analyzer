"""Unified analytics payload over the log_events fact table."""

from __future__ import annotations

import sqlite3
from typing import Any

from cf_aigw_analyzer.analytics.queries import AnalyticsFilters, build_where, list_gateway_scopes


def build_analytics(
    conn: sqlite3.Connection,
    filters: AnalyticsFilters,
    *,
    limit: int = 500,
) -> dict[str, Any]:
    safe_limit = max(1, min(limit, 5_000))
    return {
        "summary": build_summary(conn, filters),
        "timeseries": build_timeseries(conn, filters),
        "by_provider": build_provider_stats(conn, filters),
        "by_model": build_model_stats(conn, filters),
        "events": build_recent_events(conn, filters, limit=safe_limit),
        "filter_options": build_filter_options(conn, filters),
    }


def build_summary(conn: sqlite3.Connection, filters: AnalyticsFilters) -> dict[str, Any]:
    where, params = build_where(filters)
    base = f"FROM log_events e {where}"
    aggregates = conn.execute(
        f"""
        SELECT
            COUNT(*) AS requests,
            SUM(CASE WHEN e.success = 1 THEN 1 ELSE 0 END) AS success_count,
            SUM(CASE WHEN e.success = 0 THEN 1 ELSE 0 END) AS failed_count,
            COUNT(DISTINCT e.model) AS model_count,
            COUNT(DISTINCT e.provider) AS provider_count,
            MIN(e.created_at) AS first_log_at,
            MAX(e.created_at) AS last_log_at,
            SUM(COALESCE(e.input_tokens, 0)) AS input_tokens,
            SUM(COALESCE(e.output_tokens, 0)) AS output_tokens,
            SUM(COALESCE(e.total_tokens,
                COALESCE(e.input_tokens, 0) + COALESCE(e.output_tokens, 0), 0)) AS total_tokens,
            SUM(COALESCE(e.cached_tokens, 0)) AS cached_tokens,
            SUM(COALESCE(e.reasoning_tokens, 0)) AS reasoning_tokens,
            AVG(e.total_ms) AS avg_total_ms,
            AVG(e.latency_ms) AS avg_latency_ms,
            AVG(e.generation_ms) AS avg_generation_ms,
            AVG(e.input_tps) AS avg_input_tps,
            AVG(e.output_tps) AS avg_output_tps,
            AVG(e.visible_output_tps) AS avg_visible_output_tps
        {base}
        """,
        params,
    ).fetchone()
    statuses = conn.execute(
        f"""
        SELECT COALESCE(e.usage_fetch_status, 'missing') AS status, COUNT(*) AS n
        {base}
        GROUP BY COALESCE(e.usage_fetch_status, 'missing')
        """,
        params,
    ).fetchall()
    percentiles = _percentiles(conn, base, params, "e.total_ms", (0.5, 0.95, 0.99))

    requests = int(aggregates["requests"] or 0)
    success_count = int(aggregates["success_count"] or 0)
    failed_count = int(aggregates["failed_count"] or 0)
    input_tokens = int(aggregates["input_tokens"] or 0)
    cached_tokens = int(aggregates["cached_tokens"] or 0)
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
        "output_tokens": int(aggregates["output_tokens"] or 0),
        "total_tokens": int(aggregates["total_tokens"] or 0),
        "cached_tokens": cached_tokens,
        "reasoning_tokens": int(aggregates["reasoning_tokens"] or 0),
        "cache_ratio": _safe_div(cached_tokens, input_tokens),
        "avg_total_ms": _maybe_float(aggregates["avg_total_ms"]),
        "avg_latency_ms": _maybe_float(aggregates["avg_latency_ms"]),
        "avg_generation_ms": _maybe_float(aggregates["avg_generation_ms"]),
        "p50_total_ms": percentiles[0],
        "p95_total_ms": percentiles[1],
        "p99_total_ms": percentiles[2],
        "avg_input_tps": _maybe_float(aggregates["avg_input_tps"]),
        "avg_output_tps": _maybe_float(aggregates["avg_output_tps"]),
        "avg_visible_output_tps": _maybe_float(aggregates["avg_visible_output_tps"]),
        "usage_statuses": {row["status"]: int(row["n"]) for row in statuses},
    }


def build_timeseries(conn: sqlite3.Connection, filters: AnalyticsFilters) -> list[dict[str, Any]]:
    where, params = build_where(filters)
    bucket_hours = _normalize_bucket_hours(filters.timeseries_bucket_hours)
    bucket_seconds = bucket_hours * 60 * 60
    bucket_expr = """
        REPLACE(
            datetime((CAST(strftime('%s', e.created_at) AS INTEGER) / ?) * ?, 'unixepoch'),
            ' ',
            'T'
        ) || 'Z'
    """
    rows = conn.execute(
        f"""
        SELECT
            e.bucket AS hour,
            COUNT(*) AS requests,
            SUM(CASE WHEN e.success = 1 THEN 1 ELSE 0 END) AS success_count,
            SUM(COALESCE(e.input_tokens, 0)) AS input_tokens,
            SUM(COALESCE(e.output_tokens, 0)) AS output_tokens,
            SUM(COALESCE(e.total_tokens,
                COALESCE(e.input_tokens, 0) + COALESCE(e.output_tokens, 0), 0)) AS total_tokens,
            AVG(e.total_ms) AS avg_total_ms,
            AVG(e.latency_ms) AS avg_latency_ms,
            AVG(e.generation_ms) AS avg_generation_ms,
            AVG(e.input_tps) AS avg_input_tps,
            AVG(e.output_tps) AS avg_output_tps,
            AVG(e.visible_output_tps) AS avg_visible_output_tps
        FROM (
            SELECT e.*, {bucket_expr} AS bucket
            FROM log_events e
            {where}
        ) e
        GROUP BY e.bucket
        ORDER BY hour ASC
        """,
        [bucket_seconds, bucket_seconds, *params],
    ).fetchall()
    bucket_minutes = float(bucket_hours * 60)
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
                "rpm": requests / bucket_minutes,
                "tpm": total_tokens / bucket_minutes,
                "avg_total_ms": _maybe_float(row["avg_total_ms"]),
                "avg_latency_ms": _maybe_float(row["avg_latency_ms"]),
                "avg_generation_ms": _maybe_float(row["avg_generation_ms"]),
                "avg_input_tps": _maybe_float(row["avg_input_tps"]),
                "avg_output_tps": _maybe_float(row["avg_output_tps"]),
                "avg_visible_output_tps": _maybe_float(row["avg_visible_output_tps"]),
            }
        )
    return output


def _normalize_bucket_hours(hours: int | None) -> int:
    if hours in (1, 4, 8, 12, 24):
        return int(hours)
    return 1


def build_provider_stats(
    conn: sqlite3.Connection, filters: AnalyticsFilters
) -> list[dict[str, Any]]:
    return _breakdown(
        conn, filters, key_expr="COALESCE(e.provider, '(unknown)')", key_name="provider"
    )


def build_model_stats(conn: sqlite3.Connection, filters: AnalyticsFilters) -> list[dict[str, Any]]:
    rows = _breakdown(conn, filters, key_expr="COALESCE(e.model, '(unknown)')", key_name="model")
    for row in rows[:25]:
        row["p95_total_ms"] = _p95_for_value(conn, filters, "e.model", row["model"])
    return rows


def _breakdown(
    conn: sqlite3.Connection,
    filters: AnalyticsFilters,
    *,
    key_expr: str,
    key_name: str,
) -> list[dict[str, Any]]:
    where, params = build_where(filters)
    rows = conn.execute(
        f"""
        SELECT
            {key_expr} AS name,
            GROUP_CONCAT(DISTINCT COALESCE(e.provider, '(unknown)')) AS providers,
            COUNT(*) AS requests,
            SUM(CASE WHEN e.success = 1 THEN 1 ELSE 0 END) AS success_count,
            SUM(COALESCE(e.input_tokens, 0)) AS input_tokens,
            SUM(COALESCE(e.output_tokens, 0)) AS output_tokens,
            SUM(COALESCE(e.total_tokens,
                COALESCE(e.input_tokens, 0) + COALESCE(e.output_tokens, 0), 0)) AS total_tokens,
            SUM(COALESCE(e.cached_tokens, 0)) AS cached_tokens,
            SUM(COALESCE(e.reasoning_tokens, 0)) AS reasoning_tokens,
            AVG(e.input_tokens) AS avg_input_tokens,
            AVG(e.output_tokens) AS avg_output_tokens,
            AVG(e.total_ms) AS avg_total_ms,
            AVG(e.latency_ms) AS avg_latency_ms,
            AVG(e.generation_ms) AS avg_generation_ms,
            AVG(e.input_tps) AS avg_input_tps,
            AVG(e.output_tps) AS avg_output_tps,
            AVG(e.visible_output_tps) AS avg_visible_output_tps
        FROM log_events e
        {where}
        GROUP BY {key_expr}
        ORDER BY requests DESC, name ASC
        """,
        params,
    ).fetchall()
    output: list[dict[str, Any]] = []
    for row in rows:
        requests = int(row["requests"] or 0)
        success_count = int(row["success_count"] or 0)
        input_tokens = int(row["input_tokens"] or 0)
        cached_tokens = int(row["cached_tokens"] or 0)
        total_tokens = int(row["total_tokens"] or 0)
        item = {
            key_name: row["name"],
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
            "avg_latency_ms": _maybe_float(row["avg_latency_ms"]),
            "avg_generation_ms": _maybe_float(row["avg_generation_ms"]),
            "avg_input_tps": _maybe_float(row["avg_input_tps"]),
            "avg_output_tps": _maybe_float(row["avg_output_tps"]),
            "avg_visible_output_tps": _maybe_float(row["avg_visible_output_tps"]),
        }
        output.append(item)
    return output


def build_filter_options(conn: sqlite3.Connection, filters: AnalyticsFilters) -> dict[str, Any]:
    where, params = build_where(filters)
    provider_rows = conn.execute(
        f"""
        SELECT e.provider AS provider, COUNT(*) AS requests
        FROM log_events e
        {where}
        {"AND" if where else "WHERE"} e.provider IS NOT NULL AND TRIM(e.provider) != ''
        GROUP BY e.provider
        ORDER BY requests DESC, e.provider ASC
        """,
        params,
    ).fetchall()
    model_rows = conn.execute(
        f"""
        SELECT e.model AS model,
               GROUP_CONCAT(DISTINCT e.provider) AS providers,
               COUNT(*) AS requests
        FROM log_events e
        {where}
        {"AND" if where else "WHERE"} e.model IS NOT NULL AND TRIM(e.model) != ''
        GROUP BY e.model
        ORDER BY requests DESC, e.model ASC
        """,
        params,
    ).fetchall()
    return {
        "providers": [
            {"provider": row["provider"], "requests": int(row["requests"] or 0)}
            for row in provider_rows
        ],
        "models": [
            {
                "model": row["model"],
                "providers": _split_unique(row["providers"]),
                "requests": int(row["requests"] or 0),
            }
            for row in model_rows
        ],
    }


def build_recent_events(
    conn: sqlite3.Connection,
    filters: AnalyticsFilters,
    *,
    limit: int = 500,
) -> list[dict[str, Any]]:
    safe_limit = max(1, min(limit, 5_000))
    where, params = build_where(filters)
    rows = conn.execute(
        f"""
        SELECT
            e.log_id,
            e.created_at,
            e.provider,
            e.model,
            e.model_type,
            e.success,
            e.cached,
            e.status_code,
            e.input_tokens,
            e.output_tokens,
            e.total_tokens,
            e.cached_tokens,
            e.reasoning_tokens,
            e.cache_write_tokens,
            e.cost_usd,
            e.duration_ms,
            e.latency_ms,
            e.total_ms,
            e.generation_ms,
            e.input_tps,
            e.output_tps,
            e.ms_per_output_token,
            e.visible_output_tokens,
            e.visible_output_tps,
            e.usage_fetch_status,
            e.usage_error_message
        FROM log_events e
        {where}
        ORDER BY e.created_at DESC
        LIMIT ?
        """,
        [*params, safe_limit],
    ).fetchall()
    return [_normalize_event(dict(row)) for row in rows]


def build_context_buckets(
    conn: sqlite3.Connection, filters: AnalyticsFilters
) -> list[dict[str, Any]]:
    # Kept as a lightweight compatibility wrapper; the simplified UI no longer uses it.
    _ = conn, filters
    return []


def build_insights(conn: sqlite3.Connection, filters: AnalyticsFilters) -> list[dict[str, str]]:
    summary = build_summary(conn, filters)
    if not summary["requests"]:
        return [{"level": "info", "title": "暂无数据", "detail": "当前筛选条件下没有日志。"}]
    return []


def _p95_for_value(
    conn: sqlite3.Connection, filters: AnalyticsFilters, column: str, value: str
) -> float | None:
    where, params = build_where(filters)
    if value == "(unknown)":
        clause = f"{column} IS NULL"
    else:
        clause = f"{column} = ?"
        params.append(value)
    base = f"FROM log_events e {where} {'AND' if where else 'WHERE'} {clause}"
    return _percentiles(conn, base, params, "e.total_ms", (0.95,))[0]


def _percentiles(
    conn: sqlite3.Connection,
    base_from: str,
    params: list[Any],
    column: str,
    quantiles: tuple[float, ...],
) -> tuple[float | None, ...]:
    filter_sql = f"{base_from} {'AND' if 'WHERE' in base_from else 'WHERE'} {column} IS NOT NULL"
    total_row = conn.execute(f"SELECT COUNT(*) AS n {filter_sql}", params).fetchone()
    total = int(total_row["n"] or 0)
    if total == 0:
        return tuple(None for _ in quantiles)
    output: list[float | None] = []
    for quantile in quantiles:
        index = max(0, min(total - 1, int((total - 1) * quantile)))
        row = conn.execute(
            f"SELECT {column} AS value {filter_sql} ORDER BY {column} ASC LIMIT 1 OFFSET ?",
            [*params, index],
        ).fetchone()
        output.append(_maybe_float(row["value"]) if row else None)
    return tuple(output)


def _normalize_event(row: dict[str, Any]) -> dict[str, Any]:
    if row.get("success") is not None:
        row["success"] = bool(row["success"])
    if row.get("cached") is not None:
        row["cached"] = bool(row["cached"])
    return row


def _split_unique(value: Any) -> list[str]:
    if not value:
        return []
    return sorted({part for part in str(value).split(",") if part})


def _safe_div(num: int | float | None, denom: int | float | None) -> float | None:
    if num is None or denom in (None, 0):
        return None
    return float(num) / float(denom)


def _maybe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


__all__ = [
    "AnalyticsFilters",
    "build_analytics",
    "build_context_buckets",
    "build_filter_options",
    "build_insights",
    "build_model_stats",
    "build_provider_stats",
    "build_recent_events",
    "build_summary",
    "build_timeseries",
    "list_gateway_scopes",
]
