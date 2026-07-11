"""Time helpers shared across the package."""

from __future__ import annotations

from datetime import datetime, timezone

_ISO_PATTERNS = (
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y-%m-%d",
    "%Y/%m/%d %H:%M:%S",
    "%Y/%m/%d",
)


def utc_now() -> str:
    """Return current UTC time as an ISO8601 ``YYYY-MM-DDTHH:MM:SSZ`` string."""

    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def utc_now_precise() -> str:
    """Return current UTC time with microseconds for local attempt ordering."""

    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def parse_datetime_input(value: str | None) -> str | None:
    """Normalize common date inputs to the Cloudflare API UTC format.

    Accepts ``YYYY-MM-DD``, ``YYYY-MM-DDTHH:MM:SSZ``, ``YYYY/MM/DD``, etc.
    Strings already containing ``T`` are returned untouched (caller's
    responsibility to ensure they parse upstream).
    """

    if not value:
        return None

    cleaned = value.strip()
    if "T" in cleaned:
        return cleaned

    for pattern in _ISO_PATTERNS:
        try:
            parsed = datetime.strptime(cleaned, pattern)
            return parsed.strftime("%Y-%m-%dT%H:%M:%SZ")
        except ValueError:
            continue
    return cleaned
