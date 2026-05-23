"""`GET /api/v1/scopes` and gateway listing."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from cf_aigw_analyzer.analytics import list_gateway_scopes
from cf_aigw_analyzer.control.deps import get_state, readonly_conn
from cf_aigw_analyzer.control.schemas.common import GatewayItem, ScopeItem

router = APIRouter(prefix="/scopes", tags=["scopes"])


@router.get("", response_model=list[ScopeItem])
async def list_scopes(conn=Depends(readonly_conn)) -> list[ScopeItem]:
    return [ScopeItem(**row) for row in list_gateway_scopes(conn)]


@router.get("/{account_id}/gateways", response_model=list[GatewayItem])
async def list_account_gateways(account_id: str, state=Depends(get_state)) -> list[GatewayItem]:
    rows = state.db.gateways.list_for_account(account_id)
    return [
        GatewayItem(
            account_id=account_id,
            gateway_id=row["gateway_id"],
            name=row.get("name"),
            collect_logs=bool(row.get("collect_logs"))
            if row.get("collect_logs") is not None
            else None,
            fetched_at=row["fetched_at"],
        )
        for row in rows
    ]
