"""`cf-aigw-analyzer version`."""

from __future__ import annotations

import platform
import sys

import typer

from cf_aigw_analyzer import __version__
from cf_aigw_analyzer.utils.console import get_console


def version() -> None:
    """Print version and runtime info."""

    console = get_console()
    console.print(f"[bold]cloudflare-ai-gateway-analyzer[/bold] {__version__}")
    console.print(f"  python {platform.python_version()} ({sys.executable})")
    console.print(f"  platform {platform.platform()}")
    raise typer.Exit(code=0)
