"""Tests for the configuration loader and template renderer."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from cf_aigw_analyzer.config import (
    Settings,
    load_settings,
    redact_settings,
    render_template,
    resolve_yaml_path,
)


def test_defaults_when_no_yaml(isolated_env, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    settings = load_settings(None)
    assert isinstance(settings, Settings)
    assert settings.cloudflare.api_token is None
    assert settings.control.host == "127.0.0.1"
    assert settings.control.port == 8765
    assert settings.sync.per_page == 50
    assert settings.has_credentials() is False


def test_yaml_overrides_defaults(isolated_env, tmp_yaml: Path):
    tmp_yaml.write_text(
        """
        control:
          port: 9999
          host: 0.0.0.0
        sync:
          usage_workers: 16
        """,
        encoding="utf-8",
    )
    settings = load_settings(tmp_yaml)
    assert settings.control.port == 9999
    assert settings.control.host == "0.0.0.0"
    assert settings.sync.usage_workers == 16


def test_env_overrides_yaml(isolated_env, tmp_yaml: Path, monkeypatch: pytest.MonkeyPatch):
    tmp_yaml.write_text(
        """
        control:
          port: 9999
        """,
        encoding="utf-8",
    )
    monkeypatch.setenv("CF_AIGW_CONTROL__PORT", "7777")
    settings = load_settings(tmp_yaml)
    assert settings.control.port == 7777  # env wins


def test_cf_api_token_env_is_recognised(isolated_env, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("CF_API_TOKEN", "tok-from-env")
    settings = load_settings(None)
    assert settings.cloudflare.api_token is not None
    assert settings.cloudflare.api_token.get_secret_value() == "tok-from-env"
    assert settings.has_credentials() is True


def test_global_api_key_pair_satisfies_credentials(isolated_env, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("CF_EMAIL", "you@example.com")
    monkeypatch.setenv("CF_API_KEY", "key-xxx")
    settings = load_settings(None)
    assert settings.has_credentials() is True
    assert settings.cloudflare.email == "you@example.com"


def test_redact_settings_masks_secrets(isolated_env, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("CF_API_TOKEN", "tok-secret")
    settings = load_settings(None)
    sanitized = redact_settings(settings)
    assert sanitized["cloudflare"]["api_token"] == "***"
    assert sanitized["cloudflare"]["email"] is None
    assert sanitized["storage"]["data_dir"] == "local/data"
    assert sanitized["control"]["auth_token"] is None


def test_render_template_round_trip_is_valid_yaml(isolated_env):
    import yaml

    rendered = render_template()
    data = yaml.safe_load(rendered)
    assert "cloudflare" in data
    assert "control" in data
    assert data["control"]["port"] == 8765
    # Public template must not leak Pydantic's secret mask.
    assert "**********" not in rendered


def test_resolve_yaml_path_picks_project_local(isolated_env, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    yaml_file = tmp_path / "config.yaml"
    yaml_file.write_text("control: {port: 1234}\n", encoding="utf-8")

    # Explicit path takes precedence regardless of working directory.
    resolved = resolve_yaml_path(yaml_file)
    assert resolved == yaml_file.resolve()


def test_resolve_yaml_path_returns_none_when_absent(isolated_env, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    # No config.yaml in tmp_path, and CF_AIGW_CONFIG unset.
    monkeypatch.setattr(
        "cf_aigw_analyzer.config.loader.PROJECT_ROOT",
        tmp_path,
        raising=True,
    )
    assert resolve_yaml_path(None) is None


def test_invalid_yaml_top_level_is_rejected(isolated_env, tmp_yaml: Path):
    tmp_yaml.write_text("- this\n- is\n- a list\n", encoding="utf-8")
    with pytest.raises(ValueError, match="顶层必须是 mapping"):
        load_settings(tmp_yaml)


def test_unknown_section_is_ignored(isolated_env, tmp_yaml: Path):
    # Extra unknown keys at the top level are tolerated (extra='ignore').
    tmp_yaml.write_text(
        "garbage_field: 1\ncontrol:\n  port: 4242\n",
        encoding="utf-8",
    )
    settings = load_settings(tmp_yaml)
    assert settings.control.port == 4242


def test_unknown_field_inside_section_is_rejected(isolated_env, tmp_yaml: Path):
    # Inside nested sections we still forbid extras to catch typos.
    tmp_yaml.write_text(
        "control:\n  not_a_real_field: yes\n",
        encoding="utf-8",
    )
    with pytest.raises(ValidationError):
        load_settings(tmp_yaml)
