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


def build_where(filters: AnalyticsFilters, *, prefix: str = "l") -> tuple[str, list[Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    if filters.account_id:
        clauses.append(f"{prefix}.account_id = ?")
        params.append(filters.account_id)
    if filters.gateway_id:
        clauses.append(f"{prefix}.gateway_id = ?")
        params.append(filters.gateway_id)
    if filters.start_date:
        clauses.append(f"{prefix}.created_at >= ?")
        params.append(parse_datetime_input(filters.start_date))
    if filters.end_date:
        clauses.append(f"{prefix}.created_at <= ?")
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
            l.account_id,
            l.gateway_id,
            COALESCE(g.name, l.gateway_id) AS name,
            COUNT(*) AS logs,
            MIN(l.created_at) AS first_log_at,
            MAX(l.created_at) AS last_log_at
        FROM logs l
        LEFT JOIN gateways g
          ON l.account_id = g.account_id
         AND l.gateway_id = g.gateway_id
        GROUP BY l.account_id, l.gateway_id, COALESCE(g.name, l.gateway_id)
        ORDER BY last_log_at DESC
        """
    ).fetchall()
    return [dict(row) for row in rows]
