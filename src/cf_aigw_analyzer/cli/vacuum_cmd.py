"""`cf-aigw-analyzer vacuum` — run SQLite VACUUM."""

from __future__ import annotations

from cf_aigw_analyzer.cli._common import ConfigOption, console, load, open_db


def vacuum(config: ConfigOption = None) -> None:
    """Compact the SQLite database with VACUUM."""

    settings = load(config)
    with open_db(settings) as db:
        db.vacuum()
        console.print(f"SQLite VACUUM 完成: [bold]{db.path}[/bold]")
