# Operations

This guide describes safe local sync workflows.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

Install dashboard dependencies only when needed:

```bash
pip install -e ".[dashboard]"
```

Use environment variables for credentials:

```bash
export CF_API_TOKEN="your-token"
```

or:

```bash
export CF_EMAIL="you@example.com"
export CF_API_KEY="your-global-api-key"
```

Do not write real credentials into source files, docs, commits, screenshots, or logs intended for sharing.

## Discover Accounts and Gateways

```bash
cf-aigw-analyzer accounts
cf-aigw-analyzer gateways -a <ACCOUNT_ID>
cf-aigw-analyzer gateways -a <ACCOUNT_ID> --save
```

Use `--save` to store gateway metadata in the shared SQLite database. Once stored, commands that accept `--gateway-name` can resolve gateway names from local metadata or from the Cloudflare API when authentication is available.

## Metadata Sync

Start with a small sample:

```bash
cf-aigw-analyzer sync -a <ACCOUNT_ID> --gateway-name <GATEWAY_NAME> --limit 100
```

Then run the full metadata sync:

```bash
cf-aigw-analyzer sync -a <ACCOUNT_ID> --gateway-name <GATEWAY_NAME> \
  --order-by created_at --direction asc --per-page 50
```

Sync is idempotent. Re-running the same command upserts rows by `(account_id, gateway_id, log_id)`.

## Usage Sync

Start small:

```bash
cf-aigw-analyzer sync-usage -a <ACCOUNT_ID> --gateway-name <GATEWAY_NAME> \
  --missing-only --limit 100 --usage-workers 4
```

Then fill the rest:

```bash
cf-aigw-analyzer sync-usage -a <ACCOUNT_ID> --gateway-name <GATEWAY_NAME> \
  --missing-only --usage-workers 8
```

`sync-usage` is recoverable:

- Missing rows are fetched.
- `failed` rows are retried by default.
- `no_usage` rows are not repeatedly fetched by `--missing-only`.
- Cloudflare response-body-unavailable 404 cases are stored as `no_usage`.

## Status and Query

```bash
cf-aigw-analyzer status
cf-aigw-analyzer status -a <ACCOUNT_ID> --gateway-name <GATEWAY_NAME>
cf-aigw-analyzer query -a <ACCOUNT_ID> --gateway-name <GATEWAY_NAME> --format table --limit 50
```

`query` excludes `raw_json`, `account_id`, and `gateway_id` from JSON/CSV/table outputs by default. Use `--include-raw-json` and `--include-scope` only for private local inspection.

## Local Dashboard

```bash
cf-aigw-analyzer dashboard -a <ACCOUNT_ID> --gateway-name <GATEWAY_NAME>
```

Defaults:

- host: `127.0.0.1`
- port: `8765`
- database: `local/data/cloudflare_ai_gateway.sqlite`

The dashboard reads local SQLite only. It does not sync logs, call Cloudflare, or upload data. Use `--host` only for trusted local-network scenarios; do not expose the dashboard to the public internet.

## Local Data Protection

Keep `local/` private. It is ignored by git, but it can still contain operational metadata. Do not attach or publish the SQLite database unless you have reviewed and approved the data.
