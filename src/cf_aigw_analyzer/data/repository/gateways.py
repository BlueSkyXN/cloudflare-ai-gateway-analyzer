"""Gateway upsert + lookup."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from typing import Any

from cf_aigw_analyzer.core.sanitizer import sanitize_log_metadata
from cf_aigw_analyzer.data.db import json_dumps, transaction
from cf_aigw_analyzer.utils.time import utc_now


class GatewaysRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def upsert_many(self, account_id: str, gateways: Iterable[dict[str, Any]]) -> int:
        now = utc_now()
        rows = list(gateways)
        if not rows:
            return 0
        count = 0
        with transaction(self.conn):
            for gateway in rows:
                gateway_id = gateway.get("id") or gateway.get("gateway_id")
                if not gateway_id:
                    continue
                self.conn.execute(
                    """
                    INSERT INTO gateways (account_id, gateway_id, name, collect_logs, raw_json, fetched_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(account_id, gateway_id) DO UPDATE SET
                        name=excluded.name,
                        collect_logs=excluded.collect_logs,
                        raw_json=excluded.raw_json,
                        fetched_at=excluded.fetched_at
                    """,
                    (
                        account_id,
                        str(gateway_id),
                        gateway.get("name"),
                        _as_bool_int(gateway.get("collect_logs")),
                        json_dumps(sanitize_log_metadata(gateway)),
                        now,
                    ),
                )
                count += 1
        return count

    def resolve_gateway_id(self, account_id: str, name_or_id: str) -> str | None:
        row = self.conn.execute(
            """
            SELECT gateway_id FROM gateways
            WHERE account_id = ?
              AND (gateway_id = ? OR name = ?)
            ORDER BY CASE WHEN gateway_id = ? THEN 0 ELSE 1 END
            LIMIT 1
            """,
            (account_id, name_or_id, name_or_id, name_or_id),
        ).fetchone()
        return str(row["gateway_id"]) if row else None

    def list_for_account(self, account_id: str) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT account_id, gateway_id, name, collect_logs, fetched_at FROM gateways WHERE account_id=? ORDER BY name",
            (account_id,),
        ).fetchall()
        return [dict(row) for row in rows]


def _as_bool_int(value: Any) -> int | None:
    if value is None:
        return None
    return 1 if bool(value) else 0
