"""Filter dataclass + shared WHERE-clause builder for analytics queries."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Any

from cf_aigw_analyzer.utils.time import parse_datetime_input


@dataclass(slots=True)
class AnalyticsFilters:
    account_id: str | None = None
    gateway_id: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    provider: str | None = None
    model: str | None = None
    success: bool | None = None
    timeseries_bucket_hours: int = 1


def build_where(filters: AnalyticsFilters, *, prefix: str = "e") -> tuple[str, list[Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    if filters.account_id:
        clauses.append(f"{prefix}.account_id = ?")
        params.append(filters.account_id)
    if filters.gateway_id:
        clauses.append(f"{prefix}.gateway_id = ?")
        params.append(filters.gateway_id)
    if filters.start_date:
        clauses.append(f"julianday({prefix}.created_at) >= julianday(?)")
        params.append(parse_datetime_input(filters.start_date))
    if filters.end_date:
        clauses.append(f"julianday({prefix}.created_at) <= julianday(?)")
        params.append(parse_datetime_input(filters.end_date))
    if filters.provider:
        clauses.append(f"{prefix}.provider = ?")
        params.append(filters.provider)
    if filters.model:
        clauses.append(f"{prefix}.model = ?")
        params.append(filters.model)
    if filters.success is not None:
        clauses.append(f"{prefix}.success = ?")
        params.append(1 if filters.success else 0)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    return where, params


def list_gateway_scopes(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT
            e.account_id,
            e.gateway_id,
            COALESCE(g.name, e.gateway_id) AS name,
            COUNT(*) AS logs,
            MIN(e.created_at) AS first_log_at,
            MAX(e.created_at) AS last_log_at
        FROM log_events e
        LEFT JOIN gateways g
          ON e.account_id = g.account_id
         AND e.gateway_id = g.gateway_id
        GROUP BY e.account_id, e.gateway_id, COALESCE(g.name, e.gateway_id)
        ORDER BY last_log_at DESC
        """
    ).fetchall()
    return [dict(row) for row in rows]
