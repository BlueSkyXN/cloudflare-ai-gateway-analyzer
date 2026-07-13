"""Integration smoke tests for the Typer CLI (no real Cloudflare)."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import httpx
import pytest
from typer.testing import CliRunner

from cf_aigw_analyzer.cli import app
from cf_aigw_analyzer.core.cloudflare import CloudflareClient
from cf_aigw_analyzer.core.http_client import HttpClient
from cf_aigw_analyzer.core.sync_engine import SyncMetadataResult, SyncUsageResult

runner = CliRunner()


@pytest.fixture
def project_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Run CLI from a fresh tmp dir so PROJECT_ROOT-derived defaults stay local."""

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "cf_aigw_analyzer.utils.paths.PROJECT_ROOT",
        tmp_path,
        raising=True,
    )
    monkeypatch.setattr(
        "cf_aigw_analyzer.config.loader.PROJECT_ROOT",
        tmp_path,
        raising=True,
    )
    return tmp_path


def test_version_command_outputs_marker(project_root: Path) -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "cloudflare-ai-gateway-analyzer" in result.stdout


def test_init_creates_database_and_template(project_root: Path) -> None:
    result = runner.invoke(app, ["init"])
    assert result.exit_code == 0
    assert (project_root / "config-example.yaml").exists()


def test_config_show_yaml(project_root: Path) -> None:
    result = runner.invoke(app, ["config", "show"])
    assert result.exit_code == 0
    assert "control:" in result.stdout
    assert "port:" in result.stdout


def test_config_validate_without_credentials_warns(
    project_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("CF_API_TOKEN", raising=False)
    monkeypatch.delenv("CF_EMAIL", raising=False)
    monkeypatch.delenv("CF_API_KEY", raising=False)
    result = runner.invoke(app, ["config", "validate"])
    assert result.exit_code == 0
    assert "Cloudflare 凭证缺失" in result.stdout


def test_status_command_on_fresh_db(project_root: Path) -> None:
    runner.invoke(app, ["init"])
    result = runner.invoke(app, ["status"])
    assert result.exit_code == 0
    assert '"total_logs": 0' in result.stdout


def test_serve_reload_is_rejected_before_uvicorn(project_root: Path) -> None:
    result = runner.invoke(app, ["serve", "--reload"])
    assert result.exit_code == 2
    assert "--reload 当前不支持" in result.stdout


@pytest.mark.parametrize(
    ("args", "expected"),
    [
        (["status", "--help"], "Usage: main.py status"),
        (["version"], "cloudflare-ai-gateway-analyzer"),
        (["config", "show", "--help"], "Usage: main.py config show"),
    ],
)
def test_main_entrypoint_does_not_rewrite_known_commands(
    args: list[str],
    expected: str,
) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(repo_root / "src")

    result = subprocess.run(
        [sys.executable, str(repo_root / "main.py"), *args],
        cwd=repo_root,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )

    output = result.stdout + result.stderr
    assert result.returncode == 0, output
    assert expected in output
    assert "Usage: main.py sync" not in output


def test_query_requires_gateway(project_root: Path) -> None:
    runner.invoke(app, ["init"])
    result = runner.invoke(app, ["query", "--account-id", "acct"])
    # Typer surfaces BadParameter as exit code 2
    assert result.exit_code != 0
    output = result.stdout + result.output
    assert "--gateway-id" in output or "BadParameter" in output


@pytest.mark.parametrize(
    ("args", "expected"),
    [
        (["sync", "--limit", "0"], "--limit"),
        (["sync", "--usage-limit", "0"], "--usage-limit"),
        (["sync", "--usage-workers", "0"], "--usage-workers"),
        (["sync-usage", "--limit", "0"], "--limit"),
        (["sync-usage", "--usage-workers", "0"], "--usage-workers"),
    ],
)
def test_sync_commands_reject_non_positive_limits(
    project_root: Path,
    args: list[str],
    expected: str,
) -> None:
    result = runner.invoke(app, args)
    assert result.exit_code != 0
    assert expected in (result.stdout + result.output)


@pytest.mark.parametrize(
    ("flag", "expected"),
    [("--retry-failed", True), ("--no-retry-failed", False)],
)
def test_sync_usage_retry_failed_flag_overrides_config(
    project_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    flag: str,
    expected: bool,
) -> None:
    monkeypatch.setenv("CF_API_TOKEN", "tok")
    monkeypatch.setenv("CF_AIGW_SYNC__RETRY_FAILED", "false")
    seen: list[bool | None] = []

    async def fake_sync_usage(self, account_id, gateway_id, *, retry_failed=None, **kwargs):
        seen.append(retry_failed)
        return SyncUsageResult()

    monkeypatch.setattr(
        "cf_aigw_analyzer.core.sync_engine.SyncEngine.sync_usage",
        fake_sync_usage,
    )
    result = runner.invoke(
        app,
        [
            "sync-usage",
            "--account-id",
            "acct",
            "--gateway-id",
            "gw",
            flag,
        ],
    )

    assert result.exit_code == 0, result.output
    assert seen == [expected]


def test_combined_sync_retry_failed_flag_is_forwarded(
    project_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CF_API_TOKEN", "tok")
    seen: list[bool | None] = []

    async def fake_sync_logs(self, account_id, gateway_id, filters, **kwargs):
        return SyncMetadataResult()

    async def fake_sync_usage(self, account_id, gateway_id, *, retry_failed=None, **kwargs):
        seen.append(retry_failed)
        return SyncUsageResult()

    monkeypatch.setattr(
        "cf_aigw_analyzer.core.sync_engine.SyncEngine.sync_logs",
        fake_sync_logs,
    )
    monkeypatch.setattr(
        "cf_aigw_analyzer.core.sync_engine.SyncEngine.sync_usage",
        fake_sync_usage,
    )
    result = runner.invoke(
        app,
        [
            "sync",
            "--account-id",
            "acct",
            "--gateway-id",
            "gw",
            "--with-usage",
            "--retry-failed",
        ],
    )

    assert result.exit_code == 0, result.output
    assert seen == [True]


def test_accounts_uses_mocked_http(project_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CF_API_TOKEN", "tok")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "success": True,
                "result_info": {"total_count": 1},
                "result": [{"id": "acct-1", "name": "demo", "type": "user"}],
            },
        )

    transport = httpx.MockTransport(handler)
    inner = httpx.AsyncClient(base_url="https://api.cloudflare.com/client/v4", transport=transport)

    original = CloudflareClient.__init__

    def patched(self, config, *, http=None):
        if http is None:
            http = HttpClient(
                base_url=config.base_url,
                headers={"Authorization": "Bearer tok"},
                retries=config.retries,
                client=inner,
            )
        original(self, config, http=http)

    monkeypatch.setattr(CloudflareClient, "__init__", patched)
    result = runner.invoke(app, ["accounts"])
    assert result.exit_code == 0
    assert "acct-1" in result.stdout
    assert "demo" in result.stdout
