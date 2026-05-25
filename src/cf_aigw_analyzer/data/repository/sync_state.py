"""Incremental sync checkpoints."""

from __future__ import annotations

import sqlite3
from typing import Any

from cf_aigw_analyzer.utils.time import utc_now


class SyncStateRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def get(self, account_id: str, gateway_id: str, mode: str) -> dict[str, Any] | None:
        row = self.conn.execute(
            """
            SELECT * FROM sync_state
            WHERE account_id=? AND gateway_id=? AND mode=?
            """,
            (account_id, gateway_id, mode),
        ).fetchone()
        return dict(row) if row else None

    def record_success(
        self,
        account_id: str,
        gateway_id: str,
        mode: str,
        *,
        last_seen_created_at: str | None = None,
        last_seen_log_id: str | None = None,
    ) -> None:
        """Update a successful checkpoint without moving seen markers backward."""

        now = utc_now()
        self.conn.execute(
            """
            INSERT INTO sync_state (
                account_id, gateway_id, mode, last_success_at,
                last_seen_created_at, last_seen_log_id, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(account_id, gateway_id, mode) DO UPDATE SET
                last_success_at=excluded.last_success_at,
                last_seen_created_at=CASE
                    WHEN excluded.last_seen_created_at IS NULL
                        THEN sync_state.last_seen_created_at
                    WHEN sync_state.last_seen_created_at IS NULL
                        THEN excluded.last_seen_created_at
                    WHEN excluded.last_seen_created_at > sync_state.last_seen_created_at
                        THEN excluded.last_seen_created_at
                    ELSE sync_state.last_seen_created_at
                END,
                last_seen_log_id=CASE
                    WHEN excluded.last_seen_created_at IS NULL
                        THEN sync_state.last_seen_log_id
                    WHEN sync_state.last_seen_created_at IS NULL
                        THEN excluded.last_seen_log_id
                    WHEN excluded.last_seen_created_at > sync_state.last_seen_created_at
                        THEN excluded.last_seen_log_id
                    WHEN excluded.last_seen_created_at = sync_state.last_seen_created_at
                        THEN MAX(
                            COALESCE(sync_state.last_seen_log_id, ''),
                            COALESCE(excluded.last_seen_log_id, '')
                        )
                    ELSE sync_state.last_seen_log_id
                END,
                updated_at=excluded.updated_at
            """,
            (
                account_id,
                gateway_id,
                mode,
                now,
                last_seen_created_at,
                last_seen_log_id,
                now,
            ),
        )
