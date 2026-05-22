# cloudflare-ai-gateway-analyzer

Cloudflare AI Gateway log collector and SQLite analyzer.

This project stores Cloudflare AI Gateway log metadata in one local SQLite database, extracts token usage from each log response endpoint, and keeps calculated metrics in separate 1:1 tables. It does not generate XLSX files and does not store request or response body content by default.

## Status

- Runtime: Python 3.10+
- Storage: one SQLite file under `local/data/`
- Runtime dependency: `certifi` for reliable TLS certificate verification
- Optional dashboard dependencies: `streamlit`, `plotly`, and `pandas`
- License: not selected yet. No open-source license is granted until a license file is added.

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

Install the local dashboard extra when you want the browser analytics view:

```bash
pip install -e ".[dashboard]"
```

Available CLI entries:

```bash
cf-aigw-analyzer --help
cloudflare-ai-gateway-analyzer --help
```

## Authentication

Recommended:

```bash
export CF_API_TOKEN="your-token"
```

Also supported:

```bash
export CF_EMAIL="you@example.com"
export CF_API_KEY="your-global-api-key"
```

CLI flags `--api-token`, `--email`, and `--api-key` override environment variables. Do not commit real credentials, account IDs, private endpoints, or customer data.

## SQLite Database

Default path:

```text
local/data/cloudflare_ai_gateway.sqlite
```

All accounts and gateways share this one database. Rows are scoped by `(account_id, gateway_id, log_id)`.

Core tables:

- `gateways`: gateway metadata.
- `logs`: log metadata only. Request and response body-like fields are removed before storage.
- `log_usage`: 1:1 parsed token usage per log.
- `log_metrics`: 1:1 calculated metrics per log.
- `sync_runs`: sync run records.

The whole `local/` directory is ignored by git.

## Common Commands

Initialize the database:

```bash
cf-aigw-analyzer init
```

List accounts and gateways:

```bash
cf-aigw-analyzer accounts
cf-aigw-analyzer gateways -a <ACCOUNT_ID>
cf-aigw-analyzer gateways -a <ACCOUNT_ID> --save
```

Sync metadata:

```bash
cf-aigw-analyzer sync -a <ACCOUNT_ID> --gateway-name <GATEWAY_NAME> \
  --order-by created_at --direction asc
```

Sync metadata and token usage in one command:

```bash
cf-aigw-analyzer sync -a <ACCOUNT_ID> --gateway-name <GATEWAY_NAME> \
  --with-usage --missing-only --usage-workers 8
```

Only fill missing usage:

```bash
cf-aigw-analyzer sync-usage -a <ACCOUNT_ID> --gateway-name <GATEWAY_NAME> \
  --missing-only --usage-workers 8
```

Query local data:

```bash
cf-aigw-analyzer query -a <ACCOUNT_ID> --gateway-name <GATEWAY_NAME> --format table --limit 50
mkdir -p local/exports
cf-aigw-analyzer query -a <ACCOUNT_ID> --gateway-name <GATEWAY_NAME> --format json --output local/exports/logs.json
cf-aigw-analyzer query -a <ACCOUNT_ID> --gateway-name <GATEWAY_NAME> --format csv --output local/exports/logs.csv
```

`query` excludes `raw_json`, `account_id`, and `gateway_id` from shareable outputs by default. Use `--include-raw-json` and `--include-scope` only for private local inspection.

Check status:

```bash
cf-aigw-analyzer status
cf-aigw-analyzer status -a <ACCOUNT_ID> --gateway-name <GATEWAY_NAME>
```

Start the local analytics dashboard:

```bash
cf-aigw-analyzer dashboard -a <ACCOUNT_ID> --gateway-name <GATEWAY_NAME>
```

The dashboard binds to `127.0.0.1:8765` by default and reads the SQLite database locally. It does not call Cloudflare or upload data.

## Documentation

- [Architecture](docs/architecture.md)
- [Data model](docs/data-model.md)
- [Operations](docs/operations.md)
- [Security and privacy](docs/security-and-privacy.md)
- [Development](docs/development.md)

## Validation

```bash
PYTHONPATH=src python3 -m compileall -q src tests
PYTHONPATH=src python3 -m unittest discover -s tests
PYTHONPATH=src python3 -m cf_aigw_analyzer.cli --help
PYTHONPATH=src python3 -m cf_aigw_analyzer.cli dashboard --help
```
