"""CORS + request logging middleware."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from cf_aigw_analyzer.config import Settings


def configure_middleware(app: FastAPI, settings: Settings) -> None:
    if settings.control.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.control.cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
