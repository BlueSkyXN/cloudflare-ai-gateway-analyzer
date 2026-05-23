"""Usage repository: parsed Cloudflare response usage rows."""

from __future__ import annotations

import sqlite3

from cf_aigw_analyzer.data.db import transaction
from cf_aigw_analyzer.data.models import UsageFields
from cf_aigw_analyzer.models.enums import FetchStatus
from cf_aigw_analyzer.utils.time import utc_now


class UsageRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def upsert(
        self,
        account_id: str,
        gateway_id: str,
        log_id: str,
        usage: UsageFields,
        fetch_status: FetchStatus,
        http_status_code: int | None,
        error_message: str | None,
    ) -> None:
        now = utc_now()
        with transaction(self.conn):
            self.conn.execute(
                """
                INSERT INTO log_usage (
                    account_id, gateway_id, log_id,
                    input_tokens, output_tokens, total_tokens, cached_tokens,
                    reasoning_tokens, cache_write_tokens, source, fetch_status,
                    http_status_code, error_message, fetched_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(account_id, gateway_id, log_id) DO UPDATE SET
                    input_tokens=excluded.input_tokens,
                    output_tokens=excluded.output_tokens,
                    total_tokens=excluded.total_tokens,
                    cached_tokens=excluded.cached_tokens,
                    reasoning_tokens=excluded.reasoning_tokens,
                    cache_write_tokens=excluded.cache_write_tokens,
                    source=excluded.source,
                    fetch_status=excluded.fetch_status,
                    http_status_code=excluded.http_status_code,
                    error_message=excluded.error_message,
                    fetched_at=excluded.fetched_at,
                    updated_at=excluded.updated_at
                """,
                (
                    account_id,
                    gateway_id,
                    log_id,
                    usage.input_tokens,
                    usage.output_tokens,
                    usage.total_tokens,
                    usage.cached_tokens,
                    usage.reasoning_tokens,
                    usage.cache_write_tokens,
                    usage.source,
                    fetch_status.value if isinstance(fetch_status, FetchStatus) else fetch_status,
                    http_status_code,
                    error_message,
                    now,
                    now,
                ),
            )

    def status_counts(self, account_id: str | None, gateway_id: str | None) -> dict[str, int]:
        clauses: list[str] = []
        params: list[object] = []
        if account_id:
            clauses.append("account_id = ?")
            params.append(account_id)
        if gateway_id:
            clauses.append("gateway_id = ?")
            params.append(gateway_id)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""

        rows = self.conn.execute(
            f"SELECT fetch_status, COUNT(*) AS n FROM log_usage {where} GROUP BY fetch_status",
            params,
        ).fetchall()
        return {row["fetch_status"]: int(row["n"]) for row in rows}
