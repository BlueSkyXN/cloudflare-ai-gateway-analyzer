# Architecture

`cloudflare-ai-gateway-analyzer` is a Python 3.10+ tool that pulls Cloudflare AI Gateway log metadata into a single SQLite file, parses provider response usage, and exposes a FastAPI control plane plus an embedded React panel for analysis.

## Goals

- One SQLite file shared across all accounts and gateways.
- No persistence of request/response body content.
- FastAPI control plane + React panel as the primary UI; CLI for scripting and cron.
- SQL-pushed aggregates so large scopes do not load entire row sets into Python.
- Idempotent metadata + usage sync that can resume from any interruption.

## Non-goals

- Hosted multi-tenant service.
- Streaming/realtime ingestion. Sync is user-triggered.
- Mutating Cloudflare configuration. Read-only consumer.

## Module map

```
src/cf_aigw_analyzer/
├── cli/             CLI subcommands (Typer)
├── config/          Pydantic Settings + YAML loader + template
├── core/            HTTP client, Cloudflare API, parsers, sync engine
├── data/            SQLite schema, migrations, repositories
├── analytics/       Read-only SQL aggregations
├── control/         FastAPI app + routes + schemas + auth + tasks
├── models/          Shared enums
└── utils/           Console, time helpers, path resolution
```

The Python package mirrors the runtime layers exactly:

| Layer       | Touches network? | Writes DB? | Notes                                                    |
| ----------- | ---------------- | ---------- | -------------------------------------------------------- |
| `cli`       | via `core`       | via `data` | Typer entry, no business logic                           |
| `core`      | yes              | via `data` | Cloudflare client + sync engine                          |
| `data`      | no               | yes        | Repositories own all SQL writes                          |
| `analytics` | no               | read-only  | SQL-pushed aggregates, opens DB in `mode=ro`             |
| `control`   | via `core`       | via `data` | FastAPI, mounts panel static, schedules async sync tasks |

## Data flow

1. `accounts` + `gateways` discover Cloudflare resources and cache gateway metadata.
2. `sync` paginates `GET /accounts/.../logs`, sanitizes each row, and writes:
   - `logs` (metadata) + `logs_raw` (sanitized JSON) + `log_metrics` (derived fields).
3. `sync-usage` lists logs missing parsed usage, fetches `/response` concurrently, parses provider usage shapes, and writes `log_usage` plus refreshed TPS / visible-token metrics.
4. `query` and the analytics layer read joined views over `logs ⨝ log_usage ⨝ log_metrics`.
5. The dashboard renders the analytics results; events table and recent sync_runs come from the same SQLite.

## Synchronous vs async

- CLI commands and the FastAPI app share the same `SyncEngine`. The CLI uses `asyncio.run`, the FastAPI app schedules via `BackgroundTasks` and tracks status with an in-process `JobRegistry`.
- `HttpClient` uses `tenacity` for exponential backoff with jitter; 429 / 5xx are retried, 4xx (except 404) are returned as-is.

## Process model

- `cli.py {init,sync,sync-usage,query,status,vacuum,...}` — one-shot CLI.
- `cli.py serve` (or `serve.py`) — long-running FastAPI on `127.0.0.1:8765`. Uvicorn worker count is 1; the workload is IO-bound and serves a small number of analyst connections, so a single event loop is sufficient.
- React panel is built once with `npm run build`. The output `web/dist/` is mounted by `cf_aigw_analyzer.control.static`. Vite dev server can run separately during frontend development and proxies `/api` to the FastAPI process.

## Cloudflare API surface

We only call:

- `GET /accounts`
- `GET /accounts/{aid}/ai-gateway/gateways`
- `GET /accounts/{aid}/ai-gateway/gateways/{gid}/logs`
- `GET /accounts/{aid}/ai-gateway/gateways/{gid}/logs/{lid}/response`

`/response` is fetched solely to extract usage; the body itself is never persisted.

## Failure & retry model

| Situation                       | Mark as           | Re-fetched?                                                                                  |
| ------------------------------- | ----------------- | -------------------------------------------------------------------------------------------- |
| Cloudflare 200, valid usage     | `parsed`          | Yes when `logs.tokens_in/out` are still missing (backfill).                                  |
| Cloudflare 200, no usage object | `no_usage`        | No (unless `--refresh`).                                                                     |
| Cloudflare 404                  | `no_usage`        | No.                                                                                          |
| Cloudflare 4xx other / 5xx      | `failed`          | Yes when `retry_failed` is enabled (default).                                                |
| Network / TLS error             | `failed`          | Yes.                                                                                         |

## Boundaries the dashboard must not cross

- Panel must not import core or data layers; it goes through `/api/v1/*`.
- Analytics layer must not call Cloudflare; it operates on a read-only SQLite connection.
- Auth is loopback-only by default. Setting `control.auth_token` enables bearer-only access on every `/api/v1/*` route (GET included).
