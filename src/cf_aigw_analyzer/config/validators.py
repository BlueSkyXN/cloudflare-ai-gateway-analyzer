"""Secret-aware helpers for surfacing :class:`Settings` to humans / API."""

from __future__ import annotations

from typing import Any

from cf_aigw_analyzer.config.settings import Settings

REDACTED = "***"
_PYDANTIC_SECRET_MASK = "**********"


def redact_settings(settings: Settings) -> dict[str, Any]:
    """Return a ``Settings`` snapshot safe to print or expose via API.

    ``SecretStr`` fields become ``"***"`` when set, or remain ``None`` when empty.
    ``Path`` fields become POSIX strings. The result is JSON-serializable and
    YAML-dumpable without custom representers.
    """

    return _normalize(settings.model_dump(mode="json"))


def _normalize(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _normalize(child) for key, child in value.items()}
    if isinstance(value, list):
        return [_normalize(item) for item in value]
    if isinstance(value, str) and value == _PYDANTIC_SECRET_MASK:
        return REDACTED
    return value
