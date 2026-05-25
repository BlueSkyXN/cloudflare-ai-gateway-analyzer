"""Per-scope sync writer locks."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

from cf_aigw_analyzer.data.db import transaction
from cf_aigw_analyzer.utils.time import utc_now


class SyncLockBusy(RuntimeError):
    """Raised when another process already owns a sync lock."""


class SyncLocksRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def acquire(
        self,
        account_id: str,
        gateway_id: str,
        mode: str,
        owner: str,
        *,
        ttl_seconds: int = 21600,
    ) -> None:
        """Acquire a scoped lock or raise :class:`SyncLockBusy`.

        Expired locks are removed before insert, so an interrupted sync does not
        block future agents forever. The primary key keeps acquisition atomic.
        """

        now = utc_now()
        expires_at = _utc_after(max(1, ttl_seconds))
        with transaction(self.conn):
            self.conn.execute(
                """
                DELETE FROM sync_locks
                WHERE account_id=? AND gateway_id=? AND mode=? AND expires_at <= ?
                """,
                (account_id, gateway_id, mode, now),
            )
            try:
                self.conn.execute(
                    """
                    INSERT INTO sync_locks (
                        account_id, gateway_id, mode, owner, acquired_at, expires_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (account_id, gateway_id, mode, owner, now, expires_at),
                )
            except sqlite3.IntegrityError as exc:
                row = self.get(account_id, gateway_id, mode)
                holder = row["owner"] if row else "unknown"
                raise SyncLockBusy(
                    f"sync already running for {account_id}/{gateway_id}/{mode} (owner={holder})"
                ) from exc

    def release(self, account_id: str, gateway_id: str, mode: str, owner: str) -> None:
        self.conn.execute(
            """
            DELETE FROM sync_locks
            WHERE account_id=? AND gateway_id=? AND mode=? AND owner=?
            """,
            (account_id, gateway_id, mode, owner),
        )

    def get(self, account_id: str, gateway_id: str, mode: str) -> dict[str, str] | None:
        row = self.conn.execute(
            """
            SELECT * FROM sync_locks
            WHERE account_id=? AND gateway_id=? AND mode=?
            """,
            (account_id, gateway_id, mode),
        ).fetchone()
        return dict(row) if row else None


def _utc_after(seconds: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).strftime("%Y-%m-%dT%H:%M:%SZ")
