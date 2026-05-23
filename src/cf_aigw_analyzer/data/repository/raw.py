"""Raw sanitized JSON repository (1:1 with logs)."""

from __future__ import annotations

import sqlite3


class RawRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def get(self, account_id: str, gateway_id: str, log_id: str) -> str | None:
        row = self.conn.execute(
            "SELECT raw_json FROM logs_raw WHERE account_id=? AND gateway_id=? AND log_id=?",
            (account_id, gateway_id, log_id),
        ).fetchone()
        return str(row["raw_json"]) if row else None
