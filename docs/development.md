# Development

## Environment

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

For dashboard development:

```bash
pip install -e ".[dashboard]"
```

## Validation

Run these before committing code changes:

```bash
PYTHONPATH=src python3 -m compileall -q src tests
PYTHONPATH=src python3 -m unittest discover -s tests
PYTHONPATH=src python3 -m cf_aigw_analyzer.cli --help
PYTHONPATH=src python3 -m cf_aigw_analyzer.cli dashboard --help
```

Run these before committing data-sync behavior changes if credentials are available:

```bash
cf-aigw-analyzer accounts
cf-aigw-analyzer gateways -a <ACCOUNT_ID>
cf-aigw-analyzer sync -a <ACCOUNT_ID> --gateway-name <GATEWAY_NAME> --limit 10
cf-aigw-analyzer sync-usage -a <ACCOUNT_ID> --gateway-name <GATEWAY_NAME> --missing-only --limit 10
```

Do not include real IDs, credentials, or local SQLite files in commit messages.

## Project Layout

```text
src/cf_aigw_analyzer/
  cli.py          CLI commands
  cloudflare.py   Cloudflare API client
  analytics.py    read-only SQLite analytics
  database.py     SQLite schema and repository
  dashboard.py    Streamlit launcher
  dashboard_app.py Streamlit dashboard UI
  filters.py      Cloudflare log filters
  output.py       table/json/csv output
  paths.py        local path resolution
  sync.py         sync orchestration
  usage.py        usage parser
tests/
  unittest tests
docs/
  project documentation
```

## Commit Hygiene

Use focused commits:

1. Guardrails and packaging.
2. Implementation and tests.
3. Documentation and agent instructions.

Before committing:

```bash
git status --short --ignored
git diff --check
```
