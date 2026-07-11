"""`cf-aigw-analyzer sync` — Cloudflare metadata sync."""

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
from cf_aigw_analyzer.core.cloudflare import CloudflareClient, LogFilters
from cf_aigw_analyzer.core.sync_engine import SyncEngine
from cf_aigw_analyzer.data.repository import SyncLockBusy


def sync(
    config: ConfigOption = None,
    account_id: AccountOption = None,
    gateway_id: GatewayIdOption = None,
    gateway_name: GatewayNameOption = None,
    limit: int | None = typer.Option(
        None, "--limit", min=1, help="Maximum metadata rows to fetch."
    ),
    order_by: str = typer.Option(None, "--order-by"),
    direction: str = typer.Option(None, "--direction"),
    start_date: str = typer.Option(None, "--start-date"),
    end_date: str = typer.Option(None, "--end-date"),
    model: str = typer.Option(None, "--model"),
    provider: str = typer.Option(None, "--provider"),
    model_type: str = typer.Option(None, "--model-type"),
    success: bool = typer.Option(None, "--success/--no-success"),
    cached: bool = typer.Option(None, "--cached/--no-cached"),
    with_usage: bool = typer.Option(False, "--with-usage", help="Run sync-usage afterwards."),
    missing_only: bool = typer.Option(False, "--missing-only"),
    refresh_usage: bool = typer.Option(False, "--refresh-usage"),
    no_retry_failed: bool = typer.Option(False, "--no-retry-failed"),
    usage_workers: int | None = typer.Option(None, "--usage-workers", min=1, max=64),
    usage_limit: int | None = typer.Option(None, "--usage-limit", min=1),
    incremental: bool = typer.Option(
        False,
        "--incremental",
        help="Use the local sync_state checkpoint with a small overlap window.",
    ),
) -> None:
    """Sync Cloudflare AI Gateway log metadata (and optionally response usage)."""

    settings = load(config)
    account = require_account_id(settings, account_id)
    filters = LogFilters(
        per_page=settings.sync.per_page,
        order_by=order_by,
        direction=direction,
        start_date=start_date,
        end_date=end_date,
        model=model,
        provider=provider,
        model_type=model_type,
        success=success,
        cached=cached,
    )

    async def _run() -> None:
        with open_db(settings) as db:
            client = CloudflareClient(settings.cloudflare)
            try:
                resolved_gateway = await _resolve_gateway(
                    client, db, account, gateway_id, gateway_name
                )
                engine = SyncEngine(settings, db, client=client)
                meta = await engine.sync_logs(
                    account,
                    resolved_gateway,
                    filters,
                    limit=limit,
                    incremental=incremental,
                )
                console.print(f"metadata 同步完成: {meta.logs_count} 条 -> {db.path}")
                if with_usage:
                    usage = await engine.sync_usage(
                        account,
                        resolved_gateway,
                        missing_only=missing_only,
                        refresh=refresh_usage,
                        retry_failed=False if no_retry_failed else None,
                        workers=usage_workers,
                        limit=usage_limit,
                    )
                    console.print(
                        "usage 同步完成: "
                        f"targets={usage.targets}, fetched={usage.fetched}, "
                        f"parsed={usage.parsed}, no_usage={usage.no_usage}, failed={usage.failed}"
                    )
            finally:
                await client.aclose()

    try:
        run_async(_run())
    except (SyncLockBusy, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc


async def _resolve_gateway(
    client: CloudflareClient,
    db,
    account_id: str,
    gateway_id: str | None,
    gateway_name: str | None,
) -> str:
    if gateway_id:
        return gateway_id
    if gateway_name:
        local = db.gateways.resolve_gateway_id(account_id, gateway_name)
        if local:
            return local
        remote = await client.resolve_gateway_id(account_id, gateway_name)
        if remote:
            return remote
        raise typer.BadParameter(f"未找到 gateway: {gateway_name}")
    raise typer.BadParameter("需要提供 --gateway-id 或 --gateway-name")
