"""`cf-aigw-analyzer sync-usage` — response usage backfill."""

from __future__ import annotations

import typer

from cf_aigw_analyzer.cli._common import (
    AccountOption,
    ConfigOption,
    GatewayIdOption,
    GatewayNameOption,
    console,
    load,
    open_db,
    require_account_id,
    run_async,
)
from cf_aigw_analyzer.cli.sync_cmd import _resolve_gateway
from cf_aigw_analyzer.core.cloudflare import CloudflareClient
from cf_aigw_analyzer.core.sync_engine import SyncEngine
from cf_aigw_analyzer.data.repository import SyncLockBusy


def sync_usage(
    config: ConfigOption = None,
    account_id: AccountOption = None,
    gateway_id: GatewayIdOption = None,
    gateway_name: GatewayNameOption = None,
    missing_only: bool = typer.Option(False, "--missing-only"),
    refresh: bool = typer.Option(False, "--refresh"),
    retry_failed: bool | None = typer.Option(
        None,
        "--retry-failed/--no-retry-failed",
        help="Override sync.retry_failed for this run.",
    ),
    workers: int | None = typer.Option(None, "--usage-workers", min=1, max=64),
    limit: int | None = typer.Option(None, "--limit", min=1),
) -> None:
    """Fetch response usage for logs that still need it."""

    settings = load(config)
    account = require_account_id(settings, account_id)

    async def _run() -> None:
        with open_db(settings) as db:
            client = CloudflareClient(settings.cloudflare)
            try:
                resolved_gateway = await _resolve_gateway(
                    client, db, account, gateway_id, gateway_name
                )
                engine = SyncEngine(settings, db, client=client)
                result = await engine.sync_usage(
                    account,
                    resolved_gateway,
                    missing_only=missing_only,
                    refresh=refresh,
                    retry_failed=retry_failed,
                    workers=workers,
                    limit=limit,
                )
                console.print(
                    f"usage 同步完成: targets={result.targets}, fetched={result.fetched}, "
                    f"parsed={result.parsed}, no_usage={result.no_usage}, failed={result.failed} -> {db.path}"
                )
            finally:
                await client.aclose()

    try:
        run_async(_run())
    except SyncLockBusy as exc:
        raise typer.BadParameter(str(exc)) from exc
