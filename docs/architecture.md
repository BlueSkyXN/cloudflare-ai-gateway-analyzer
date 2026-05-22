# Architecture

`cloudflare-ai-gateway-analyzer` is a Python CLI for collecting Cloudflare AI Gateway log metadata into SQLite and deriving local usage analytics.

## Goals

- Keep deployment simple: Python CLI, one SQLite database, and an optional local-only dashboard.
- Store multiple accounts and gateways in one database.
- Preserve log metadata needed for analysis.
- Avoid storing request and response body content.
- Extract token usage from Cloudflare log response payloads when available.
- Keep calculated metrics in 1:1 side tables so raw metadata and derived data remain separate.
- Provide local analytics for model comparison, time-series throughput, latency, token usage, cache ratio, and context-length effects.

## Non-goals

- No XLSX export in the current version.
- No hosted web UI. The dashboard is local-only and binds to loopback by default.
- No scheduler daemon in the current version.
- No automatic publishing, deployment, or upload.
- No license grant until a license is explicitly chosen and added.

## Main Components

- `cf_aigw_analyzer.cli`: CLI command surface.
- `cf_aigw_analyzer.cloudflare`: Cloudflare API client with retries and TLS verification.
- `cf_aigw_analyzer.database`: SQLite schema and repository methods.
- `cf_aigw_analyzer.filters`: API filter mapping and date normalization.
- `cf_aigw_analyzer.sync`: metadata and usage sync orchestration.
- `cf_aigw_analyzer.usage`: provider response usage parser.
- `cf_aigw_analyzer.analytics`: read-only SQLite aggregation for summaries, trends, model comparisons, context buckets, events, and insights.
- `cf_aigw_analyzer.dashboard`: Streamlit launcher for the local dashboard.
- `cf_aigw_analyzer.dashboard_app`: Streamlit UI for local analytics.
- `cf_aigw_analyzer.output`: table, JSON, and CSV output helpers.

## Data Flow

1. `accounts` and `gateways` discover Cloudflare resources.
2. `sync` reads AI Gateway log metadata page by page.
3. `logs` stores sanitized metadata keyed by `(account_id, gateway_id, log_id)`.
4. `log_metrics` stores calculated per-log metrics in a 1:1 row.
5. `sync-usage` requests `/response` for each target log and parses usage fields.
6. `log_usage` stores parsed usage or the non-parsed status in a 1:1 row.
7. `query` reads from local SQLite only and excludes private output fields by default.
8. `dashboard` starts a local Streamlit process that reads SQLite through `cf_aigw_analyzer.analytics`.

## API Endpoints

The CLI currently uses:

- `GET /accounts`
- `GET /accounts/{account_id}/ai-gateway/gateways`
- `GET /accounts/{account_id}/ai-gateway/gateways/{gateway_id}/logs`
- `GET /accounts/{account_id}/ai-gateway/gateways/{gateway_id}/logs/{log_id}/response`

`/response` is used only to parse usage fields. Response body content is not persisted.

The dashboard does not call Cloudflare. It only reads the local SQLite file.
