"""Async Cloudflare AI Gateway client.

Only covers the endpoints we need:

* ``GET /accounts``
* ``GET /accounts/{aid}/ai-gateway/gateways``
* ``GET /accounts/{aid}/ai-gateway/gateways/{gid}/logs``
* ``GET /accounts/{aid}/ai-gateway/gateways/{gid}/logs/{lid}/response``
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

import httpx

from cf_aigw_analyzer.config.settings import CloudflareConfig
from cf_aigw_analyzer.core.http_client import HttpClient

MAX_PER_PAGE = 50


class CloudflareApiError(RuntimeError):
    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass(slots=True)
class LogFilters:
    """Filters for ``iter_logs``. Maps directly to Cloudflare query string."""

    page: int = 1
    per_page: int = MAX_PER_PAGE
    order_by: str | None = None
    direction: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    model: str | None = None
    provider: str | None = None
    model_type: str | None = None
    search: str | None = None
    cached: bool | None = None
    success: bool | None = None
    feedback: int | None = None
    min_cost: float | None = None
    max_cost: float | None = None
    min_duration: float | None = None
    max_duration: float | None = None
    min_tokens_in: int | None = None
    max_tokens_in: int | None = None
    min_tokens_out: int | None = None
    max_tokens_out: int | None = None
    min_total_tokens: int | None = None
    max_total_tokens: int | None = None
    meta_info: bool = False

    def to_query(self) -> dict[str, Any]:
        params: dict[str, Any] = {
            "page": max(1, self.page),
            "per_page": min(max(1, self.per_page), MAX_PER_PAGE),
        }
        optional: dict[str, Any] = {
            "order_by": self.order_by,
            "order_by_direction": self.direction,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "model": self.model,
            "provider": self.provider,
            "model_type": self.model_type,
            "search": self.search,
            "feedback": self.feedback,
            "min_cost": self.min_cost,
            "max_cost": self.max_cost,
            "min_duration": self.min_duration,
            "max_duration": self.max_duration,
            "min_tokens_in": self.min_tokens_in,
            "max_tokens_in": self.max_tokens_in,
            "min_tokens_out": self.min_tokens_out,
            "max_tokens_out": self.max_tokens_out,
            "min_total_tokens": self.min_total_tokens,
            "max_total_tokens": self.max_total_tokens,
        }
        for key, value in optional.items():
            if value is not None and value != "":
                params[key] = value
        if self.cached is not None:
            params["cached"] = "true" if self.cached else "false"
        if self.success is not None:
            params["success"] = "true" if self.success else "false"
        if self.meta_info:
            params["meta_info"] = "true"
        return params


class CloudflareClient:
    """Async wrapper that returns parsed dict results from Cloudflare API."""

    def __init__(self, config: CloudflareConfig, *, http: HttpClient | None = None) -> None:
        if not config.api_token and not (config.email and config.api_key):
            raise CloudflareApiError(
                "缺少认证信息：请设置 CF_API_TOKEN，或同时提供 CF_EMAIL + CF_API_KEY。"
            )
        self.config = config
        self._http = http or HttpClient(
            base_url=config.base_url,
            headers=self._build_headers(),
            timeout=config.timeout,
            retries=config.retries,
        )

    def _build_headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/json",
            "User-Agent": "cloudflare-ai-gateway-analyzer/0.3",
        }
        if self.config.api_token:
            headers["Authorization"] = f"Bearer {self.config.api_token.get_secret_value()}"
        else:
            headers["X-Auth-Email"] = self.config.email or ""
            headers["X-Auth-Key"] = (
                self.config.api_key.get_secret_value() if self.config.api_key else ""
            )
        return headers

    async def __aenter__(self) -> CloudflareClient:
        return self

    async def __aexit__(self, *exc_info) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._http.aclose()

    async def _get_result(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        response = await self._http.get(path, params=params)
        payload = self._parse(response)
        if response.is_error:
            raise CloudflareApiError(
                _error_message(payload, response.status_code), response.status_code
            )
        if isinstance(payload, dict) and payload.get("success") is False:
            raise CloudflareApiError(
                _error_message(payload, response.status_code), response.status_code
            )
        if not isinstance(payload, dict):
            raise CloudflareApiError("Cloudflare 返回了非 JSON 响应。", response.status_code)
        return payload

    def _parse(self, response: httpx.Response) -> Any:
        if not response.content:
            return None
        try:
            return response.json()
        except ValueError:
            return response.text

    async def iter_accounts(self) -> AsyncIterator[dict[str, Any]]:
        async for account in self._iter_paginated("/accounts"):
            yield account

    async def iter_gateways(self, account_id: str) -> AsyncIterator[dict[str, Any]]:
        async for gateway in self._iter_paginated(f"/accounts/{account_id}/ai-gateway/gateways"):
            yield gateway

    async def resolve_gateway_id(self, account_id: str, name_or_id: str) -> str | None:
        async for gateway in self.iter_gateways(account_id):
            if gateway.get("id") == name_or_id or gateway.get("name") == name_or_id:
                return str(gateway.get("id"))
        return None

    async def iter_logs(
        self,
        account_id: str,
        gateway_id: str,
        filters: LogFilters,
        *,
        limit: int | None = None,
        throttle_ms: int = 200,
    ) -> AsyncIterator[dict[str, Any]]:
        path = f"/accounts/{account_id}/ai-gateway/gateways/{gateway_id}/logs"
        params = filters.to_query()
        fetched = 0

        while True:
            payload = await self._get_result(path, params=params)
            rows = payload.get("result") or []
            if not isinstance(rows, list) or not rows:
                return
            for row in rows:
                if not isinstance(row, dict):
                    continue
                yield row
                fetched += 1
                if limit is not None and fetched >= limit:
                    return

            result_info = payload.get("result_info") or {}
            total = result_info.get("total_count")
            if isinstance(total, int) and params["page"] * params["per_page"] >= total:
                return
            if len(rows) < params["per_page"]:
                return
            params["page"] = int(params["page"]) + 1
            if throttle_ms > 0:
                await asyncio.sleep(throttle_ms / 1000.0)

    async def fetch_log_response(
        self, account_id: str, gateway_id: str, log_id: str
    ) -> tuple[int, Any]:
        path = f"/accounts/{account_id}/ai-gateway/gateways/{gateway_id}/logs/{log_id}/response"
        response = await self._http.get(path)
        payload = self._parse(response)
        return response.status_code, payload

    async def _iter_paginated(self, path: str) -> AsyncIterator[dict[str, Any]]:
        page = 1
        while True:
            payload = await self._get_result(path, params={"page": page, "per_page": MAX_PER_PAGE})
            rows = payload.get("result") or []
            if not isinstance(rows, list) or not rows:
                return
            for row in rows:
                if isinstance(row, dict):
                    yield row
            result_info = payload.get("result_info") or {}
            total = result_info.get("total_count")
            if isinstance(total, int) and page * MAX_PER_PAGE >= total:
                return
            if len(rows) < MAX_PER_PAGE:
                return
            page += 1


def _error_message(payload: Any, status_code: int) -> str:
    if isinstance(payload, dict):
        errors = payload.get("errors")
        if isinstance(errors, list) and errors:
            messages = []
            for item in errors:
                if isinstance(item, dict):
                    messages.append(str(item.get("message", item)))
                else:
                    messages.append(str(item))
            return "; ".join(messages)
        if payload.get("message"):
            return str(payload["message"])
    return f"HTTP {status_code}"
