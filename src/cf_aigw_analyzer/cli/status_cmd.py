"""`cf-aigw-analyzer status` — print DB summary."""

from __future__ import annotations

import json

import typer

from cf_aigw_analyzer.cli._common import (
    AccountOption,
    ConfigOption,
    GatewayIdOption,
    GatewayNameOption,
    load,
    open_db,
    resolve_gateway_locally,
)


def status(
    config: ConfigOption = None,
    account_id: AccountOption = None,
    gateway_id: GatewayIdOption = None,
    gateway_name: GatewayNameOption = None,
) -> None:
    """Print SQLite status as JSON: log counts, usage breakdown, last run."""

    settings = load(config)

    with open_db(settings) as db:
        account = account_id or settings.control.default_account_id
        gateway = (
            resolve_gateway_locally(db, account, gateway_id, gateway_name) if account else None
        )
        summary = db.logs.summary(account, gateway)
        usage_counts = db.usage.status_counts(account, gateway)
        last_run = db.sync_runs.last(account, gateway)

        payload = {
            "database": str(db.path),
            "database_bytes": db.database_bytes,
            "total_logs": summary["total_logs"],
            "first_log_at": summary["first_log_at"],
            "last_log_at": summary["last_log_at"],
            "usage_parsed": usage_counts.get("parsed", 0),
            "usage_no_usage": usage_counts.get("no_usage", 0),
            "usage_failed": usage_counts.get("failed", 0),
            "last_run": last_run,
        }
    typer.echo(json.dumps(payload, indent=2, ensure_ascii=False, default=str))
