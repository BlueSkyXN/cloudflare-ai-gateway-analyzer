# Data Model

The analyzer stores all observed scopes in a single SQLite database (default path: `./local/data/cloudflare_ai_gateway.sqlite`). Tables share `(account_id, gateway_id, log_id)` so every read is explicitly scoped.

## Schema version

`PRAGMA user_version = 3`. The `migrations` table records the applied version history with timestamps. Future schema changes should add an entry to `cf_aigw_analyzer.data.migrations.MIGRATIONS` and bump `SCHEMA_VERSION`.

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
| `name`          | TEXT    | Gateway display name.                            |
| `collect_logs`  | INTEGER | 0/1; null when Cloudflare did not return it.     |
| `raw_json`      | TEXT    | Sanitized gateway payload.                       |
| `fetched_at`    | TEXT    | ISO 8601 UTC.                                    |

### `logs`

Sanitized log metadata. **Does not store request/response body content.**

Primary key: `(account_id, gateway_id, log_id)`.

| Column         | Type    | Notes                                            |
| -------------- | ------- | ------------------------------------------------ |
| `created_at`   | TEXT    | ISO 8601 from Cloudflare.                        |
| `provider`     | TEXT    | e.g. `openai`, `anthropic`.                      |
| `model`        | TEXT    | Provider model identifier.                       |
| `model_type`   | TEXT    | `chat`, `image`, etc.                            |
| `success`      | INTEGER | 0/1/null.                                        |
| `cached`       | INTEGER | 0/1/null.                                        |
| `status_code`  | INTEGER | Upstream HTTP status.                            |
| `cost_usd`     | REAL    | Cloudflare-reported USD cost.                    |
| `tokens_in`    | INTEGER | From log metadata; back-filled from usage.       |
| `tokens_out`   | INTEGER | Same.                                            |
| `synced_at`    | TEXT    | When the row was last written.                   |

Indexes:

- `idx_logs_scope_time(account_id, gateway_id, created_at DESC)`
- `idx_logs_provider_model(account_id, gateway_id, provider, model)`
- `idx_logs_global_time(created_at DESC)` — new in v0.3, accelerates cross-scope analytics

### `logs_raw`

Sanitized JSON for the log. Separated from `logs` so the hot metadata table stays narrow.

| Column        | Type | Notes                                |
| ------------- | ---- | ------------------------------------ |
| `account_id`  | TEXT | Part of composite primary key.       |
| `gateway_id`  | TEXT | Part of composite primary key.       |
| `log_id`      | TEXT | Part of composite primary key.       |
| `raw_json`    | TEXT | Sanitized JSON (no body fields).     |
| `updated_at`  | TEXT | When the snapshot was refreshed.     |

`ON DELETE CASCADE` keeps `logs_raw` in sync with `logs`.

### `log_usage`

Parsed token usage per log. 1:1 with `logs`.

| Column                | Type    | Notes                                                                                                                             |
| --------------------- | ------- | --------------------------------------------------------------------------------------------------------------------------------- |
| `input_tokens`        | INTEGER | Best-effort across providers.                                                                                                     |
| `output_tokens`       | INTEGER |                                                                                                                                   |
| `total_tokens`        | INTEGER |                                                                                                                                   |
| `cached_tokens`       | INTEGER | OpenAI `cached_tokens`, Anthropic `cache_read_input_tokens`, Gemini `cachedContentTokenCount`.                                    |
| `reasoning_tokens`    | INTEGER | OpenAI / Anthropic / Gemini equivalents.                                                                                          |
| `cache_write_tokens`  | INTEGER | Anthropic `cache_creation_input_tokens`.                                                                                          |
| `source`              | TEXT    | Where in the payload the usage object came from (e.g. `usage`, `result.usage`, `streamed_data.usage`).                           |
| `fetch_status`        | TEXT    | `parsed` / `no_usage` / `failed`. Enforced via `CHECK` constraint.                                                                |
| `http_status_code`    | INTEGER | Last Cloudflare response status.                                                                                                  |
| `error_message`       | TEXT    | Optional human-readable error from the fetch attempt.                                                                             |

Index: `idx_usage_scope_status(account_id, gateway_id, fetch_status)`.

### `log_metrics`

Per-log derived metrics. Recomputed on log upsert and on usage upsert (for TPS / visible-token columns).

| Column                  | Type | Notes                                                  |
| ----------------------- | ---- | ------------------------------------------------------ |
| `duration_ms`           | REAL | From log `duration` field.                             |
| `latency_ms`            | REAL | From timings.latency.                                  |
| `total_ms`              | REAL | From timings.total or duration fallback.               |
| `generation_ms`         | REAL | `total_ms - latency_ms` clipped to 0.                  |
| `output_tps`            | REAL | `output_tokens / (generation_ms / 1000)`.              |
| `ms_per_output_token`   | REAL | `generation_ms / output_tokens`.                       |
| `visible_output_tokens` | INTEGER | `output_tokens - reasoning_tokens` (floor 0).        |
| `visible_output_tps`    | REAL | Visible-token TPS using `generation_ms`.               |

Index: `idx_metrics_scope(account_id, gateway_id)`.

### `sync_runs`

Audit log of every sync invocation (CLI or HTTP).

| Column              | Type    | Notes                                       |
| ------------------- | ------- | ------------------------------------------- |
| `run_id`            | INTEGER | Auto-increment primary key.                 |
| `account_id`        | TEXT    | Nullable for global ops.                    |
| `gateway_id`        | TEXT    | Nullable.                                   |
| `mode`              | TEXT    | `sync` / `sync-usage` / `seed`.             |
| `params_json`       | TEXT    | Stable JSON of filters + flags.             |
| `logs_count`        | INTEGER |                                             |
| `usage_fetched`     | INTEGER |                                             |
| `usage_parsed`      | INTEGER |                                             |
| `usage_no_usage`    | INTEGER |                                             |
| `usage_failed`      | INTEGER |                                             |
| `started_at`        | TEXT    | ISO 8601 UTC.                               |
| `finished_at`       | TEXT    | ISO 8601 UTC.                               |

Index: `idx_sync_runs_scope_time(account_id, gateway_id, started_at DESC)`.

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

- The current schema is v3. v0.2 schema (v2) has no upgrade path; you must re-sync from Cloudflare.
- New columns: add a migration handler in `migrations.MIGRATIONS` keyed by the new `SCHEMA_VERSION`. Handlers must be idempotent.
- Index changes: emit `CREATE INDEX IF NOT EXISTS` in the migration. Drop with care; pre-existing index names are owned by older versions.

## Backups & VACUUM

- WAL is enabled by default. Copying the database file while the analyzer is running requires `sqlite3 file.sqlite ".backup"` or stopping the process.
- `python cli.py vacuum` rebuilds the file when it grows after lots of upserts.
- All tables can be dropped and rebuilt safely: the analyzer never depends on schema state beyond what `migrations.apply_migrations` ensures.
