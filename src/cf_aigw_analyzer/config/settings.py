"""Pydantic Settings model for the analyzer.

Precedence (lowest → highest):
    defaults < ./config.yaml < environment variables

Environment prefix: ``CF_AIGW_``, nested delimiter ``__``.
Example: ``CF_AIGW_CONTROL__PORT=9000``.

Cloudflare credentials accept both the project-prefixed form
(``CF_AIGW_CLOUDFLARE__API_TOKEN``) and the bare upstream form (``CF_API_TOKEN``).
The bare form is the recommended one in user docs.
"""

from __future__ import annotations

import random
from contextvars import ContextVar
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

_yaml_path_ctx: ContextVar[Path | None] = ContextVar("yaml_path_ctx", default=None)


class _Section(BaseModel):
    """Shared base for nested config sections."""

    model_config = ConfigDict(extra="forbid")


class CloudflareConfig(_Section):
    api_token: SecretStr | None = Field(
        default=None,
        description="Cloudflare API Token (preferred). Bare env CF_API_TOKEN also accepted by the loader.",
    )
    email: str | None = None
    api_key: SecretStr | None = None
    base_url: str = "https://api.cloudflare.com/client/v4"
    timeout: float = Field(default=30.0, ge=1.0, le=600.0)
    retries: int = Field(default=3, ge=1, le=10)


class StorageConfig(_Section):
    data_dir: Path = Field(default=Path("./local/data"))
    db_filename: str = "cloudflare_ai_gateway.sqlite"
    vacuum_on_close: bool = False
    wal_checkpoint_interval: int = Field(default=1000, ge=0)

    @property
    def db_path(self) -> Path:
        return self.data_dir / self.db_filename


CONTROL_PORT_MIN = 49152
CONTROL_PORT_MAX = 65535


def random_control_port() -> int:
    """Return a high-range port for the default control-plane bind."""

    return random.randint(CONTROL_PORT_MIN, CONTROL_PORT_MAX)


class SyncConfig(_Section):
    per_page: int = Field(default=50, ge=1, le=50)
    log_throttle_ms: int = Field(default=200, ge=0)
    usage_workers: int = Field(default=8, ge=1, le=64)
    usage_batch_size: int = Field(default=50, ge=1, le=500)
    retry_failed: bool = True
    incremental_overlap_minutes: int = Field(default=10, ge=0, le=1440)


class ControlConfig(_Section):
    host: str = "127.0.0.1"
    port: int | None = Field(default=None, ge=1, le=65535)
    auth_token: SecretStr | None = None
    expose_docs: bool = True
    cors_origins: list[str] = Field(default_factory=list)
    static_dir: Path = Field(default=Path("web/dist"))
    default_account_id: str | None = None
    default_gateway_id: str | None = None


class LoggingConfig(_Section):
    level: str = "INFO"
    format: str = Field(default="rich", pattern="^(rich|plain|json)$")

    @field_validator("level")
    @classmethod
    def _normalize_level(cls, value: str) -> str:
        return value.strip().upper()


class _YamlSettingsSource(PydanticBaseSettingsSource):
    """Reads a YAML file pointed to by :data:`_yaml_path_ctx`.

    Returned with lower precedence than env variables, but higher than defaults.
    """

    def __init__(self, settings_cls: type[BaseSettings]) -> None:
        super().__init__(settings_cls)
        self._data: dict[str, Any] = _read_yaml(_yaml_path_ctx.get())

    def get_field_value(self, field: Any, field_name: str) -> tuple[Any, str, bool]:
        value = self._data.get(field_name)
        return value, field_name, value is not None

    def __call__(self) -> dict[str, Any]:
        return {key: value for key, value in self._data.items() if value is not None}


def _read_yaml(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ValueError(f"{path} 顶层必须是 mapping，实际是 {type(raw).__name__}")
    return raw


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="CF_AIGW_",
        env_nested_delimiter="__",
        case_sensitive=False,
        extra="ignore",
    )

    cloudflare: CloudflareConfig = Field(default_factory=CloudflareConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    sync: SyncConfig = Field(default_factory=SyncConfig)
    control: ControlConfig = Field(default_factory=ControlConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        # Order: highest precedence first.
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            _YamlSettingsSource(settings_cls),
            file_secret_settings,
        )

    def has_credentials(self) -> bool:
        cf = self.cloudflare
        return bool(cf.api_token) or bool(cf.email and cf.api_key)
