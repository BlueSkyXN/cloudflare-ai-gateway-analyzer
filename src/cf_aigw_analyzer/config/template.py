"""Render a public ``config-example.yaml`` from the live Settings schema.

This avoids documentation drift: the example template is generated from the
Pydantic model defaults rather than hand-maintained.
"""

from __future__ import annotations

import io
from typing import Any

import yaml

from cf_aigw_analyzer.config.settings import Settings

_SECTION_COMMENTS: dict[str, str] = {
    "cloudflare": (
        "Cloudflare credentials.\n"
        "Prefer environment variables for secrets: CF_API_TOKEN (recommended),\n"
        "or CF_EMAIL + CF_API_KEY for the legacy Global API Key path."
    ),
    "storage": (
        "Local SQLite storage location.\n"
        "Defaults to ./local/data which is gitignored. Use an absolute path\n"
        "if you want the database outside the repository."
    ),
    "sync": (
        "Cloudflare API pagination + parallel response-usage fetch knobs.\n"
        "Cloudflare caps per_page at 50. Incremental sync uses sync_state\n"
        "with a small overlap window so repeated agent runs are idempotent."
    ),
    "control": (
        "FastAPI control plane and panel hosting.\n"
        "Set auth_token to require Bearer auth on every /api/v1/* route\n"
        "(including read-only GETs). Empty token + loopback host = open."
    ),
    "logging": ("Log level and console format.\nformat: rich | plain | json"),
}


def _comment_block(text: str) -> list[str]:
    return [f"# {line}" if line else "#" for line in text.splitlines()]


def render_template() -> str:
    """Return the YAML-formatted public template text."""

    sample = Settings().model_dump(mode="json")
    sample = _scrub_secrets(sample)

    buffer = io.StringIO()
    buffer.write("# Cloudflare AI Gateway Analyzer — example configuration.\n")
    buffer.write("# Copy to ./config.yaml and fill in values.\n")
    buffer.write("# Environment variables (prefix CF_AIGW_) override this file.\n\n")

    for section_name, section_value in sample.items():
        for line in _comment_block(_SECTION_COMMENTS.get(section_name, "")):
            buffer.write(line + "\n")
        dumped = yaml.safe_dump(
            {section_name: section_value},
            sort_keys=False,
            allow_unicode=True,
            default_flow_style=False,
        )
        buffer.write(dumped)
        buffer.write("\n")
    return buffer.getvalue().rstrip() + "\n"


def _scrub_secrets(value: Any) -> Any:
    """Replace Pydantic's default secret mask (``"**********"``) with ``None``.

    Defaults have no secret content set, so this only normalises the textual
    placeholder Pydantic emits for ``SecretStr`` when dumping to JSON mode.
    """

    if isinstance(value, dict):
        return {key: _scrub_secrets(child) for key, child in value.items()}
    if isinstance(value, list):
        return [_scrub_secrets(item) for item in value]
    if isinstance(value, str) and value == "**********":
        return None
    return value
