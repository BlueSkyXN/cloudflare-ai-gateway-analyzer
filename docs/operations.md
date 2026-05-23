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
python cli.py gateways -a <ACCOUNT_ID> --save   # cache gateway names locally
```

`--save` writes the gateways into the `gateways` table so subsequent commands accept `--gateway-name` instead of UUIDs.

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

## Usage sync

```bash
python cli.py sync-usage -a <ACCOUNT_ID> --gateway-name <GW> --missing-only --usage-workers 8
```

Recovery behaviour:

- Missing rows are fetched.
- `failed` rows are retried by default (`--no-retry-failed` to skip).
- `no_usage` rows are not refetched in `--missing-only` mode.
- Cloudflare 404 (`response body unavailable`) is recorded as `no_usage`, not `failed`.

## Combined sync

```bash
python cli.py sync -a <ACCOUNT_ID> --gateway-name <GW> --with-usage --missing-only --usage-workers 8
```

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
python cli.py serve                # http://127.0.0.1:8765
```

The FastAPI process:

- Binds 127.0.0.1 by default. To listen on other interfaces, set `control.host` *and* `control.auth_token`.
- Serves the built panel from `web/dist` (or shows a placeholder if absent).
- Exposes `/docs` and `/redoc` unless `control.expose_docs` is false.

For panel development:

```bash
cd web
npm ci
npm run dev      # 127.0.0.1:5173 — proxies /api to 8765
```

## Triggering sync from the panel

The Sync page (`/sync`) calls `POST /api/v1/sync/logs` and `POST /api/v1/sync/usage`. Jobs run inside the FastAPI worker (no external queue). The page polls `/api/v1/sync/jobs` every 3 seconds while a job is in flight.

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

The compose file binds to loopback by default. The health probe hits `/api/v1/health` every 30 seconds.

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
