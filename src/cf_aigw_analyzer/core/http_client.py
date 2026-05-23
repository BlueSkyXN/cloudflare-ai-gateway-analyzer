"""Async HTTP client with tenacity-backed retries and certifi TLS.

Wraps :mod:`httpx` so the Cloudflare client and any other future caller share
the same retry policy, timeout defaults, and TLS context.
"""

from __future__ import annotations

import ssl
from collections.abc import Awaitable, Callable
from typing import Any

import certifi
import httpx
from tenacity import (
    AsyncRetrying,
    RetryError,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential_jitter,
)


def build_ssl_context() -> ssl.SSLContext:
    """Build an SSL context anchored on certifi's bundle."""

    return ssl.create_default_context(cafile=certifi.where())


def _is_retryable_response(response: httpx.Response) -> bool:
    return response.status_code == 429 or response.status_code >= 500


def _is_retryable_exception(exc: BaseException) -> bool:
    if isinstance(exc, httpx.TransportError):
        return True
    return bool(isinstance(exc, RetryableStatus))


class RetryableStatus(Exception):
    """Raised internally when a response status should trigger another attempt."""

    def __init__(self, response: httpx.Response) -> None:
        super().__init__(f"retryable status {response.status_code}")
        self.response = response


class HttpClient:
    """Thin retrying wrapper over :class:`httpx.AsyncClient`."""

    def __init__(
        self,
        base_url: str,
        *,
        headers: dict[str, str] | None = None,
        timeout: float = 30.0,
        retries: int = 3,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = httpx.Timeout(timeout)
        self.retries = max(1, int(retries))
        if client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
                headers=headers or {},
                verify=build_ssl_context(),
            )
            self._owns_client = True
        else:
            self._client = client
            self._owns_client = False

    async def __aenter__(self) -> HttpClient:
        return self

    async def __aexit__(self, *exc_info) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def get_json(self, path: str, params: dict[str, Any] | None = None) -> Any:
        response = await self._request("GET", path, params=params)
        if response.status_code == 204 or not response.content:
            return None
        try:
            return response.json()
        except ValueError:
            return response.text

    async def get(self, path: str, params: dict[str, Any] | None = None) -> httpx.Response:
        return await self._request("GET", path, params=params)

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: Any | None = None,
    ) -> httpx.Response:
        request_params = {k: v for k, v in (params or {}).items() if v is not None}

        async def _attempt() -> httpx.Response:
            response = await self._client.request(method, path, params=request_params, json=json)
            if _is_retryable_response(response):
                raise RetryableStatus(response)
            return response

        try:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(self.retries),
                wait=wait_exponential_jitter(initial=0.25, max=4.0, jitter=0.5),
                retry=retry_if_exception(_is_retryable_exception),
                reraise=True,
            ):
                with attempt:
                    return await _attempt()
        except RetryableStatus as exc:
            return exc.response
        except RetryError as exc:
            inner = exc.last_attempt.exception() if exc.last_attempt else None
            if isinstance(inner, RetryableStatus):
                return inner.response
            raise

        raise RuntimeError("retry loop exited without returning a response")


async def with_retries(
    fn: Callable[[], Awaitable[Any]],
    *,
    retries: int = 3,
    initial: float = 0.25,
    cap: float = 4.0,
) -> Any:
    """Generic helper to wrap an awaitable in the same retry policy."""

    async for attempt in AsyncRetrying(
        stop=stop_after_attempt(retries),
        wait=wait_exponential_jitter(initial=initial, max=cap, jitter=0.5),
        retry=retry_if_exception(_is_retryable_exception),
        reraise=True,
    ):
        with attempt:
            return await fn()
    raise RuntimeError("unreachable")
