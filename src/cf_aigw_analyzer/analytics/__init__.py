"""Read-only analytics over the local SQLite database.

Aggregations are pushed down to SQL so that the dashboard can serve scopes
with millions of rows without loading them into Python memory.
"""

from cf_aigw_analyzer.analytics.context import build_context_buckets
from cf_aigw_analyzer.analytics.events import build_recent_events
from cf_aigw_analyzer.analytics.insights import build_insights
from cf_aigw_analyzer.analytics.models import build_model_stats
from cf_aigw_analyzer.analytics.queries import AnalyticsFilters, list_gateway_scopes
from cf_aigw_analyzer.analytics.summary import build_summary
from cf_aigw_analyzer.analytics.timeseries import build_timeseries

__all__ = [
    "AnalyticsFilters",
    "build_context_buckets",
    "build_insights",
    "build_model_stats",
    "build_recent_events",
    "build_summary",
    "build_timeseries",
    "list_gateway_scopes",
]
