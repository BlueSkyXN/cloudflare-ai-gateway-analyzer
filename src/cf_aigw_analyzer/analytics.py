"""Read-only analytics over the local AI Gateway SQLite database."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import quote

from .filters import parse_datetime
from .usage import as_int


@dataclass(slots=True)
class AnalyticsFilters:
    account_id: str | None = None
    gateway_id: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    provider: str | None = None
    model: str | None = None
    success: bool | None = None


CONTEXT_BUCKETS: tuple[tuple[str, int | None, int | None], ...] = (
    ("<1k", None, 1_000),
    ("1k-10k", 1_000, 10_000),
    ("10k-100k", 10_000, 100_000),
    ("100k-500k", 100_000, 500_000),
    ("500k+", 500_000, None),
)


def open_readonly_database(path: str | Path) -> sqlite3.Connection:
    db_path = Path(path).expanduser().resolve()
    if not db_path.exists():
        raise FileNotFoundError(f"SQLite database does not exist: {db_path}")
    uri = f"file:{quote(str(db_path), safe='/:')}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _avg(values: Iterable[float | int | None]) -> float | None:
    numeric = [float(value) for value in values if value is not None]
    if not numeric:
        return None
    return sum(numeric) / len(numeric)


def _percentile(values: Iterable[float | int | None], percentile: float) -> float | None:
    numeric = sorted(float(value) for value in values if value is not None)
    if not numeric:
        return None
    if len(numeric) == 1:
        return numeric[0]
    position = (len(numeric) - 1) * percentile
    lower = int(position)
    upper = min(lower + 1, len(numeric) - 1)
    if lower == upper:
        return numeric[lower]
    weight = position - lower
    return numeric[lower] * (1 - weight) + numeric[upper] * weight


def _ratio(numerator: float | int | None, denominator: float | int | None) -> float | None:
    if numerator is None or denominator in (None, 0):
        return None
    return float(numerator) / float(denominator)


def _sum(values: Iterable[int | float | None]) -> int:
    return int(sum(int(value) for value in values if value is not None))


def _where(filters: AnalyticsFilters) -> tuple[str, list[Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    if filters.account_id:
        clauses.append("l.account_id = ?")
        params.append(filters.account_id)
    if filters.gateway_id:
        clauses.append("l.gateway_id = ?")
        params.append(filters.gateway_id)
    if filters.start_date:
        clauses.append("l.created_at >= ?")
        params.append(parse_datetime(filters.start_date))
    if filters.end_date:
        clauses.append("l.created_at <= ?")
        params.append(parse_datetime(filters.end_date))
    if filters.provider:
        clauses.append("l.provider = ?")
        params.append(filters.provider)
    if filters.model:
        clauses.append("l.model = ?")
        params.append(filters.model)
    if filters.success is not None:
        clauses.append("l.success = ?")
        params.append(1 if filters.success else 0)
    return f"WHERE {' AND '.join(clauses)}" if clauses else "", params


def list_gateway_scopes(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT
            l.account_id,
            l.gateway_id,
            COALESCE(g.name, l.gateway_id) AS name,
            COUNT(*) AS logs,
            MIN(l.created_at) AS first_log_at,
            MAX(l.created_at) AS last_log_at
        FROM logs l
        LEFT JOIN gateways g
          ON l.account_id = g.account_id
         AND l.gateway_id = g.gateway_id
        GROUP BY l.account_id, l.gateway_id, COALESCE(g.name, l.gateway_id)
        ORDER BY last_log_at DESC
        """
    ).fetchall()
    return [dict(row) for row in rows]


def resolve_gateway_id(
    conn: sqlite3.Connection,
    account_id: str | None,
    gateway_name_or_id: str | None,
) -> str | None:
    if not gateway_name_or_id:
        return None
    clauses = ["(g.gateway_id = ? OR g.name = ? OR l.gateway_id = ?)"]
    params: list[Any] = [gateway_name_or_id, gateway_name_or_id, gateway_name_or_id]
    if account_id:
        clauses.append("l.account_id = ?")
        params.append(account_id)
    row = conn.execute(
        f"""
        SELECT l.gateway_id
        FROM logs l
        LEFT JOIN gateways g
          ON l.account_id = g.account_id
         AND l.gateway_id = g.gateway_id
        WHERE {' AND '.join(clauses)}
        ORDER BY CASE WHEN l.gateway_id = ? THEN 0 ELSE 1 END, l.created_at DESC
        LIMIT 1
        """,
        params + [gateway_name_or_id],
    ).fetchone()
    return str(row["gateway_id"]) if row else gateway_name_or_id


def fetch_rows(conn: sqlite3.Connection, filters: AnalyticsFilters) -> list[dict[str, Any]]:
    where, params = _where(filters)
    rows = conn.execute(
        f"""
        SELECT
            l.log_id,
            l.created_at,
            l.provider,
            l.model,
            l.model_type,
            l.success,
            l.cached,
            l.status_code,
            l.cost_usd,
            COALESCE(u.input_tokens, l.tokens_in) AS input_tokens,
            COALESCE(u.output_tokens, l.tokens_out) AS output_tokens,
            u.total_tokens AS usage_total_tokens,
            u.cached_tokens,
            u.reasoning_tokens,
            u.cache_write_tokens,
            u.source AS usage_source,
            u.fetch_status AS usage_fetch_status,
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
        {where}
        ORDER BY l.created_at ASC
        """,
        params,
    ).fetchall()
    return [_normalize_row(row) for row in rows]


def _normalize_row(row: sqlite3.Row) -> dict[str, Any]:
    item = dict(row)
    input_tokens = as_int(item.get("input_tokens"))
    output_tokens = as_int(item.get("output_tokens"))
    total_tokens = as_int(item.get("usage_total_tokens"))
    if total_tokens is None and (input_tokens is not None or output_tokens is not None):
        total_tokens = (input_tokens or 0) + (output_tokens or 0)
    item["input_tokens"] = input_tokens
    item["output_tokens"] = output_tokens
    item["total_tokens"] = total_tokens
    item["cached_tokens"] = as_int(item.get("cached_tokens")) or 0
    item["reasoning_tokens"] = as_int(item.get("reasoning_tokens")) or 0
    item["cache_write_tokens"] = as_int(item.get("cache_write_tokens")) or 0
    item["success"] = None if item.get("success") is None else bool(item["success"])
    item["cached"] = None if item.get("cached") is None else bool(item["cached"])
    item.pop("usage_total_tokens", None)
    return item


def build_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    requests = len(rows)
    success_count = sum(1 for row in rows if row.get("success") is True)
    failed_count = sum(1 for row in rows if row.get("success") is False)
    input_tokens = _sum(row.get("input_tokens") for row in rows)
    output_tokens = _sum(row.get("output_tokens") for row in rows)
    total_tokens = _sum(row.get("total_tokens") for row in rows)
    cached_tokens = _sum(row.get("cached_tokens") for row in rows)
    reasoning_tokens = _sum(row.get("reasoning_tokens") for row in rows)
    statuses: dict[str, int] = {}
    for row in rows:
        status = str(row.get("usage_fetch_status") or "missing")
        statuses[status] = statuses.get(status, 0) + 1

    return {
        "requests": requests,
        "success_count": success_count,
        "failed_count": failed_count,
        "success_rate": _ratio(success_count, requests),
        "models": len({row.get("model") for row in rows if row.get("model")}),
        "providers": len({row.get("provider") for row in rows if row.get("provider")}),
        "first_log_at": rows[0]["created_at"] if rows else None,
        "last_log_at": rows[-1]["created_at"] if rows else None,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "cached_tokens": cached_tokens,
        "reasoning_tokens": reasoning_tokens,
        "cache_ratio": _ratio(cached_tokens, input_tokens),
        "avg_total_ms": _avg(row.get("total_ms") for row in rows),
        "p50_total_ms": _percentile((row.get("total_ms") for row in rows), 0.50),
        "p95_total_ms": _percentile((row.get("total_ms") for row in rows), 0.95),
        "p99_total_ms": _percentile((row.get("total_ms") for row in rows), 0.99),
        "avg_latency_ms": _avg(row.get("latency_ms") for row in rows),
        "avg_output_tps": _avg(row.get("output_tps") for row in rows),
        "avg_visible_output_tps": _avg(row.get("visible_output_tps") for row in rows),
        "usage_statuses": statuses,
    }


def _group_by(rows: list[dict[str, Any]], key_name: str) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        key = str(row.get(key_name) or "(unknown)")
        groups.setdefault(key, []).append(row)
    return groups


def build_model_stats(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    stats = []
    for model, group in _group_by(rows, "model").items():
        summary = build_summary(group)
        stats.append(
            {
                "model": model,
                "provider": ", ".join(sorted({str(row.get("provider")) for row in group if row.get("provider")})),
                **summary,
                "avg_input_tokens": _avg(row.get("input_tokens") for row in group),
                "avg_output_tokens": _avg(row.get("output_tokens") for row in group),
                "tokens_per_request": _ratio(summary["total_tokens"], summary["requests"]),
            }
        )
    stats.sort(key=lambda item: item["requests"], reverse=True)
    return stats


def context_bucket(input_tokens: int | None) -> str:
    if input_tokens is None:
        return "unknown"
    for label, minimum, maximum in CONTEXT_BUCKETS:
        if (minimum is None or input_tokens >= minimum) and (maximum is None or input_tokens < maximum):
            return label
    return "unknown"


def build_context_buckets(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        groups.setdefault(context_bucket(row.get("input_tokens")), []).append(row)

    ordered = [label for label, _, _ in CONTEXT_BUCKETS] + ["unknown"]
    result = []
    for label in ordered:
        group = groups.get(label, [])
        if not group:
            continue
        summary = build_summary(group)
        result.append(
            {
                "context_bucket": label,
                **summary,
                "avg_input_tokens": _avg(row.get("input_tokens") for row in group),
                "avg_output_tokens": _avg(row.get("output_tokens") for row in group),
            }
        )
    return result


def _hour_bucket(created_at: str | None) -> str:
    if not created_at or len(created_at) < 13:
        return "unknown"
    return f"{created_at[:13]}:00:00Z"


def build_timeseries(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        groups.setdefault(_hour_bucket(row.get("created_at")), []).append(row)

    result = []
    for hour, group in sorted(groups.items()):
        summary = build_summary(group)
        result.append(
            {
                "hour": hour,
                **summary,
                "rpm": summary["requests"] / 60,
                "tpm": summary["total_tokens"] / 60,
            }
        )
    return result


def build_recent_events(rows: list[dict[str, Any]], limit: int = 500) -> list[dict[str, Any]]:
    safe_limit = max(1, min(limit, 5_000))
    fields = (
        "log_id",
        "created_at",
        "provider",
        "model",
        "model_type",
        "success",
        "cached",
        "status_code",
        "input_tokens",
        "output_tokens",
        "total_tokens",
        "cached_tokens",
        "reasoning_tokens",
        "usage_fetch_status",
        "duration_ms",
        "latency_ms",
        "total_ms",
        "generation_ms",
        "output_tps",
        "visible_output_tps",
    )
    ordered = sorted(rows, key=lambda row: str(row.get("created_at") or ""), reverse=True)
    return [{field: row.get(field) for field in fields} for row in ordered[:safe_limit]]


def build_insights(rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    if not rows:
        return [{"level": "info", "title": "暂无数据", "detail": "当前筛选条件下没有可分析的日志。"}]

    insights: list[dict[str, str]] = []
    summary = build_summary(rows)
    model_stats = build_model_stats(rows)
    context_stats = build_context_buckets(rows)
    timeseries = build_timeseries(rows)

    if model_stats:
        top = model_stats[0]
        insights.append(
            {
                "level": "info",
                "title": "主力模型",
                "detail": f"{top['model']} 请求量最高，共 {top['requests']:,} 次，占全部请求的 {top['requests'] / summary['requests']:.1%}。",
            }
        )

        latency_candidates = [item for item in model_stats if item["requests"] >= 10 and item["p95_total_ms"] is not None]
        if latency_candidates:
            slow = max(latency_candidates, key=lambda item: item["p95_total_ms"])
            insights.append(
                {
                    "level": "warning",
                    "title": "高延迟模型",
                    "detail": f"{slow['model']} 的 p95 total latency 最高，为 {slow['p95_total_ms']:.0f} ms（样本 {slow['requests']:,} 次）。",
                }
            )

    no_usage = summary["usage_statuses"].get("no_usage", 0)
    if summary["requests"] and no_usage / summary["requests"] >= 0.05:
        insights.append(
            {
                "level": "warning",
                "title": "usage 缺失比例",
                "detail": f"有 {no_usage:,} 条日志没有解析到 usage，占 {no_usage / summary['requests']:.1%}；这些请求不会贡献完整 token 统计。",
            }
        )

    if context_stats:
        slow_bucket = max(
            (item for item in context_stats if item["avg_total_ms"] is not None),
            key=lambda item: item["avg_total_ms"],
            default=None,
        )
        if slow_bucket:
            insights.append(
                {
                    "level": "info",
                    "title": "上下文长度影响",
                    "detail": f"{slow_bucket['context_bucket']} 上下文分桶平均 total latency 最高，为 {slow_bucket['avg_total_ms']:.0f} ms。",
                }
            )

        long_bucket = next((item for item in context_stats if item["context_bucket"] == "100k-500k"), None)
        medium_bucket = next((item for item in context_stats if item["context_bucket"] == "10k-100k"), None)
        if long_bucket and medium_bucket and long_bucket["avg_output_tps"] and medium_bucket["avg_output_tps"]:
            delta = long_bucket["avg_output_tps"] / medium_bucket["avg_output_tps"] - 1
            insights.append(
                {
                    "level": "info",
                    "title": "长上下文 TPS 对比",
                    "detail": f"100k-500k 分桶的平均 output TPS 相比 10k-100k 分桶变化 {delta:+.1%}。",
                }
            )

    if timeseries:
        peak = max(timeseries, key=lambda item: item["requests"])
        insights.append(
            {
                "level": "info",
                "title": "请求峰值时段",
                "detail": f"{peak['hour']} 请求量最高，共 {peak['requests']:,} 次，TPM 约 {peak['tpm']:,.0f}。",
            }
        )

    if summary["cache_ratio"] is not None:
        insights.append(
            {
                "level": "info",
                "title": "缓存利用率",
                "detail": f"cached tokens / input tokens 约为 {summary['cache_ratio']:.1%}，可用于观察长上下文复用效果。",
            }
        )

    return insights[:8]


def build_dashboard_payload(conn: sqlite3.Connection, filters: AnalyticsFilters) -> dict[str, Any]:
    rows = fetch_rows(conn, filters)
    return {
        "summary": build_summary(rows),
        "timeseries": build_timeseries(rows),
        "model_stats": build_model_stats(rows),
        "context_buckets": build_context_buckets(rows),
        "recent_events": build_recent_events(rows),
        "insights": build_insights(rows),
    }
