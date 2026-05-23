"""Tests for the HTTP client retry policy (no real network)."""

from __future__ import annotations

import httpx
import pytest

from cf_aigw_analyzer.core.http_client import HttpClient


@pytest.mark.asyncio
async def test_retries_on_5xx_until_success() -> None:
    call_count = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        call_count["n"] += 1
        if call_count["n"] < 3:
            return httpx.Response(503, text="busy")
        return httpx.Response(200, json={"result": [], "success": True})

    transport = httpx.MockTransport(handler)
    inner = httpx.AsyncClient(base_url="https://example.test", transport=transport)
    client = HttpClient(base_url="https://example.test", retries=5, client=inner)
    try:
        response = await client.get("/")
        assert response.status_code == 200
        assert call_count["n"] == 3
    finally:
        await inner.aclose()


@pytest.mark.asyncio
async def test_returns_4xx_without_retry() -> None:
    call_count = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        call_count["n"] += 1
        return httpx.Response(403, json={"errors": [{"message": "forbidden"}]})

    transport = httpx.MockTransport(handler)
    inner = httpx.AsyncClient(base_url="https://example.test", transport=transport)
    client = HttpClient(base_url="https://example.test", retries=4, client=inner)
    try:
        response = await client.get("/")
        assert response.status_code == 403
        assert call_count["n"] == 1
    finally:
        await inner.aclose()


@pytest.mark.asyncio
async def test_retries_on_429_and_eventually_returns() -> None:
    call_count = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        call_count["n"] += 1
        return httpx.Response(429, headers={"Retry-After": "0"}, text="slow down")

    transport = httpx.MockTransport(handler)
    inner = httpx.AsyncClient(base_url="https://example.test", transport=transport)
    client = HttpClient(base_url="https://example.test", retries=3, client=inner)
    try:
        response = await client.get("/")
        assert response.status_code == 429
        assert call_count["n"] == 3
    finally:
        await inner.aclose()
