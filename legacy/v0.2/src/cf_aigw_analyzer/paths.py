"""Filesystem path helpers."""

from __future__ import annotations

import os
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB_FILENAME = "cloudflare_ai_gateway.sqlite"


def safe_filename_part(value: str | None) -> str:
    """Return a path-safe fragment for account or gateway IDs."""

    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value or "default")).strip("._-")
    return cleaned or "default"


def default_data_dir(data_dir: str | None = None) -> Path:
    """Resolve the local data directory.

    The project is meant to run from its deployment checkout, so the default is
    the repository-local local/data directory instead of a user-wide cache.
    """

    configured = data_dir or os.getenv("CF_AIGW_DATA_DIR")
    if configured:
        return Path(configured).expanduser().resolve()
    return PROJECT_ROOT / "local" / "data"


def resolve_db_path(
    db_path: str | None = None,
    data_dir: str | None = None,
    gateway_id: str | None = None,
) -> Path:
    """Resolve the single SQLite database path.

    ``gateway_id`` is accepted for backward-compatible call sites, but the
    default database is intentionally one file for all gateways.
    """

    configured = db_path or os.getenv("CF_AIGW_DB")
    if configured:
        return Path(configured).expanduser().resolve()
    return default_data_dir(data_dir) / DEFAULT_DB_FILENAME
