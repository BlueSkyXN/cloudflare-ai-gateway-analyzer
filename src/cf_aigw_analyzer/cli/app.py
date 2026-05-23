"""Top-level Typer application wiring."""

from __future__ import annotations

import typer

from cf_aigw_analyzer.cli import (
    config_cmd,
    discover_cmd,
    init_cmd,
    query_cmd,
    serve_cmd,
    status_cmd,
    sync_cmd,
    usage_cmd,
    vacuum_cmd,
    version_cmd,
)

app = typer.Typer(
    name="cf-aigw-analyzer",
    help=(
        "Cloudflare AI Gateway log collector + SQLite analyzer with an optional "
        "FastAPI control plane and React panel."
    ),
    no_args_is_help=True,
    add_completion=False,
    rich_markup_mode="rich",
)


config_app = typer.Typer(
    help="Inspect and validate the local config.yaml.",
    no_args_is_help=True,
)
config_app.command("show")(config_cmd.show)
config_app.command("validate")(config_cmd.validate)
config_app.command("template")(config_cmd.template)
app.add_typer(config_app, name="config")


app.command("version")(version_cmd.version)
app.command("init")(init_cmd.init)
app.command("accounts")(discover_cmd.accounts)
app.command("gateways")(discover_cmd.gateways)
app.command("sync")(sync_cmd.sync)
app.command("sync-usage")(usage_cmd.sync_usage)
app.command("query")(query_cmd.query)
app.command("status")(status_cmd.status)
app.command("vacuum")(vacuum_cmd.vacuum)
app.command("serve")(serve_cmd.serve)


__all__ = ["app"]
