# src/cf_aigw_analyzer/data navigation card

SQLite storage layer for schema v7, migrations, connection helpers, row models, and repositories.
Read this card before editing schema, migrations, indexes, repository writes, or readonly connection behavior.
Key files: `schema.py`, `migrations.py`, `db.py`, `models.py`, and `repository/`.

## Why this is high-risk

- `log_events` is the single analytics fact table consumed by CLI, API, analytics, and panel code.
- Migration mistakes can silently corrupt or discard local SQLite data.
- `log_raw.raw_json` may only contain sanitized Cloudflare log metadata, never request/response bodies.
- `gateways.raw_json` may contain sanitized gateway configuration snapshots, but secret-bearing fields must be redacted.
- Read/write boundaries matter: repositories write; analytics/control readonly paths must not mutate.

## Required before changes

- Check the current `SCHEMA_VERSION`, `MIGRATIONS`, and repository tests before changing DDL.
- If schema changes, update migration handlers, `PRAGMA user_version` expectations, row models, repositories, and `docs/data-model.md`.
- Preserve v7 `julianday(created_at)` expression-index support for time-window filters.
- Keep destructive reset behavior explicit in migrations and docs when touching legacy upgrade paths.

## Do not

- Do not reintroduce retired tables: `logs`, `log_usage`, `log_metrics`, or `logs_raw`.
- Do not add a duplicate `channel` column or alias; `provider` is the channel dimension.
- Do not persist unsanitized Cloudflare JSON. Use `sanitize_log_metadata` for log raw JSON and `sanitize_gateway_metadata` for gateway raw JSON.
- Do not put analytics aggregation SQL writes in this layer; analytics opens SQLite read-only.

## Validation

- `PYTHONPATH=src python3 -m pytest tests/unit/test_repository.py -v tests/unit/test_analytics.py`
- For sanitizer-touching repository changes, also run `PYTHONPATH=src python3 -m pytest tests/unit/test_sanitizer.py`.
