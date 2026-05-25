"""Schema migration runner.

Version 5 intentionally resets local analyzer data into a simpler schema. The
project is a local sync cache, and the v5 design trades old-cache preservation for
one analytics fact table that can be repopulated from Cloudflare.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable

from cf_aigw_analyzer.data.schema import DDL, SCHEMA_VERSION
from cf_aigw_analyzer.utils.time import utc_now

MigrationFn = Callable[[sqlite3.Connection], None]


RESET_TABLES = (
    "log_raw",
    "log_events",
    "logs_raw",
    "log_metrics",
    "log_usage",
    "logs",
    "sync_locks",
    "sync_state",
    "sync_runs",
    "gateways",
)


def _migration_v5(conn: sqlite3.Connection) -> None:
    """Reset legacy multi-table log storage and create the v5 schema."""

    conn.execute("PRAGMA foreign_keys=OFF")
    try:
        for table in RESET_TABLES:
            conn.execute(f"DROP TABLE IF EXISTS {table}")
        conn.executescript(DDL)
    finally:
        conn.execute("PRAGMA foreign_keys=ON")


MIGRATIONS: dict[int, MigrationFn] = {5: _migration_v5}


def current_version(conn: sqlite3.Connection) -> int:
    row = conn.execute("PRAGMA user_version").fetchone()
    return int(row[0]) if row else 0


def apply_migrations(conn: sqlite3.Connection) -> int:
    """Bring the database up to :data:`SCHEMA_VERSION`.

    Returns the resulting version. Idempotent.
    """

    version = current_version(conn)
    if version >= SCHEMA_VERSION:
        return version

    for target in sorted(MIGRATIONS):
        if target <= version:
            continue
        handler = MIGRATIONS[target]
        with conn:
            handler(conn)
            conn.execute(
                "INSERT OR REPLACE INTO migrations(version, applied_at) VALUES (?, ?)",
                (target, utc_now()),
            )
            conn.execute(f"PRAGMA user_version={target}")
        version = target

    return version
