"""Domain enums used across the package."""

from __future__ import annotations

from enum import StrEnum


class FetchStatus(StrEnum):
    """Possible states for a ``log_usage`` row."""

    PARSED = "parsed"
    NO_USAGE = "no_usage"
    FAILED = "failed"


class OutputFormat(StrEnum):
    """Output format choices for the CLI ``query`` command."""

    TABLE = "table"
    JSON = "json"
    CSV = "csv"


class LogFormat(StrEnum):
    """Console log format choices."""

    RICH = "rich"
    PLAIN = "plain"
    JSON = "json"
