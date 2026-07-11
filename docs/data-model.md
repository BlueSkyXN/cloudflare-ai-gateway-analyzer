# Data Model

The analyzer stores all observed accounts and gateways in a single SQLite database (default path: `./local/data/cloudflare_ai_gateway.sqlite`). Analytics now centers on one wide fact table, `log_events`, so common filters and metrics do not need 1:1 joins.

## Schema version

`PRAGMA user_version = 7`. The `migrations` table records applied version history with timestamps.

Version 5 is an intentional destructive reset for analyzer-owned tables. Existing v0.2-v0.4 SQLite data is not migrated into the new shape; re-sync from Cloudflare after upgrading.

Version 6 adds `input_tps` while preserving v5 data.

Version 7 adds expression indexes for the existing `julianday(created_at)` time-window filters.

## Relationship overview

- `log_events` is the single analytics-ready fact table. One Cloudflare AI Gateway log equals one row.
- `log_raw` stores sanitized `raw_json` only when raw inspection is needed; regular analytics should not scan it.
- `gateways` caches account-scoped gateway metadata so commands can resolve `--gateway-name` locally after discovery. Cloudflare may omit a separate gateway `name`; in that case the stable `gateway_id` is also stored as the display name.
- `sync_runs` is an audit log; `sync_state` stores incremental checkpoints; `sync_locks` prevents duplicate per-scope writers.
- `migrations` records schema application history.

`provider` is the channel dimension. The schema intentionally does not add `channel` as a duplicate name.

## Tables

### `migrations`

| Column        | Type    | Notes                            |
| ------------- | ------- | -------------------------------- |
| `version`     | INTEGER | Primary key.                     |
| `applied_at`  | TEXT    | ISO 8601 UTC.                    |

### `gateways`

Cached Cloudflare gateway metadata.

| Column          | Type    | Notes                                            |
| --------------- | ------- | ------------------------------------------------ |
| `account_id`    | TEXT    | Part of composite primary key.                   |
| `gateway_id`    | TEXT    | Part of composite primary key.                   |
| `name`          | TEXT    | Gateway display name; falls back to `gateway_id`. |
| `collect_logs`  | INTEGER | 0/1; null when Cloudflare did not return it.     |
| `raw_json`      | TEXT    | Sanitized gateway payload.                       |
| `fetched_at`    | TEXT    | ISO 8601 UTC.                                    |

### `log_events`

Primary key: `(account_id, gateway_id, log_id)`.

This table stores the commonly queried facts and dimensions directly on the log row.

| Column                   | Type    | Notes                                                                  |
| ------------------------ | ------- | ---------------------------------------------------------------------- |
| `account_id`             | TEXT    | Part of composite primary key.                                         |
| `gateway_id`             | TEXT    | Part of composite primary key.                                         |
| `log_id`                 | TEXT    | Part of composite primary key.                                         |
| `created_at`             | TEXT    | Cloudflare log timestamp.                                              |
| `provider`               | TEXT    | Channel dimension, e.g. `openai`, `anthropic`.                         |
| `model`                  | TEXT    | Provider model identifier.                                             |
| `model_type`             | TEXT    | `chat`, `image`, etc.                                                  |
| `success`                | INTEGER | 0/1/null.                                                              |
| `cached`                 | INTEGER | 0/1/null.                                                              |
| `status_code`            | INTEGER | Upstream HTTP status.                                                  |
| `cost_usd`               | REAL    | Cloudflare-reported USD cost when available.                           |
| `input_tokens`           | INTEGER | Usage input tokens; may be filled from metadata or usage response.      |
| `output_tokens`          | INTEGER | Usage output tokens.                                                   |
| `total_tokens`           | INTEGER | Provider total, or input + output fallback in analytics.                |
| `cached_tokens`          | INTEGER | Cache-read tokens across provider-specific usage formats.               |
| `reasoning_tokens`       | INTEGER | Reasoning/thinking token equivalent when available.                     |
| `cache_write_tokens`     | INTEGER | Cache-write tokens when available.                                     |
| `duration_ms`            | REAL    | Duration from log metadata.                                            |
| `latency_ms`             | REAL    | Time to first byte / latency from timings.                              |
| `total_ms`               | REAL    | Total request time from timings or duration fallback.                   |
| `generation_ms`          | REAL    | `total_ms - latency_ms`, clipped to 0.                                 |
| `input_tps`              | REAL    | Estimated input-token rate: `input_tokens / (latency_ms / 1000)`; not a direct provider prefill measurement. |
| `output_tps`             | REAL    | `output_tokens / (generation_ms / 1000)`.                              |
| `ms_per_output_token`    | REAL    | `generation_ms / output_tokens`.                                       |
| `visible_output_tokens`  | INTEGER | `output_tokens - reasoning_tokens`, floored at 0.                      |
| `visible_output_tps`     | REAL    | Visible-token TPS using `generation_ms`.                               |
| `usage_source`           | TEXT    | Where the usage object was parsed from.                                |
| `usage_fetch_status`     | TEXT    | `parsed` / `no_usage` / `failed` / null for missing.                    |
| `usage_http_status_code` | INTEGER | Last Cloudflare `/response` status.                                    |
| `usage_error_message`    | TEXT    | Optional human-readable error from the fetch attempt.                   |
| `usage_fetched_at`       | TEXT    | When `/response` was fetched or attempted.                              |
| `synced_at`              | TEXT    | When metadata was last synced.                                         |
| `updated_at`             | TEXT    | When the row was last updated.                                         |

Indexes:

- `idx_log_events_scope_time(account_id, gateway_id, created_at DESC)`
- `idx_log_events_provider_model(account_id, gateway_id, provider, model)`
- `idx_log_events_global_time(created_at DESC)`
- `idx_log_events_usage_status(account_id, gateway_id, usage_fetch_status)`

### `log_raw`

Sanitized JSON for the log. Separated from `log_events` so regular analytics avoid scanning large JSON blobs.

| Column        | Type | Notes                                |
| ------------- | ---- | ------------------------------------ |
| `account_id`  | TEXT | Part of composite primary key.       |
| `gateway_id`  | TEXT | Part of composite primary key.       |
| `log_id`      | TEXT | Part of composite primary key.       |
| `raw_json`    | TEXT | Sanitized JSON; no body fields.      |
| `updated_at`  | TEXT | When the snapshot was refreshed.     |

`ON DELETE CASCADE` keeps `log_raw` in sync with `log_events`.

### `sync_runs`

Audit log of every sync invocation (CLI or HTTP).

| Column              | Type    | Notes                                       |
| ------------------- | ------- | ------------------------------------------- |
| `run_id`            | INTEGER | Auto-increment primary key.                 |
| `account_id`        | TEXT    | Nullable for global ops.                    |
| `gateway_id`        | TEXT    | Nullable.                                   |
| `mode`              | TEXT    | `sync` / `sync-usage` / `seed`.             |
| `params_json`       | TEXT    | Stable JSON of filters + flags.             |
| `logs_count`        | INTEGER | Metadata rows processed.                    |
| `usage_fetched`     | INTEGER | `/response` attempts.                       |
| `usage_parsed`      | INTEGER | Usage parsed successfully.                  |
| `usage_no_usage`    | INTEGER | No usage object found.                      |
| `usage_failed`      | INTEGER | Fetch or parse failure.                     |
| `started_at`        | TEXT    | ISO 8601 UTC.                               |
| `finished_at`       | TEXT    | ISO 8601 UTC.                               |

Index: `idx_sync_runs_scope_time(account_id, gateway_id, started_at DESC)`.

### `sync_state`

Per-scope checkpoint for explicit incremental sync runs.

| Column                 | Type | Notes                                       |
| ---------------------- | ---- | ------------------------------------------- |
| `account_id`           | TEXT | Part of composite primary key.              |
| `gateway_id`           | TEXT | Part of composite primary key.              |
| `mode`                 | TEXT | `sync` or `sync-usage`.                     |
| `last_success_at`      | TEXT | Last successful run time.                   |
| `last_seen_created_at` | TEXT | Highest Cloudflare log `created_at` seen.   |
| `last_seen_log_id`     | TEXT | Tie-break marker for the highest timestamp. |
| `updated_at`           | TEXT | Last checkpoint write time.                 |

`sync --incremental` uses `last_seen_created_at` minus `sync.incremental_overlap_minutes` as the next `start_date`, forces `created_at ASC`, and requires an uncapped, unfiltered complete result set starting at page 1. The overlap is intentional; `(account_id, gateway_id, log_id)` primary keys absorb duplicates.

### `sync_locks`

Best-effort writer lock so two agents do not run the same sync mode for the same scope at the same time.

| Column        | Type | Notes                          |
| ------------- | ---- | ------------------------------ |
| `account_id`  | TEXT | Part of composite primary key. |
| `gateway_id`  | TEXT | Part of composite primary key. |
| `mode`        | TEXT | `sync` or `sync-usage`.        |
| `owner`       | TEXT | Process-local owner id.        |
| `acquired_at` | TEXT | ISO 8601 UTC.                  |
| `expires_at`  | TEXT | Stale locks are removed before acquisition. |

Index: `idx_sync_locks_expires(expires_at)`.

## PRAGMAs

```sql
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA busy_timeout = 5000;
PRAGMA temp_store = MEMORY;
PRAGMA mmap_size = 268435456; -- 256 MB memory mapping for read-heavy workloads
```

## Migration policy

- The current schema is v7.
- v5 drops old analyzer-owned tables (`logs`, `log_usage`, `log_metrics`, `logs_raw`) and recreates the simplified schema.
- No old SQLite data is migrated. Re-sync from Cloudflare after the reset.
- Future schema changes should add a migration handler in `migrations.MIGRATIONS`, bump `SCHEMA_VERSION`, and keep repository tests aligned.

## Backups & VACUUM

- WAL is enabled by default. Copying the database file while the analyzer is running requires `sqlite3 file.sqlite ".backup"` or stopping the process.
- `python cli.py vacuum` rebuilds the file when it grows after lots of upserts.
- Analyzer-owned tables can be dropped and rebuilt safely as long as `migrations.apply_migrations` recreates the expected schema and the operator re-syncs data.
