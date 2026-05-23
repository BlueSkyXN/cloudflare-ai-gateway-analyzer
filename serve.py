#!/usr/bin/env python3
"""Direct control-plane entry point: ``python serve.py``.

Equivalent to ``python cli.py serve``. Provided so deployment scripts (docker
entrypoint, systemd unit, etc.) can stay short.
"""

from __future__ import annotations

import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parent / "src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from cf_aigw_analyzer.cli import app  # noqa: E402

if __name__ == "__main__":
    sys.argv.insert(1, "serve")
    app()
