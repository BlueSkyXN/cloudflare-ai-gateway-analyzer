"""`cf-aigw-analyzer config {show,validate,template}`."""

from __future__ import annotations

import json
from pathlib import Path

import typer
import yaml

from cf_aigw_analyzer.cli._common import ConfigOption
from cf_aigw_analyzer.config import (
    load_settings,
    redact_settings,
    render_template,
    resolve_yaml_path,
)
from cf_aigw_analyzer.utils.console import get_console


def show(
    config: ConfigOption = None,
    format: str = typer.Option(
        "yaml",
        "--format",
        "-f",
        help="Output format: yaml | json.",
        case_sensitive=False,
    ),
) -> None:
    """Print the effective config with secrets redacted."""

    settings = load_settings(config)
    payload = redact_settings(settings)
    fmt = format.strip().lower()

    if fmt == "json":
        typer.echo(json.dumps(payload, indent=2, default=str, ensure_ascii=False))
    elif fmt == "yaml":
        typer.echo(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True).rstrip())
    else:
        raise typer.BadParameter(f"unsupported format: {format}")


def validate(config: ConfigOption = None) -> None:
    """Validate config.yaml against the Settings schema."""

    console = get_console()
    resolved = resolve_yaml_path(config)
    if resolved is None:
        console.print("[yellow]未发现 config.yaml；将使用环境变量与默认值。[/yellow]")
    else:
        console.print(f"读取: [bold]{resolved}[/bold]")

    try:
        settings = load_settings(config)
    except Exception as exc:
        console.print(f"[red]校验失败:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    issues: list[str] = []
    if not settings.has_credentials():
        issues.append("Cloudflare 凭证缺失：请设置 CF_API_TOKEN（推荐）或 CF_EMAIL + CF_API_KEY。")

    if issues:
        for line in issues:
            console.print(f"[yellow]warn:[/yellow] {line}")
    else:
        console.print("[green]OK[/green]")


def template(
    output: Path = typer.Option(
        Path("config-example.yaml"),
        "--output",
        "-o",
        help="Where to write the template. Use '-' for stdout.",
    ),
) -> None:
    """Render config-example.yaml from the Settings schema."""

    rendered = render_template()
    if str(output) == "-":
        typer.echo(rendered)
        return
    output.write_text(rendered, encoding="utf-8")
    get_console().print(f"已写入: [bold]{output}[/bold]")
