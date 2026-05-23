"""Shared pytest fixtures."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest


@pytest.fixture
def isolated_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[pytest.MonkeyPatch]:
    """Strip any host-level Cloudflare / project env vars that could leak into tests."""

    for key in (
        "CF_API_TOKEN",
        "CF_EMAIL",
        "CF_API_KEY",
        "CF_AIGW_CONFIG",
    ):
        monkeypatch.delenv(key, raising=False)
    for key_prefix in (
        "CF_AIGW_CLOUDFLARE__",
        "CF_AIGW_CONTROL__",
        "CF_AIGW_SYNC__",
        "CF_AIGW_STORAGE__",
    ):
        for env_key in list(__import__("os").environ.keys()):
            if env_key.startswith(key_prefix):
                monkeypatch.delenv(env_key, raising=False)
    yield monkeypatch


@pytest.fixture
def tmp_yaml(tmp_path: Path) -> Path:
    """Return an empty writable yaml path for tests to populate."""

    return tmp_path / "config.yaml"
