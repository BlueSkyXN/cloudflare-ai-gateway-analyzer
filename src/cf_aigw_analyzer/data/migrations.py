"""Schema migration runner.

Strategy: a single :data:`SCHEMA_VERSION` constant in :mod:`schema` represents
the current target. ``user_version`` PRAGMA is updated transactionally, and
every applied version is appended to the ``migrations`` table for audit.

For v0.3 we ship a clean schema and do not need step-wise migrations from v0.2
data (the user explicitly accepted full rewrite without migration). Future
upgrades should append handlers to :data:`MIGRATIONS`.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable

from cf_aigw_analyzer.data.schema import DDL, SCHEMA_VERSION
from cf_aigw_analyzer.utils.time import utc_now

MigrationFn = Callable[[sqlite3.Connection], None]


def _migration_v3(conn: sqlite3.Connection) -> None:
    """Initial v3 schema. Executes the full DDL idempotently."""

    conn.executescript(DDL)


MIGRATIONS: dict[int, MigrationFn] = {
    3: _migration_v3,
}


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
