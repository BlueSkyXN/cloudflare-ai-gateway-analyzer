"""Routes package."""

from cf_aigw_analyzer.control.routes import (
    analytics_route,
    config_route,
    events_route,
    health_route,
    scopes_route,
    status_route,
    sync_route,
)

__all__ = [
    "analytics_route",
    "config_route",
    "events_route",
    "health_route",
    "scopes_route",
    "status_route",
    "sync_route",
]
