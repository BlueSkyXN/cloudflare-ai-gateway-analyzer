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
    # Inject the `sync` subcommand if the user didn't specify one explicitly.
    if len(sys.argv) > 1 and sys.argv[1] in app.registered_commands:
        app()
    else:
        sys.argv.insert(1, "sync")
        app()
