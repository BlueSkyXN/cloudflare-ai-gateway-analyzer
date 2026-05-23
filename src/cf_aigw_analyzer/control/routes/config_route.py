"""`GET /api/v1/config` — redacted Settings snapshot."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from cf_aigw_analyzer.config import redact_settings
from cf_aigw_analyzer.control.deps import get_settings

router = APIRouter(prefix="/config", tags=["config"])


@router.get("")
async def get_config(settings=Depends(get_settings)) -> dict[str, Any]:
    return redact_settings(settings)
