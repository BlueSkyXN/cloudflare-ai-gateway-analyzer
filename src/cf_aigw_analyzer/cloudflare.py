"""Cloudflare AI Gateway API client."""

from __future__ import annotations

import json
import os
import ssl
import time
from dataclasses import dataclass
from typing import Any, Iterator
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .filters import LogFilters, MAX_PER_PAGE

DEFAULT_BASE_URL = "https://api.cloudflare.com/client/v4"


class CloudflareApiError(RuntimeError):
    """Raised when Cloudflare API calls fail after retries."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


@dataclass(slots=True)
class ApiPayload:
    data: Any
    status_code: int


def _json_or_text(raw: bytes) -> Any:
    text = raw.decode("utf-8", errors="replace")
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


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


class CloudflareClient:
    """Small stdlib-only client for the Cloudflare API endpoints we need."""

    def __init__(
        self,
        api_token: str | None = None,
        email: str | None = None,
        api_key: str | None = None,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 30.0,
        retries: int = 3,
        ssl_context: ssl.SSLContext | None = None,
    ):
        self.api_token = api_token or os.getenv("CF_API_TOKEN")
        self.email = email or os.getenv("CF_EMAIL")
        self.api_key = api_key or os.getenv("CF_API_KEY")
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.retries = max(1, retries)
        self.ssl_context = ssl_context or self._build_ssl_context()

        if not self.api_token and not (self.email and self.api_key):
            raise CloudflareApiError("缺少认证信息：请设置 CF_API_TOKEN，或提供 CF_EMAIL + CF_API_KEY。")

    @staticmethod
    def _build_ssl_context() -> ssl.SSLContext:
        try:
            import certifi

            return ssl.create_default_context(cafile=certifi.where())
        except Exception:
            return ssl.create_default_context()

    @property
    def headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/json",
            "User-Agent": "cloudflare-ai-gateway-analyzer/0.2",
        }
        if self.api_token:
            headers["Authorization"] = f"Bearer {self.api_token}"
        else:
            headers["X-Auth-Email"] = str(self.email)
            headers["X-Auth-Key"] = str(self.api_key)
        return headers

    def get(self, path: str, params: dict[str, Any] | None = None) -> ApiPayload:
        url = f"{self.base_url}{path}"
        if params:
            query = urlencode({k: v for k, v in params.items() if v is not None})
            url = f"{url}?{query}"

        last_error: str | None = None
        last_status: int | None = None
        for attempt in range(1, self.retries + 1):
            request = Request(url, headers=self.headers, method="GET")
            try:
                with urlopen(request, timeout=self.timeout, context=self.ssl_context) as response:
                    payload = _json_or_text(response.read())
                    return ApiPayload(payload, response.status)
            except HTTPError as exc:
                payload = _json_or_text(exc.read())
                last_status = exc.code
                last_error = _error_message(payload, exc.code)
                if exc.code == 429 and attempt < self.retries:
                    wait = float(exc.headers.get("Retry-After") or attempt)
                    time.sleep(wait)
                    continue
                if exc.code >= 500 and attempt < self.retries:
                    time.sleep(float(attempt))
                    continue
                break
            except URLError as exc:
                last_error = str(exc.reason)
                if attempt < self.retries:
                    time.sleep(float(attempt))
                    continue
                break

        raise CloudflareApiError(last_error or "Cloudflare API 请求失败", last_status)

    def get_cloudflare_result(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = self.get(path, params).data
        if not isinstance(payload, dict):
            raise CloudflareApiError("Cloudflare 返回了非 JSON 响应。")
        if payload.get("success") is False:
            raise CloudflareApiError(_error_message(payload, 200), 200)
        return payload

    def iter_accounts(self) -> Iterator[dict[str, Any]]:
        page = 1
        while True:
            payload = self.get_cloudflare_result(
                "/accounts",
                {"page": page, "per_page": MAX_PER_PAGE},
            )
            rows = payload.get("result") or []
            if not isinstance(rows, list) or not rows:
                return
            yield from rows
            result_info = payload.get("result_info") or {}
            total_count = result_info.get("total_count")
            if isinstance(total_count, int) and page * MAX_PER_PAGE >= total_count:
                return
            if len(rows) < MAX_PER_PAGE:
                return
            page += 1

    def iter_gateways(self, account_id: str) -> Iterator[dict[str, Any]]:
        page = 1
        while True:
            payload = self.get_cloudflare_result(
                f"/accounts/{account_id}/ai-gateway/gateways",
                {"page": page, "per_page": MAX_PER_PAGE},
            )
            rows = payload.get("result") or []
            if not isinstance(rows, list) or not rows:
                return
            yield from rows
            result_info = payload.get("result_info") or {}
            total_count = result_info.get("total_count")
            if isinstance(total_count, int) and page * MAX_PER_PAGE >= total_count:
                return
            if len(rows) < MAX_PER_PAGE:
                return
            page += 1

    def resolve_gateway_id(self, account_id: str, gateway_name_or_id: str) -> str | None:
        for gateway in self.iter_gateways(account_id):
            if gateway.get("id") == gateway_name_or_id or gateway.get("name") == gateway_name_or_id:
                return str(gateway.get("id"))
        return None

    def iter_logs(
        self,
        account_id: str,
        gateway_id: str,
        filters: LogFilters,
        limit: int | None = None,
    ) -> Iterator[dict[str, Any]]:
        path = f"/accounts/{account_id}/ai-gateway/gateways/{gateway_id}/logs"
        params = filters.to_api_params()
        fetched = 0

        while True:
            payload = self.get_cloudflare_result(path, params)
            rows = payload.get("result") or []
            if not isinstance(rows, list) or not rows:
                return

            for row in rows:
                if isinstance(row, dict):
                    yield row
                    fetched += 1
                    if limit and fetched >= limit:
                        return

            result_info = payload.get("result_info") or {}
            total_count = result_info.get("total_count")
            if isinstance(total_count, int) and params["page"] * params["per_page"] >= total_count:
                return
            if len(rows) < params["per_page"]:
                return
            params["page"] += 1
            time.sleep(0.2)

    def fetch_log_response(self, account_id: str, gateway_id: str, log_id: str) -> ApiPayload:
        return self.get(f"/accounts/{account_id}/ai-gateway/gateways/{gateway_id}/logs/{log_id}/response")
