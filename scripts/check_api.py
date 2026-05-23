"""Boot the FastAPI app in-process and walk core read-only endpoints.

Used as a non-live smoke from CI / Docker build. No network needed.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if SRC.is_dir() and str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import httpx  # noqa: E402
from pydantic import SecretStr  # noqa: E402

from cf_aigw_analyzer.config import Settings  # noqa: E402
from cf_aigw_analyzer.config.settings import CloudflareConfig, StorageConfig  # noqa: E402
from cf_aigw_analyzer.control.app import build_app  # noqa: E402
from cf_aigw_analyzer.control.lifecycle import AppState  # noqa: E402
from cf_aigw_analyzer.data.db import AnalyzerDatabase  # noqa: E402

ENDPOINTS = (
    "/api/v1/health",
    "/api/v1/scopes",
    "/api/v1/status",
    "/api/v1/analytics/summary",
    "/api/v1/analytics/timeseries",
    "/api/v1/analytics/models",
    "/api/v1/analytics/context-buckets",
    "/api/v1/analytics/insights",
    "/api/v1/events",
    "/api/v1/config",
)


async def main() -> int:
    tmp_db = ROOT / ".smoke.sqlite"
    tmp_db.unlink(missing_ok=True)
    settings = Settings(
        cloudflare=CloudflareConfig(api_token=SecretStr("smoke-tok")),
        storage=StorageConfig(data_dir=tmp_db.parent, db_filename=tmp_db.name),
    )
    db = AnalyzerDatabase(tmp_db)
    try:
        state = AppState(settings=settings, db=db)
        app = build_app(settings=settings, state=state)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://smoke") as client:
            for endpoint in ENDPOINTS:
                response = await client.get(endpoint)
                if response.status_code != 200:
                    print(f"[FAIL] {endpoint} -> {response.status_code}: {response.text[:120]}")
                    return 1
                print(f"[OK]   {endpoint}")
    finally:
        db.close()
        tmp_db.unlink(missing_ok=True)

    print("smoke passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
