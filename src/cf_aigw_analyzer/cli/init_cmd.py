"""`cf-aigw-analyzer init` — create SQLite + write config-example.yaml if missing."""

from __future__ import annotations

import typer

from cf_aigw_analyzer.cli._common import ConfigOption, console, db_path_from, load
from cf_aigw_analyzer.config import render_template
from cf_aigw_analyzer.config.loader import resolve_yaml_path
from cf_aigw_analyzer.data.db import AnalyzerDatabase
from cf_aigw_analyzer.utils import paths as paths_module


def init(
    config: ConfigOption = None,
    write_example: bool = typer.Option(
        True,
        "--write-example/--no-write-example",
        help="Write config-example.yaml at project root when missing.",
    ),
) -> None:
    """Initialize SQLite at the configured path and optionally write template."""

    settings = load(config)
    db_path = db_path_from(settings)
    with AnalyzerDatabase(db_path):
        pass
    console.print(f"SQLite 已初始化: [bold]{db_path}[/bold]")

    example_path = paths_module.PROJECT_ROOT / "config-example.yaml"
    if write_example and not example_path.exists():
        example_path.write_text(render_template(), encoding="utf-8")
        console.print(f"已写入: [bold]{example_path}[/bold]")

    yaml_resolved = resolve_yaml_path(config)
    if yaml_resolved is None:
        console.print(
            "[yellow]提示[/yellow] 当前未发现 config.yaml；如需自定义，复制 config-example.yaml 为 config.yaml。"
        )
        raise typer.Exit(code=0)
