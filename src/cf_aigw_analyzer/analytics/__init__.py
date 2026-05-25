"""Read-only analytics over the local SQLite log_events fact table."""

from cf_aigw_analyzer.analytics.aggregate import (
    AnalyticsFilters,
    build_analytics,
    build_context_buckets,
    build_filter_options,
    build_insights,
    build_model_stats,
    build_provider_stats,
    build_recent_events,
    build_summary,
    build_timeseries,
    list_gateway_scopes,
)

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
