"""Human-readable insights derived from summary + breakdowns."""

from __future__ import annotations

import sqlite3

from cf_aigw_analyzer.analytics.context import build_context_buckets
from cf_aigw_analyzer.analytics.models import build_model_stats
from cf_aigw_analyzer.analytics.queries import AnalyticsFilters
from cf_aigw_analyzer.analytics.summary import build_summary
from cf_aigw_analyzer.analytics.timeseries import build_timeseries


def build_insights(conn: sqlite3.Connection, filters: AnalyticsFilters) -> list[dict[str, str]]:
    summary = build_summary(conn, filters)
    if not summary["requests"]:
        return [
            {"level": "info", "title": "暂无数据", "detail": "当前筛选条件下没有可分析的日志。"}
        ]

    insights: list[dict[str, str]] = []
    model_stats = build_model_stats(conn, filters)
    context_stats = build_context_buckets(conn, filters)
    timeseries = build_timeseries(conn, filters)

    if model_stats:
        top = model_stats[0]
        share = top["requests"] / summary["requests"] if summary["requests"] else 0
        insights.append(
            {
                "level": "info",
                "title": "主力模型",
                "detail": f"{top['model']} 请求量最高，共 {top['requests']:,} 次，占全部请求的 {share:.1%}。",
            }
        )
        slow_candidates = [m for m in model_stats if m["requests"] >= 10 and m.get("p95_total_ms")]
        if slow_candidates:
            slowest = max(slow_candidates, key=lambda m: m["p95_total_ms"])
            insights.append(
                {
                    "level": "warning",
                    "title": "高延迟模型",
                    "detail": (
                        f"{slowest['model']} 的 p95 total latency 最高，为 "
                        f"{slowest['p95_total_ms']:.0f} ms（样本 {slowest['requests']:,} 次）。"
                    ),
                }
            )

    no_usage = summary["usage_statuses"].get("no_usage", 0)
    if summary["requests"] and no_usage / summary["requests"] >= 0.05:
        insights.append(
            {
                "level": "warning",
                "title": "usage 缺失比例",
                "detail": (
                    f"有 {no_usage:,} 条日志未解析到 usage，占 "
                    f"{no_usage / summary['requests']:.1%}；这些请求不会贡献完整 token 统计。"
                ),
            }
        )

    if context_stats:
        with_latency = [c for c in context_stats if c.get("avg_total_ms") is not None]
        if with_latency:
            slow_bucket = max(with_latency, key=lambda c: c["avg_total_ms"])
            insights.append(
                {
                    "level": "info",
                    "title": "上下文长度影响",
                    "detail": (
                        f"{slow_bucket['context_bucket']} 分桶平均 total latency 最高，"
                        f"为 {slow_bucket['avg_total_ms']:.0f} ms。"
                    ),
                }
            )
        long_bucket = next((c for c in context_stats if c["context_bucket"] == "100k-500k"), None)
        medium_bucket = next((c for c in context_stats if c["context_bucket"] == "10k-100k"), None)
        if (
            long_bucket
            and medium_bucket
            and long_bucket.get("avg_output_tps")
            and medium_bucket.get("avg_output_tps")
        ):
            delta = long_bucket["avg_output_tps"] / medium_bucket["avg_output_tps"] - 1
            insights.append(
                {
                    "level": "info",
                    "title": "长上下文 TPS 对比",
                    "detail": (
                        f"100k-500k 分桶的平均 output TPS 相比 10k-100k 分桶变化 {delta:+.1%}。"
                    ),
                }
            )

    if timeseries:
        peak = max(timeseries, key=lambda t: t["requests"])
        insights.append(
            {
                "level": "info",
                "title": "请求峰值时段",
                "detail": (
                    f"{peak['hour']} 请求量最高，共 {peak['requests']:,} 次，TPM 约 {peak['tpm']:,.0f}。"
                ),
            }
        )

    if summary.get("cache_ratio") is not None:
        insights.append(
            {
                "level": "info",
                "title": "缓存利用率",
                "detail": (
                    f"cached tokens / input tokens 约为 {summary['cache_ratio']:.1%}，"
                    "可用于观察长上下文复用效果。"
                ),
            }
        )

    return insights[:8]
