"""`cf-aigw-analyzer accounts` & `gateways` discovery."""

from __future__ import annotations

import typer

from cf_aigw_analyzer.cli._common import (
    AccountOption,
    ConfigOption,
    console,
    load,
    open_db,
    require_account_id,
    run_async,
)
from cf_aigw_analyzer.core.cloudflare import CloudflareClient


def accounts(config: ConfigOption = None) -> None:
    """List Cloudflare accounts visible to the current credentials."""

    settings = load(config)

    async def _run() -> list[dict]:
        client = CloudflareClient(settings.cloudflare)
        try:
            return [a async for a in client.iter_accounts()]
        finally:
            await client.aclose()

    rows = run_async(_run())
    if not rows:
        console.print("(no accounts)")
        return
    for row in rows:
        console.print(f"- {row.get('id')}  {row.get('name')}  ({row.get('type')})")


def gateways(
    config: ConfigOption = None,
    account_id: AccountOption = None,
    save: bool = typer.Option(False, "--save", help="Persist to the local gateways table."),
) -> None:
    """List AI gateways for an account; optionally cache them locally."""

    settings = load(config)
    account = require_account_id(settings, account_id)

    async def _run() -> list[dict]:
        client = CloudflareClient(settings.cloudflare)
        try:
            return [g async for g in client.iter_gateways(account)]
        finally:
            await client.aclose()

    rows = run_async(_run())
    if not rows:
        console.print("(no gateways)")
        return

    if save:
        with open_db(settings) as db:
            saved = db.gateways.upsert_many(account, rows)
            console.print(f"已写入 SQLite: {saved} 个 gateway -> {db.path}")

    for row in rows:
        flag = "logs" if row.get("collect_logs") else "off"
        name = row.get("name") or row.get("id")
        label = f"{row.get('id')}  {name}" if name != row.get("id") else str(row.get("id"))
        console.print(f"- {label}  [{flag}]  created={row.get('created_at')}")
