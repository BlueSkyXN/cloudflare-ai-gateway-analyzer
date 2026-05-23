#!/usr/bin/env python3
"""Top-level CLI entry script.

Supports both development (``python cli.py``) and editable-installed
(``cf-aigw-analyzer``) invocation. When running from source, this script
inserts ``src/`` into ``sys.path`` so imports resolve without a wheel install.
"""

from __future__ import annotations

import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parent / "src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from cf_aigw_analyzer.cli import app  # noqa: E402

if __name__ == "__main__":
    app()
