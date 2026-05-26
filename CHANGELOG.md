# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html) once a `1.0.0` is released.

## [Unreleased]

### Changed

- Simplified SQLite schema to version 6 with `log_events` as the single analytics fact table and `log_raw` as the sanitized raw JSON side table.
- Added `input_tps` as a separate input-side throughput metric while keeping `output_tps` for generation throughput.
- Replaced the split frontend analytics contract with one `GET /api/v1/analytics` response containing `summary`, `timeseries`, `by_provider`, `by_model`, `events`, and `filter_options`.
- Updated CLI `query` and `status` outputs to read wide-table usage, timing, TPS, and usage status fields from `log_events`.
- Frontend analytics pages now share the unified analytics hook and display `provider` as “渠道”.

### Removed

- Retired analyzer-owned tables `logs`, `log_usage`, `log_metrics`, and `logs_raw`.
- Removed old split analytics endpoints from the frontend dependency surface: `/analytics/summary`, `/analytics/timeseries`, `/analytics/models`, `/analytics/context-buckets`, `/analytics/insights`, and `/events`.

### Migration

- Schema v5 performs a destructive reset of old analyzer tables. Existing local SQLite analytics data is not migrated; re-sync from Cloudflare.
- Schema v6 preserves v5 rows and backfills `input_tps` from `input_tokens` and `latency_ms`.

## [0.3.0a0] — 2026-05-23

Complete rewrite. The CLI / SQLite metadata model is preserved at a high level, but everything else has been reorganized.

### Added

- FastAPI control plane at `/api/v1/*` replacing the Streamlit subprocess.
- React 18 + Vite + TypeScript + ECharts + Tailwind panel under `web/`. Default dark theme, dashboard-oriented information density.
- `config.yaml` configuration with Pydantic v2 + nested env-var override (`CF_AIGW_*`).
- SQLite schema version 4:
  - Split `logs.raw_json` into a separate `logs_raw` table to keep the metadata hot path narrow.
  - Added `migrations` table to record applied schema versions with timestamps.
  - New indexes: `idx_logs_global_time`, `idx_sync_runs_scope_time`.
  - `log_usage.fetch_status` now has a `CHECK` constraint.
  - Added `sync_state` checkpoints and `sync_locks` for resumable, duplicate-safe sync runs.
- Async sync engine (`asyncio` + `Semaphore`) replacing the threadpool implementation.
- httpx + tenacity-based HTTP client with shared retry policy.
- Multi-stage Dockerfile + `docker-compose.yml` + `entrypoint.sh` for containerised deployment.
- Hatch build hook ready to embed the React `web/dist` into wheels (via `pyproject.toml`).
- Scripts: `seed_sqlite.py`, `smoke_local.py`, `generate_openapi.py`, `check_api.py`.
- Unit + integration tests (pytest + pytest-asyncio + httpx MockTransport).

### Changed

- Package layout: `src/cf_aigw_analyzer/` now contains explicit submodules (`cli/`, `config/`, `core/`, `data/`, `analytics/`, `control/`, `models/`, `utils/`).
- CLI moved to Typer with subcommands split per file (`cli/init_cmd.py`, `cli/sync_cmd.py`, ...).
- Two entry-point scripts at the repository root (`cli.py`, `main.py`, `serve.py`) for development + frozen builds.
- Analytics aggregations are pushed down to SQLite, avoiding Python-side full scans.
- Authentication: when `control.auth_token` is set, **all** `/api/v1/*` routes (including read-only GETs and `/docs`) require Bearer auth.
- Token usage parser now returns a `UsageFields` Pydantic model and handles Cloudflare-wrapped JSON strings explicitly.

### Removed

- Streamlit dashboard and the `dashboard` extra.
- Standard-library urllib HTTP client (replaced by httpx).
- Single-file `database.py` (replaced by `data/db.py` + `data/repository/*`).
- v0.2 schema (`raw_json` column inside `logs`). No automatic data migration — re-sync from Cloudflare.

### Compatibility

- Python 3.10+, identical to v0.2.
- CLI commands `sync`, `sync-usage`, `query`, `status`, `vacuum`, `accounts`, `gateways`, `init` are preserved with the same flags. The `dashboard` command has been replaced by `serve`.
- The historical v0.2 source remains available at `legacy/v0.2/` for reference. It is not maintained.

## [0.2.0] — see `legacy/v0.2/`

Legacy single-package implementation with Streamlit dashboard. Documented in `legacy/v0.2/README.md`.
