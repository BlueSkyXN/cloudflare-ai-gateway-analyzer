# Operations

Day-to-day operating procedures for the analyzer.

## Installing

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Production deployments should pin `requirements.txt`. The dashboard extra is rolled into core dependencies now; there is no separate `[dashboard]` install group.

## Configuring credentials

Either set environment variables in your shell (recommended):

```bash
export CF_API_TOKEN=cf-token-...
```

Or copy `config-example.yaml` to `config.yaml` and edit the `cloudflare` section. **Do not commit `config.yaml`.**

Verify with `python cli.py config validate`.

## First-time setup

```bash
python cli.py init                          # create SQLite + write template if missing
python cli.py accounts                      # confirm credentials reach Cloudflare
python cli.py gateways -a <ACCOUNT_ID> --save   # cache gateway ids locally
```

`--save` writes the gateways into the `gateways` table so subsequent commands accept `--gateway-name` as either a cached display name or a gateway id. Cloudflare currently returns gateway ids as the stable label, so using the id is recommended.

## Metadata sync

Start small:

```bash
python cli.py sync -a <ACCOUNT_ID> --gateway-name <GW> --limit 100
```

Then run the full sync:

```bash
python cli.py sync -a <ACCOUNT_ID> --gateway-name <GW> --order-by created_at --direction asc
```

Sync is idempotent — re-running the same command upserts on `(account_id, gateway_id, log_id)`.
`--limit` must be a positive integer. Omit it for an uncapped metadata sync.

For repeated agent/cron runs after an initial backfill, prefer explicit
incremental mode:

```bash
python cli.py sync -a <ACCOUNT_ID> --gateway-name <GW> --incremental
```

`--incremental` reads `sync_state`, rewinds the previous `last_seen_created_at`
by `sync.incremental_overlap_minutes`, and lets the SQLite primary key absorb
the intentional overlap. Incremental mode forces `created_at ASC` so the
checkpoint only advances through a fully consumed result set. Do not combine it
with `--limit`, manual `--start-date` / `--end-date`, or an incompatible
`--order-by` / `--direction`. Result-narrowing filters such as `--model`,
`--provider`, `--success`, `--cached`, or token/cost/duration bounds are also
rejected because the checkpoint is shared by the whole account/gateway scope.

If an older database contains an invalid checkpoint, incremental sync fails before
contacting Cloudflare with an `invalid incremental checkpoint` error. Repair it by
running the uncapped non-incremental sync shown above. A valid `created_at` from that
run replaces the bad marker; invalid timestamps in individual log rows are stored as
metadata but do not advance the checkpoint.

## Usage sync

```bash
python cli.py sync-usage -a <ACCOUNT_ID> --gateway-name <GW> --missing-only --usage-workers 8
```

Recovery behaviour:

- `--missing-only` fetches only rows whose usage has never been attempted.
- Without `--missing-only`, never-fetched rows are processed before failed rows.
- `failed` rows follow `sync.retry_failed` by default; `--retry-failed` and
  `--no-retry-failed` override the policy for one run.
- `no_usage` rows are not refetched unless `--refresh` is used.
- Cloudflare 404 (`response body unavailable`) is recorded as `no_usage`, not `failed`.
- `--limit` must be positive when provided; `--usage-workers` is bounded to `1..64`.
- Candidate IDs are loaded in bounded `sync.usage_batch_size` batches rather than all at once.
- Missing and failed phases each retain newest-`created_at`-first ordering when a limit is used.
- A failure is attempted at most once per invocation. A later invocation can retry it even when both runs start within the same wall-clock second.

## Combined sync

```bash
python cli.py sync -a <ACCOUNT_ID> --gateway-name <GW> --with-usage --missing-only --usage-workers 8
```

Use `--usage-limit` when the follow-up usage backfill should be capped
separately from metadata sync. In the React Sync page, the single Limit field is
applied to both metadata and usage when `with usage` is enabled.

The sync engine also takes a per-scope writer lock, so a second agent trying to
run the same `(account_id, gateway_id, mode)` while one is active fails fast
instead of wasting duplicate Cloudflare requests.

## Querying

Default output is a 50-row table:

```bash
python cli.py query -a <ACCOUNT_ID> --gateway-name <GW> --limit 50
```

JSON / CSV exports use `--format` and `--output`:

```bash
mkdir -p local/exports
python cli.py query -a <ACCOUNT_ID> --gateway-name <GW> --format json -o local/exports/logs.json
```

By default exports exclude `raw_json`, `account_id`, and `gateway_id`. Add `--include-raw-json` and `--include-scope` for local inspection — never include those flags in pipelines that ship the file off-box.

## Status & sync history

```bash
python cli.py status                                    # global
python cli.py status -a <ACCOUNT_ID> --gateway-name <GW> # scoped
```

The same data is available via `GET /api/v1/status` and the dashboard's Sync page.

## Running the dashboard

```bash
python cli.py serve                # 启动后打印实际监听端口（默认 56000）
```

The FastAPI process:

- Binds 127.0.0.1 by default. To listen on other interfaces, set `control.host` *and* `control.auth_token`.
- Serves the built panel from `web/dist` (or shows a placeholder if absent).
- Exposes `/docs` and `/redoc` unless `control.expose_docs` is false.

For panel development:

```bash
cd web
npm run dev      # 127.0.0.1:5173 — proxies /api to 56000 (可通过 VITE_CONTROL_PORT 覆盖)
```

## Triggering sync from the panel

The Sync page (`/sync`) calls `POST /api/v1/sync/logs` and `POST /api/v1/sync/usage`. Jobs run inside the FastAPI worker (no external queue). The page polls `/api/v1/sync/jobs` every 3 seconds while a job is in flight. The page normalizes Limit to a positive integer so `0` never turns into an accidental full sync.

## Vacuum

After heavy churn:

```bash
python cli.py vacuum
```

This rewrites the SQLite file and reclaims free pages. Run during maintenance windows — it briefly locks the database.

## Docker

```bash
cp .env.example .env       # populate credentials
docker compose up -d
docker compose logs -f
docker compose exec cf-aigw python cli.py status
```

The compose file binds to loopback by default. The health probe hits
`/api/v1/health` every 30 seconds. If `CF_AIGW_CONTROL__AUTH_TOKEN` is set, the
probe sends the matching `Authorization: Bearer <token>` header; `/api/v1/health`
is not exempt from auth.

The default compose file reads credentials and simple overrides from `.env` and
persists SQLite under `./local`. If you prefer `config.yaml`, mount it with a
local compose override, for example:

```yaml
services:
  cf-aigw:
    volumes:
      - ./local:/app/local
      - ./config.yaml:/app/config.yaml:ro
```

To rebuild after pulling new code:

```bash
docker compose build
docker compose up -d
```

## Backups

```bash
sqlite3 local/data/cloudflare_ai_gateway.sqlite ".backup '/tmp/snapshot.sqlite'"
```

Treat the snapshot as private — it contains the same operational metadata as the live database.
