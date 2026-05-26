"""Schema migration runner.

Version 5 intentionally resets local analyzer data into a simpler schema. The
project is a local sync cache, and the v5 design trades old-cache preservation for
one analytics fact table that can be repopulated from Cloudflare.

Version 6 adds input-side throughput while preserving v5 data.
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


def _migration_v6(conn: sqlite3.Connection) -> None:
    """Add input TPS derived from prompt tokens and first-byte latency."""

    if "input_tps" not in _table_columns(conn, "log_events"):
        conn.execute("ALTER TABLE log_events ADD COLUMN input_tps REAL")
    conn.execute(
        """
        UPDATE log_events
        SET input_tps = input_tokens / (latency_ms / 1000.0)
        WHERE input_tps IS NULL
          AND input_tokens IS NOT NULL
          AND input_tokens > 0
          AND latency_ms IS NOT NULL
          AND latency_ms > 0
        """
    )


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {str(row[1]) for row in rows}


MIGRATIONS: dict[int, MigrationFn] = {5: _migration_v5, 6: _migration_v6}


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
