"""Filesystem path helpers.

``PROJECT_ROOT`` is computed from this file's location so that running the
package from a source checkout, an installed wheel, or a frozen binary all
yield the same anchor (the repository root for source / wheel install, or the
binary directory for PyInstaller-style freezes).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

DEFAULT_DB_FILENAME = "cloudflare_ai_gateway.sqlite"


def _detect_project_root() -> Path:
    if getattr(sys, "frozen", False):  # pragma: no cover - frozen binaries
        return Path(sys.executable).resolve().parent
    # src/cf_aigw_analyzer/utils/paths.py → project root
    return Path(__file__).resolve().parents[3]


PROJECT_ROOT: Path = _detect_project_root()


_SAFE_PART_RE = re.compile(r"[^A-Za-z0-9_.-]+")


def safe_filename_part(value: str | None) -> str:
    """Return a path-safe fragment for account/gateway/log identifiers."""

    cleaned = _SAFE_PART_RE.sub("_", str(value or "default")).strip("._-")
    return cleaned or "default"


def resolve_db_path(
    db_path: str | Path | None = None,
    data_dir: str | Path | None = None,
) -> Path:
    """Resolve the SQLite database path.

    Single-file design: all accounts and gateways share one database. Callers
    must not vary the path per scope.
    """

    if db_path:
        return Path(db_path).expanduser().resolve()

    base = Path(data_dir).expanduser() if data_dir else PROJECT_ROOT / "local" / "data"
    return (base / DEFAULT_DB_FILENAME).resolve()
