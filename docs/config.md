# Configuration

`Settings` is a Pydantic v2 model defined in `cf_aigw_analyzer.config.settings`. It composes five nested sections: `cloudflare`, `storage`, `sync`, `control`, `logging`.

## Precedence

Lowest to highest:

1. Pydantic defaults.
2. `./config.yaml` (auto-discovered) or the file passed via `--config` / `CF_AIGW_CONFIG`.
3. `CF_AIGW_*`-prefixed environment variables (nested with `__`).
4. Bare upstream Cloudflare env vars (`CF_API_TOKEN`, `CF_EMAIL`, `CF_API_KEY`).

The bare names are kept for parity with Cloudflare's own conventions — users should not need to learn a project-specific prefix to plug in a token.

## YAML location

By default we look for `./config.yaml` (or `.yml`) relative to the project root resolved from the running entry point. Override with:

```bash
export CF_AIGW_CONFIG=/etc/cf-aigw/config.yaml
# or
python cli.py status --config /etc/cf-aigw/config.yaml
```

## Sections

### `cloudflare`

```yaml
cloudflare:
  api_token: ~        # CF_API_TOKEN (recommended)
  email: ~            # CF_EMAIL (legacy global-key auth)
  api_key: ~          # CF_API_KEY
  base_url: https://api.cloudflare.com/client/v4
  timeout: 30         # seconds; 1..600
  retries: 3          # 1..10
```

### `storage`

```yaml
storage:
  data_dir: ./local/data
  db_filename: cloudflare_ai_gateway.sqlite
  vacuum_on_close: false
  wal_checkpoint_interval: 1000
```

`storage.db_path` is derived as `data_dir / db_filename` and used by both the CLI and the FastAPI lifespan.

### `sync`

```yaml
sync:
  per_page: 50        # Cloudflare caps this at 50
  log_throttle_ms: 200
  usage_workers: 8    # asyncio Semaphore for /response fetches
  usage_batch_size: 50
  retry_failed: true
  incremental_overlap_minutes: 10
```

`usage_workers` is bounded `[1, 64]` so a misconfigured value cannot DoS Cloudflare.
`usage_batch_size` is bounded `[1, 500]` and caps the number of usage-target
coroutines materialized at once. Missing targets are processed before retryable
failed targets. `retry_failed` is the default policy used when a CLI/API request
does not explicitly disable retries.
`incremental_overlap_minutes` is used by `sync --incremental` and the
`/api/v1/sync/logs` `incremental=true` body flag. It rewinds the stored
`sync_state.last_seen_created_at` by a small window so repeated agent/cron runs
prefer overlap over missed late-arriving rows; SQLite primary keys absorb the
overlap. Incremental mode requires a complete, ascending result set and rejects
explicit limits or date windows.

### `control`

```yaml
control:
  host: 127.0.0.1
  # 默认固定端口。可用 --port / control.port / CF_AIGW_CONTROL__PORT 覆盖。
  port: 56000
  auth_token: ~       # set to any string to require Bearer auth on all /api/v1/*
  expose_docs: true
  cors_origins: []
  static_dir: web/dist
  default_account_id: ~
  default_gateway_id: ~
```

`default_account_id` lets CLI commands skip the `-a` flag once you only operate on one Cloudflare account.

### `logging`

```yaml
logging:
  level: INFO         # DEBUG / INFO / WARNING / ERROR
  format: rich        # rich | plain | json
```

The CLI uses the `rich` Console regardless of `format` — the field is wired up for future log routing.

## Templates

Generate a fresh template from the live schema:

```bash
python cli.py config template -o config-example.yaml
```

Validate the current configuration (without contacting Cloudflare):

```bash
python cli.py config validate
```

Inspect the effective configuration (secrets redacted):

```bash
python cli.py config show --format yaml
python cli.py config show --format json
```

The same redaction is used by `GET /api/v1/config`.

## Environment variable cheatsheet

| Variable                                | Equivalent YAML path             |
| --------------------------------------- | -------------------------------- |
| `CF_API_TOKEN`                          | `cloudflare.api_token`           |
| `CF_EMAIL`                              | `cloudflare.email`               |
| `CF_API_KEY`                            | `cloudflare.api_key`             |
| `CF_AIGW_CONFIG`                        | (path to YAML; not in YAML)      |
| `CF_AIGW_CONTROL__PORT`                 | `control.port`                   |
| `CF_AIGW_CONTROL__AUTH_TOKEN`           | `control.auth_token`             |
| `CF_AIGW_CONTROL__CORS_ORIGINS`         | `control.cors_origins` (JSON list) |
| `CF_AIGW_SYNC__USAGE_WORKERS`           | `sync.usage_workers`             |
| `CF_AIGW_SYNC__INCREMENTAL_OVERLAP_MINUTES` | `sync.incremental_overlap_minutes` |
| `CF_AIGW_STORAGE__DATA_DIR`             | `storage.data_dir`               |
| `CF_AIGW_LOGGING__LEVEL`                | `logging.level`                  |

Booleans accept `true`/`false`/`1`/`0`. Lists are parsed as JSON.
