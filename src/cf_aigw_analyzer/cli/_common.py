"""Shared CLI helpers and option types."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable
from pathlib import Path
from typing import Annotated, TypeVar

import typer

from cf_aigw_analyzer.config import Settings, load_settings
from cf_aigw_analyzer.config.loader import resolve_yaml_path
from cf_aigw_analyzer.data.db import AnalyzerDatabase
from cf_aigw_analyzer.utils.console import get_console
from cf_aigw_analyzer.utils.paths import resolve_db_path

T = TypeVar("T")

ConfigOption = Annotated[
    Path | None,
    typer.Option(
        "--config",
        "-c",
        help="Path to config.yaml. Defaults to ./config.yaml at project root.",
        envvar="CF_AIGW_CONFIG",
        show_default=False,
    ),
]

AccountOption = Annotated[
    str | None,
    typer.Option(
        "--account-id",
        "-a",
        help="Cloudflare account ID. Defaults to control.default_account_id when configured.",
        envvar="CF_AIGW_ACCOUNT_ID",
        show_default=False,
    ),
]

GatewayIdOption = Annotated[
    str | None,
    typer.Option(
        "--gateway-id",
        "-g",
        help="Cloudflare AI Gateway ID.",
        envvar="CF_AIGW_GATEWAY_ID",
        show_default=False,
    ),
]

GatewayNameOption = Annotated[
    str | None,
    typer.Option(
        "--gateway-name",
        help="Cloudflare AI Gateway name; resolved against local cache or live API.",
        show_default=False,
    ),
]


def load(config: Path | None) -> Settings:
    return load_settings(config)


def db_path_from(settings: Settings) -> Path:
    return resolve_db_path(None, settings.storage.data_dir)


def open_db(settings: Settings) -> AnalyzerDatabase:
    return AnalyzerDatabase(db_path_from(settings))


def require_account_id(settings: Settings, account_id: str | None) -> str:
    chosen = account_id or settings.control.default_account_id
    if not chosen:
        raise typer.BadParameter("缺少 --account-id，请通过 CLI 或 control.default_account_id 提供")
    return chosen


def resolve_gateway_locally(
    db: AnalyzerDatabase,
    account_id: str,
    gateway_id: str | None,
    gateway_name: str | None,
) -> str | None:
    """Resolve gateway identifier using local SQLite only."""

    if gateway_id:
        return gateway_id
    if gateway_name:
        resolved = db.gateways.resolve_gateway_id(account_id, gateway_name)
        if not resolved:
            raise typer.BadParameter(
                f"本地 SQLite 中没有找到 gateway: {gateway_name}（先跑 `gateways --save`）"
            )
        return resolved
    return None


def require_local_gateway(
    db: AnalyzerDatabase,
    account_id: str,
    gateway_id: str | None,
    gateway_name: str | None,
) -> str:
    resolved = resolve_gateway_locally(db, account_id, gateway_id, gateway_name)
    if not resolved:
        raise typer.BadParameter("需要提供 --gateway-id 或 --gateway-name")
    return resolved


def yaml_path_label(config: Path | None) -> str:
    resolved = resolve_yaml_path(config)
    return str(resolved) if resolved else "(none)"


def run_async(coro: Awaitable[T]) -> T:
    """Helper to drive an async coroutine from a sync Typer command."""

    return asyncio.run(coro)  # type: ignore[arg-type]


console = get_console()
