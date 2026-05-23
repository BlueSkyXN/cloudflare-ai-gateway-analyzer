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

if __name__ == "__main__":
    # Inject the `sync` subcommand when the user did not specify any other
    # action. Top-level flags like --help / -h / --version must pass through
    # so users still get the full Typer help text from `python main.py --help`.
    passthrough = {"--help", "-h", "--version"}
    first = sys.argv[1] if len(sys.argv) > 1 else ""
    if first in app.registered_commands or first in passthrough:
        app()
    else:
        sys.argv.insert(1, "sync")
        app()
