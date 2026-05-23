"""`GET /api/v1/health`."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from cf_aigw_analyzer import __version__
from cf_aigw_analyzer.control.deps import get_state
from cf_aigw_analyzer.control.schemas.common import HealthResponse

router = APIRouter(tags=["meta"])


@router.get("/health", response_model=HealthResponse)
async def health(state=Depends(get_state)) -> HealthResponse:
    return HealthResponse(
        status="ok",
        version=__version__,
        database=str(state.db.path),
        database_bytes=state.db.database_bytes,
        has_credentials=state.settings.has_credentials(),
    )
