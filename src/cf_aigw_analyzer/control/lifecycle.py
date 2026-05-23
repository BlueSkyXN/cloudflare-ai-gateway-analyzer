"""Lifespan + Settings carrier shared across routes."""

from __future__ import annotations

import contextlib
import sqlite3
from collections.abc import AsyncIterator
from dataclasses import dataclass, field

from fastapi import FastAPI

from cf_aigw_analyzer.config import Settings
from cf_aigw_analyzer.control.tasks import JobRegistry
from cf_aigw_analyzer.data.db import AnalyzerDatabase, open_readonly_connection


@dataclass(slots=True)
class AppState:
    settings: Settings
    db: AnalyzerDatabase
    jobs: JobRegistry = field(default_factory=JobRegistry)

    def open_readonly(self) -> sqlite3.Connection:
        return open_readonly_connection(self.db.path)


def create_state(settings: Settings) -> AppState:
    """Construct the request-shared state. The database is initialized eagerly."""

    from cf_aigw_analyzer.utils.paths import resolve_db_path

    db_path = resolve_db_path(None, settings.storage.data_dir)
    db = AnalyzerDatabase(db_path)
    return AppState(settings=settings, db=db)


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    state: AppState = app.state.context  # populated by build_app
    try:
        yield
    finally:
        state.db.close()
