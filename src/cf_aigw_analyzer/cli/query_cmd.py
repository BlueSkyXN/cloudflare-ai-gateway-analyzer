"""`cf-aigw-analyzer query` — read local SQLite + emit table/json/csv."""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from typing import Any

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
    require_local_gateway,
)
from cf_aigw_analyzer.data import LogQueryFilters
from cf_aigw_analyzer.models.enums import OutputFormat

DEFAULT_COLUMNS = (
    "log_id",
    "created_at",
    "provider",
    "model",
    "model_type",
    "success",
    "cached",
    "status_code",
    "input_tokens",
    "output_tokens",
    "total_tokens",
    "cached_tokens",
    "reasoning_tokens",
    "duration_ms",
    "latency_ms",
    "total_ms",
    "generation_ms",
    "output_tps",
    "usage_fetch_status",
)


def query(
    config: ConfigOption = None,
    account_id: AccountOption = None,
    gateway_id: GatewayIdOption = None,
    gateway_name: GatewayNameOption = None,
    start_date: str = typer.Option(None, "--start-date"),
    end_date: str = typer.Option(None, "--end-date"),
    provider: str = typer.Option(None, "--provider"),
    model: str = typer.Option(None, "--model"),
    model_type: str = typer.Option(None, "--model-type"),
    success: bool = typer.Option(None, "--success/--no-success"),
    cached: bool = typer.Option(None, "--cached/--no-cached"),
    search: str = typer.Option(None, "--search"),
    limit: int = typer.Option(50, "--limit", min=1, max=10_000),
    format: OutputFormat = typer.Option(
        OutputFormat.TABLE,
        "--format",
        "-f",
        case_sensitive=False,
    ),
    output: Path | None = typer.Option(None, "--output", "-o"),
    include_raw_json: bool = typer.Option(False, "--include-raw-json"),
    include_scope: bool = typer.Option(False, "--include-scope"),
) -> None:
    """Query local SQLite logs and emit table/JSON/CSV. Loopback safe by default."""

    settings = load(config)
    account = require_account_id(settings, account_id)

    with open_db(settings) as db:
        gateway = require_local_gateway(db, account, gateway_id, gateway_name)
        rows = db.logs.query(
            LogQueryFilters(
                account_id=account,
                gateway_id=gateway,
                start_date=start_date,
                end_date=end_date,
                provider=provider,
                model=model,
                model_type=model_type,
                success=success,
                cached=cached,
                search=search,
                limit=limit,
            )
        )

    sanitized = _sanitize_rows(rows, include_raw_json=include_raw_json, include_scope=include_scope)
    _emit(sanitized, format, output)


def _sanitize_rows(
    rows: list[dict[str, Any]],
    *,
    include_raw_json: bool,
    include_scope: bool,
) -> list[dict[str, Any]]:
    excluded: set[str] = set()
    if not include_raw_json:
        excluded.add("raw_json")
    if not include_scope:
        excluded.update({"account_id", "gateway_id"})
    return [{key: value for key, value in row.items() if key not in excluded} for row in rows]


def _emit(rows: list[dict[str, Any]], fmt: OutputFormat, output: Path | None) -> None:
    if fmt == OutputFormat.JSON:
        text = json.dumps(rows, indent=2, ensure_ascii=False, default=str)
        if output:
            output.write_text(text + "\n", encoding="utf-8")
            console.print(f"已输出 {len(rows)} 条 -> [bold]{output}[/bold]")
        else:
            typer.echo(text)
        return

    if fmt == OutputFormat.CSV:
        if output:
            with output.open("w", encoding="utf-8", newline="") as handle:
                _write_csv(rows, handle)
            console.print(f"已输出 {len(rows)} 条 -> [bold]{output}[/bold]")
        else:
            _write_csv(rows, sys.stdout)
        return

    if not rows:
        console.print("(no rows)")
        return

    columns = [col for col in DEFAULT_COLUMNS if col in rows[0]]
    if not columns:
        columns = list(rows[0].keys())

    widths = {col: len(col) for col in columns}
    rendered: list[dict[str, str]] = []
    for row in rows:
        item = {}
        for col in columns:
            value = _stringify(row.get(col))
            if len(value) > 48:
                value = value[:45] + "..."
            item[col] = value
            widths[col] = max(widths[col], len(value))
        rendered.append(item)

    typer.echo(" | ".join(col.ljust(widths[col]) for col in columns))
    typer.echo("-+-".join("-" * widths[col] for col in columns))
    for row in rendered:
        typer.echo(" | ".join(row[col].ljust(widths[col]) for col in columns))
    console.print(f"\n本次返回 [bold]{len(rows)}[/bold] 条")


def _write_csv(rows: list[dict[str, Any]], handle) -> None:
    if not rows:
        return
    fieldnames = list(rows[0].keys())
    for row in rows[1:]:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)
