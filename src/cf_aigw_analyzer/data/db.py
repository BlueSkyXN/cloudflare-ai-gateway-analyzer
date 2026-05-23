"""SQLite connection management and read-only opener for analytics."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from urllib.parse import quote

from cf_aigw_analyzer.data.migrations import apply_migrations
from cf_aigw_analyzer.data.schema import PRAGMAS


def open_connection(path: str | Path) -> sqlite3.Connection:
    """Open (or create) the analyzer database with PRAGMAs applied."""

    db_path = Path(path).expanduser().resolve()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, isolation_level=None, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    for pragma in PRAGMAS:
        conn.execute(pragma)
    apply_migrations(conn)
    return conn


def open_readonly_connection(path: str | Path) -> sqlite3.Connection:
    """Open the database read-only via URI mode, used by analytics + dashboard."""

    db_path = Path(path).expanduser().resolve()
    if not db_path.exists():
        raise FileNotFoundError(f"SQLite database does not exist: {db_path}")
    uri = f"file:{quote(str(db_path), safe='/:')}?mode=ro"
    conn = sqlite3.connect(uri, uri=True, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def json_dumps(value: Any) -> str:
    """Stable JSON encoder for storing ``raw_json`` / ``params_json``."""

    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


@contextmanager
def transaction(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """Wrap a unit of writes in BEGIN/COMMIT (or ROLLBACK on error).

    ``isolation_level=None`` means we're in autocommit; explicit BEGIN gives us
    a single visible transaction for bulk repository operations.
    """

    conn.execute("BEGIN")
    try:
        yield conn
    except Exception:
        conn.execute("ROLLBACK")
        raise
    else:
        conn.execute("COMMIT")


class AnalyzerDatabase:
    """Thin facade combining connection lifecycle + scoped repositories.

    Lazy repository properties keep imports shallow at the package level.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).expanduser().resolve()
        self.conn = open_connection(self.path)

    def __enter__(self) -> AnalyzerDatabase:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def close(self) -> None:
        self.conn.close()

    def vacuum(self) -> None:
        self.conn.execute("VACUUM")

    @property
    def database_bytes(self) -> int:
        return self.path.stat().st_size if self.path.exists() else 0

    # Lazy repository accessors (imported here to avoid circular deps)
    @property
    def gateways(self):
        from cf_aigw_analyzer.data.repository.gateways import GatewaysRepository

        return GatewaysRepository(self.conn)

    @property
    def logs(self):
        from cf_aigw_analyzer.data.repository.logs import LogsRepository

        return LogsRepository(self.conn)

    @property
    def usage(self):
        from cf_aigw_analyzer.data.repository.usage import UsageRepository

        return UsageRepository(self.conn)

    @property
    def metrics(self):
        from cf_aigw_analyzer.data.repository.metrics import MetricsRepository

        return MetricsRepository(self.conn)

    @property
    def sync_runs(self):
        from cf_aigw_analyzer.data.repository.sync_runs import SyncRunsRepository

        return SyncRunsRepository(self.conn)

    @property
    def raw(self):
        from cf_aigw_analyzer.data.repository.raw import RawRepository

        return RawRepository(self.conn)
