"""Dump the OpenAPI schema to a file.

Usage::

    python scripts/generate_openapi.py --output local/openapi.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if SRC.is_dir() and str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from cf_aigw_analyzer.config import Settings  # noqa: E402
from cf_aigw_analyzer.control.app import build_app  # noqa: E402
from cf_aigw_analyzer.control.lifecycle import AppState  # noqa: E402
from cf_aigw_analyzer.data.db import AnalyzerDatabase  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("local/openapi.json"))
    args = parser.parse_args()

    tmp_db = Path(".openapi-tmp.sqlite")
    settings = Settings()
    db = AnalyzerDatabase(tmp_db)
    try:
        state = AppState(settings=settings, db=db)
        app = build_app(settings=settings, state=state)
        schema = app.openapi()
    finally:
        db.close()
        if tmp_db.exists():
            tmp_db.unlink()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(schema, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {args.output} ({len(schema.get('paths', {}))} paths)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
