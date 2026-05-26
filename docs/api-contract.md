# API Contract

The FastAPI control plane mounts everything under `/api/v1`. OpenAPI is generated automatically and exported by:

```bash
python3 scripts/generate_openapi.py --output local/openapi.json
```

## Authentication

| `control.auth_token` value | Behaviour                                                                                |
| -------------------------- | ---------------------------------------------------------------------------------------- |
| empty / unset (default)    | No auth required. Combined with `127.0.0.1` host bind this is safe for local use.        |
| any non-empty string       | **All** `/api/v1/*` routes require `Authorization: Bearer <token>`, including GETs.      |

There is no per-route exemption. Once the token is set, even `/docs` and `/openapi.json` are gated. This matches our threat model: cross-site requests can read state through GET endpoints, so we apply uniform auth.

## Routes

### Meta

| Method | Path             | Description                                                             |
| ------ | ---------------- | ----------------------------------------------------------------------- |
| GET    | `/api/v1/health` | Version, DB path, DB size in bytes, whether credentials are configured. |

### Scopes

| Method | Path                                   | Description                                                                  |
| ------ | -------------------------------------- | ---------------------------------------------------------------------------- |
| GET    | `/api/v1/scopes`                       | All `(account_id, gateway_id)` pairs with cached counts and first/last seen. |
| GET    | `/api/v1/scopes/{account_id}/gateways` | Gateway metadata cached locally for a specific account.                      |

### Analytics

The current analytics contract is a single route:

| Method | Path                 | Returns                                                                                     |
| ------ | -------------------- | ------------------------------------------------------------------------------------------- |
| GET    | `/api/v1/analytics`  | `summary`, `timeseries`, `by_provider`, `by_model`, `events`, and `filter_options`.         |

Query parameters:

```text
account_id, gateway_id, start_date, end_date, provider, model, success,
timeseries_bucket_hours, limit
```

- `provider` is the channel dimension displayed as “渠道” in the UI.
- `timeseries_bucket_hours` controls the `timeseries` aggregation step and must be one of `1`, `4`, `8`, `12`, `24`
  (hours). It defaults to `1`.
- `limit` controls the number of recent `events` returned. It defaults to 500 and is capped at 5000.
- Dates accept `YYYY-MM-DD`, `YYYY-MM-DDTHH:MM:SS[Z]`, or `YYYY/MM/DD`.
- Strings are passed as-is; booleans accept `true` / `false`.

Response sections:

| Section          | Description                                                                                   |
| ---------------- | --------------------------------------------------------------------------------------------- |
| `summary`        | Request count, success rate, model/provider count, token totals, cache ratio, latency percentiles, average input/output TPS, usage status counts. |
| `timeseries`     | request/token/latency/input and output TPS series aggregated by `timeseries_bucket_hours` (1/4/8/12/24h). |
| `by_provider`    | Provider-level breakdown.                                                                      |
| `by_model`       | Model-level breakdown with provider list and p95 total latency.                                |
| `events`         | Recent `log_events` rows with usage, timing, status, and TPS fields.                           |
| `filter_options` | Provider and model option lists for dashboard filters.                                         |

Removed legacy frontend dependencies:

- `/api/v1/analytics/summary`
- `/api/v1/analytics/timeseries`
- `/api/v1/analytics/models`
- `/api/v1/analytics/context-buckets`
- `/api/v1/analytics/insights`
- `/api/v1/events`

### Status & sync runs

| Method | Path                         | Notes                                          |
| ------ | ---------------------------- | ---------------------------------------------- |
| GET    | `/api/v1/status`             | Same payload as `cf-aigw-analyzer status` CLI. |
| GET    | `/api/v1/sync/runs`          | Recent rows from `sync_runs` table.            |
| GET    | `/api/v1/sync/runs/{run_id}` | Single sync run by id. 404 when missing.       |

### Sync triggers (async jobs)

| Method | Path                         | Body / params                                                       |
| ------ | ---------------------------- | ------------------------------------------------------------------- |
| POST   | `/api/v1/sync/logs`          | `SyncTriggerRequest`. Returns `{job_id, status: "running", mode}`. |
| POST   | `/api/v1/sync/usage`         | `SyncUsageTriggerRequest`. Returns `{job_id, status, mode}`.        |
| GET    | `/api/v1/sync/jobs`          | All in-process jobs with status.                                    |
| GET    | `/api/v1/sync/jobs/{job_id}` | Single job status (poll until `status="done"` or `"failed"`).     |

Jobs run inside the FastAPI worker process via `asyncio.create_task`. There is no external broker — this matches the analyzer's single-process design. The registry retains the most recent 100 jobs and drops finished ones beyond that.

Sync trigger numeric constraints are part of the public contract:

- `/sync/logs`: `limit >= 1`, `usage_limit >= 1`, `usage_workers` in `1..64`.
- `/sync/usage`: `limit >= 1`, `workers` in `1..64`.
- Omitted limits mean "no explicit cap"; `0` and negative values are rejected with `422`.

`/sync/logs` also accepts `incremental: true`. In that mode the server reads `sync_state` for the same `(account_id, gateway_id, "sync")` scope, rewinds `last_seen_created_at` by `sync.incremental_overlap_minutes`, and sends that as the Cloudflare `start_date`. Do not combine `incremental=true` with explicit `start_date` / `end_date` filters; the request is treated as a job failure.

When `/sync/logs` is called with `with_usage=true`, clients should pass `usage_limit` when they intend the follow-up usage backfill to be capped too. The bundled React panel uses the same positive Limit value for both metadata sync and usage sync.

### Config

| Method | Path             | Notes                                                                   |
| ------ | ---------------- | ----------------------------------------------------------------------- |
| GET    | `/api/v1/config` | Redacted settings snapshot. Secrets are returned as `"***"`. Read-only. |

There is **no** `PUT /config`. Mutating credentials over HTTP is out of scope for this tool — edit `config.yaml` or environment variables instead.

## OpenAPI generation

`fastapi.openapi.utils.get_openapi` is called via `app.openapi()`. The generator script writes a stable JSON form suitable for diffing in CI. The frontend can use [openapi-typescript](https://github.com/drwpow/openapi-typescript) to derive types if hand-written types in `web/src/api/types.ts` are insufficient.
