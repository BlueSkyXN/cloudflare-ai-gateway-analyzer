"""FastAPI dependencies."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator

from fastapi import Request

from cf_aigw_analyzer.config import Settings


def get_state(request: Request):
    return request.app.state.context


def get_settings(request: Request) -> Settings:
    return request.app.state.context.settings


def get_jobs(request: Request):
    return request.app.state.context.jobs


def readonly_conn(request: Request) -> Iterator[sqlite3.Connection]:
    state = request.app.state.context
    conn = state.open_readonly()
    try:
        yield conn
    finally:
        conn.close()
