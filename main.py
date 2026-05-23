#!/usr/bin/env python3
"""Direct sync entry point: ``python main.py``.

Equivalent to ``python cli.py sync …`` but with a shorter invocation suitable
for cron and PyInstaller-style single-file builds. All flags are forwarded.
"""

from __future__ import annotations

import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parent / "src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from cf_aigw_analyzer.cli import app  # noqa: E402


def _registered_top_level_names() -> set[str]:
    """Return Typer command/group names registered on the shared CLI app."""

    names: set[str] = set()
    for command in app.registered_commands:
        if command.name:
            names.add(command.name)
        elif command.callback is not None:
            names.add(command.callback.__name__.replace("_", "-"))
    for group in app.registered_groups:
        if group.name:
            names.add(group.name)
    return names


if __name__ == "__main__":
    # Inject the `sync` subcommand when the user did not specify any other
    # action. Top-level flags like --help / -h / --version must pass through
    # so users still get the full Typer help text from `python main.py --help`.
    passthrough = {"--help", "-h", "--version"}
    first = sys.argv[1] if len(sys.argv) > 1 else ""
    if first in _registered_top_level_names() or first in passthrough:
        app()
    else:
        sys.argv.insert(1, "sync")
        app()
