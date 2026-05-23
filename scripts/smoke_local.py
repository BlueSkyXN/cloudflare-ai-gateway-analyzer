"""Local non-live smoke driver.

Runs:

* ``python -m pytest`` (unit + integration)
* ``ruff check`` and ``ruff format --check``
* ``python scripts/check_api.py``
* ``python scripts/generate_openapi.py``

Does NOT call Cloudflare, does NOT spawn npm. Suitable for CI and Docker build
sanity checks.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


STEPS: list[tuple[str, list[str]]] = [
    ("ruff check", ["ruff", "check", "src", "tests", "scripts", "cli.py", "main.py", "serve.py"]),
    (
        "ruff format --check",
        ["ruff", "format", "--check", "src", "tests", "scripts", "cli.py", "main.py", "serve.py"],
    ),
    ("pytest", [sys.executable, "-m", "pytest", "-q"]),
    (
        "openapi export",
        [sys.executable, "scripts/generate_openapi.py", "--output", "local/openapi.json"],
    ),
    ("api smoke", [sys.executable, "scripts/check_api.py"]),
]


def main() -> int:
    env = {
        "PYTHONPATH": str(ROOT / "src"),
        **dict(__import__("os").environ),
    }
    for label, command in STEPS:
        print(f"\n==> {label}: {' '.join(command)}")
        result = subprocess.run(command, cwd=ROOT, env=env)
        if result.returncode != 0:
            print(f"[FAIL] {label}")
            return result.returncode
        print(f"[OK]   {label}")
    print("\nsmoke green")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
