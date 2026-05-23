# Development

## Local setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

For the React panel:

```bash
cd web
npm ci
```

## Running locally

```bash
# Initialize SQLite + write template
python cli.py init

# Seed synthetic data (no Cloudflare calls)
python scripts/seed_sqlite.py --db local/data/cloudflare_ai_gateway.sqlite --count 200

# Run FastAPI on localhost
python cli.py serve

# Run Vite dev server in another shell
cd web && npm run dev
```

Visit `http://127.0.0.1:5173` for the development panel (proxied to `127.0.0.1:8765`) or `http://127.0.0.1:8765` for the embedded panel.

## Validation

The canonical pre-commit gate is `scripts/smoke_local.py`. It runs:

```
ruff check
ruff format --check
pytest -q
scripts/generate_openapi.py
scripts/check_api.py
```

Individually:

```bash
PYTHONPATH=src python3 -m pytest -q
python3 -m ruff check src tests scripts cli.py main.py serve.py
python3 -m ruff format --check src tests scripts cli.py main.py serve.py
```

For panel changes:

```bash
cd web
npm run lint    # tsc -b --noEmit
npm run build
```

## Project layout

```
src/cf_aigw_analyzer/
  cli/        Typer subcommands
  config/     Pydantic Settings + YAML loader
  core/       httpx-based Cloudflare client, parsers, sync engine
  data/       SQLite repositories, schema, migrations
  analytics/  Read-only SQL aggregation
  control/    FastAPI app, routes, schemas, auth, async tasks
  models/     Shared enums
  utils/      Time/path/console helpers

web/          React 18 + Vite + TS panel
tests/
  unit/       Repository + parser + analytics tests (offline)
  integration/ ASGI / CLI / sync-engine tests with httpx.MockTransport
scripts/      Seed, smoke, OpenAPI generator, API smoke
docs/         User/contributor docs
local/        Gitignored runtime data + planning notes
legacy/v0.2/  Historical v0.2 source for reference
```

## Tests

- **Unit** tests live in `tests/unit/` and exercise pure-Python modules (parsers, metrics, sanitizer, repositories, analytics, config loader).
- **Integration** tests in `tests/integration/` boot the CLI (`typer.testing.CliRunner`) or the FastAPI app (`httpx.ASGITransport`). Every Cloudflare call is mocked via `httpx.MockTransport`.

There are **no** live-network tests by default. If you need to validate against real Cloudflare credentials, run the CLI smoke commands documented in `docs/operations.md` manually and **never** commit recorded responses.

## Adding new endpoints

1. Add a Pydantic response schema in `src/cf_aigw_analyzer/control/schemas/`.
2. Add a router file under `src/cf_aigw_analyzer/control/routes/` and export it from `routes/__init__.py`.
3. Wire it up in `control/app.build_app`.
4. Add an integration test that hits the route through `httpx.ASGITransport`.
5. Re-run `scripts/generate_openapi.py` and commit the updated `local/openapi.json` if you check it in.

## Adding new SQL aggregations

1. Push the aggregation into SQL inside `cf_aigw_analyzer/analytics/`. Do not pull the row set into Python.
2. Use the shared `AnalyticsFilters` + `build_where` helper for consistent filtering.
3. Add a unit test with a seeded SQLite under `tests/unit/test_analytics.py`.

## Adding a CLI subcommand

1. Create a module under `src/cf_aigw_analyzer/cli/` named `<verb>_cmd.py`.
2. Register the command in `cli/app.py`.
3. Add an integration test in `tests/integration/test_cli.py`. Use `CliRunner` and `httpx.MockTransport` for any network paths.
4. Update `docs/operations.md` if user-facing.

## Commit boundaries

We prefer focused commits along these axes:

1. Guardrails / packaging (`.gitignore`, `pyproject.toml`, `requirements*.txt`).
2. Implementation + tests (`src/`, `tests/`).
3. Documentation + agent instructions (`README.md`, `docs/`, `AGENTS.md`, `CLAUDE.md`).

Before each commit:

```bash
git status --short --ignored
git diff --check
```

## Coding standards

- Python 3.10+. Type hints everywhere; `from __future__ import annotations` enabled.
- Ruff line length 100; ruff format is the only auto-formatter (no Black).
- Tests use pytest fixtures + `pytest-asyncio` auto mode.
- React panel uses TypeScript strict mode; no implicit `any`. Imports go through `@/` alias.

## Updating dependencies

- Runtime deps live in `pyproject.toml` `[project] dependencies` and mirrored in `requirements.txt`.
- Dev deps are in `[project.optional-dependencies] dev` and mirrored in `requirements-dev.txt`.
- Bump versions thoughtfully — major Pydantic / FastAPI / httpx revs almost always require local validation.

## Releasing

There is no automated release workflow yet. To produce a wheel for local install:

```bash
pip install hatch
hatch build
```

The hatch wheel includes `web/dist/` if it exists at build time (see `pyproject.toml`).
