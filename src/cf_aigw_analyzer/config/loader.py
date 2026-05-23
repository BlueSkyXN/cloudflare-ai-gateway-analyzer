"""Config loader: resolve yaml path + build :class:`Settings`."""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import SecretStr

from cf_aigw_analyzer.config.settings import Settings, _yaml_path_ctx
from cf_aigw_analyzer.utils.paths import PROJECT_ROOT

DEFAULT_YAML_NAMES = ("config.yaml", "config.yml")

# Bare environment variable names that map onto nested Settings fields.
# These are kept for parity with the official Cloudflare conventions
# (CF_API_TOKEN etc.) so users don't have to learn a CF_AIGW_-prefixed alias.
# The third tuple element indicates whether the target field is a SecretStr.
_BARE_ENV_MAP: tuple[tuple[str, str, str, bool], ...] = (
    ("cloudflare", "api_token", "CF_API_TOKEN", True),
    ("cloudflare", "email", "CF_EMAIL", False),
    ("cloudflare", "api_key", "CF_API_KEY", True),
)


def resolve_yaml_path(explicit: str | os.PathLike[str] | None = None) -> Path | None:
    """Return the path to the active YAML config, or ``None`` if absent.

    Resolution order:

    1. ``explicit`` parameter (highest).
    2. ``CF_AIGW_CONFIG`` environment variable.
    3. ``./config.yaml`` or ``./config.yml`` relative to project root.
    """

    candidate: Path | None = None
    if explicit:
        candidate = Path(explicit).expanduser()
    elif env_path := os.getenv("CF_AIGW_CONFIG"):
        candidate = Path(env_path).expanduser()
    else:
        for name in DEFAULT_YAML_NAMES:
            project_local = PROJECT_ROOT / name
            if project_local.exists():
                candidate = project_local
                break

    if candidate is None:
        return None
    return candidate.resolve()


def load_settings(yaml_path: str | os.PathLike[str] | None = None) -> Settings:
    """Build a :class:`Settings` instance.

    Precedence (lowest → highest):

    * Pydantic defaults
    * ``./config.yaml`` (auto-discovered or ``yaml_path``)
    * ``CF_AIGW_*`` prefixed environment variables (nested delimiter ``__``)
    * Bare Cloudflare env aliases: ``CF_API_TOKEN``, ``CF_EMAIL``, ``CF_API_KEY``
    """

    resolved = resolve_yaml_path(yaml_path)
    token = _yaml_path_ctx.set(resolved)
    try:
        settings = Settings()
    finally:
        _yaml_path_ctx.reset(token)

    return _apply_bare_env_aliases(settings)


def _apply_bare_env_aliases(settings: Settings) -> Settings:
    """Overlay bare upstream env vars (e.g. ``CF_API_TOKEN``) on top of settings."""

    overrides: dict[str, dict[str, object]] = {}
    for section, field_name, env_name, is_secret in _BARE_ENV_MAP:
        value = os.getenv(env_name)
        if not value:
            continue
        wrapped: object = SecretStr(value) if is_secret else value
        overrides.setdefault(section, {})[field_name] = wrapped

    if not overrides:
        return settings

    updates: dict[str, object] = {}
    for section, field_updates in overrides.items():
        current_section = getattr(settings, section)
        updates[section] = current_section.model_copy(update=field_updates)
    return settings.model_copy(update=updates)
