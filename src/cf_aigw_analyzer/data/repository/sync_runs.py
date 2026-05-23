"""Sync run audit log."""

from __future__ import annotations

import sqlite3
from typing import Any

from cf_aigw_analyzer.data.db import json_dumps
from cf_aigw_analyzer.utils.time import utc_now


class SyncRunsRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def record(
        self,
        account_id: str | None,
        gateway_id: str | None,
        mode: str,
        params: dict[str, Any] | None = None,
        *,
        logs_count: int = 0,
        usage_fetched: int = 0,
        usage_parsed: int = 0,
        usage_no_usage: int = 0,
        usage_failed: int = 0,
        started_at: str | None = None,
    ) -> int:
        finished_at = utc_now()
        cursor = self.conn.execute(
            """
            INSERT INTO sync_runs (
                account_id, gateway_id, mode, params_json, logs_count,
                usage_fetched, usage_parsed, usage_no_usage, usage_failed,
                started_at, finished_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                account_id,
                gateway_id,
                mode,
                json_dumps(params or {}),
                logs_count,
                usage_fetched,
                usage_parsed,
                usage_no_usage,
                usage_failed,
                started_at or finished_at,
                finished_at,
            ),
        )
        return int(cursor.lastrowid or 0)

    def list_recent(
        self,
        account_id: str | None = None,
        gateway_id: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if account_id:
            clauses.append("account_id = ?")
            params.append(account_id)
        if gateway_id:
            clauses.append("gateway_id = ?")
            params.append(gateway_id)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""

        rows = self.conn.execute(
            f"SELECT * FROM sync_runs {where} ORDER BY run_id DESC LIMIT ?",
            [*params, max(1, min(limit, 200))],
        ).fetchall()
        return [dict(row) for row in rows]

    def get(self, run_id: int) -> dict[str, Any] | None:
        row = self.conn.execute("SELECT * FROM sync_runs WHERE run_id=?", (run_id,)).fetchone()
        return dict(row) if row else None

    def last(
        self,
        account_id: str | None = None,
        gateway_id: str | None = None,
    ) -> dict[str, Any] | None:
        rows = self.list_recent(account_id, gateway_id, limit=1)
        return rows[0] if rows else None
