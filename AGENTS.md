# Repository agent instructions

## Purpose

`cloudflare-ai-gateway-analyzer` is a Python 3.10+ tool that pulls Cloudflare AI Gateway log metadata into a single SQLite file, parses provider response usage, and serves a FastAPI control plane plus a React/Vite/TypeScript panel for local analytics.

## Codex startup behavior

- Codex is normally started from the repository root. This file is the startup router.
- Subdirectory `AGENTS.md` files (when present) are navigation cards; read them before editing under those subtrees.
- If a future `AGENTS.override.md` appears, pause and confirm with the user before treating it as the new card.

## Directory map

| Path                                | Responsibility                                                                                   | Local AGENTS.md | Read when                                                                  |
| ----------------------------------- | ------------------------------------------------------------------------------------------------ | --------------: | -------------------------------------------------------------------------- |
| `cli.py`, `main.py`, `serve.py`     | Top-level entry points (Typer + sync + serve)                                                    | No              | When changing CLI surface or packaging                                     |
| `src/cf_aigw_analyzer/cli/`         | Typer subcommands (split per file)                                                               | No              | When adding/altering subcommands or flags                                  |
| `src/cf_aigw_analyzer/config/`      | Pydantic Settings, YAML loader, template renderer, redactor                                      | No              | When changing config schema, env precedence, or redaction                  |
| `src/cf_aigw_analyzer/core/`        | httpx-based Cloudflare client, retry policy, parsers, sync engine                                | No              | When touching HTTP behaviour, retries, usage parsing, or sync orchestration |
| `src/cf_aigw_analyzer/data/`        | SQLite schema, migrations, repositories, row models                                              | No              | Before any DB schema, index, or repository contract change                 |
| `src/cf_aigw_analyzer/analytics/`   | Read-only SQL aggregations (summary, timeseries, models, context buckets, events, insights)     | No              | When changing aggregation logic or filter semantics                        |
| `src/cf_aigw_analyzer/control/`     | FastAPI app, routes, schemas, auth, lifespan, static panel hosting, async job registry          | No              | When adding routes, changing schemas, or modifying auth                    |
| `src/cf_aigw_analyzer/models/`      | Shared enums (`FetchStatus`, `OutputFormat`, `LogFormat`)                                       | No              | When adding new domain enums                                               |
| `src/cf_aigw_analyzer/utils/`       | Console helpers, time/path utilities                                                             | No              | When introducing utility primitives                                        |
| `web/`                              | React 18 + Vite + TypeScript + ECharts + Tailwind panel                                          | No              | When changing the frontend (pages, hooks, types, theme)                    |
| `tests/unit/`                       | Pure-Python unit tests (offline, deterministic)                                                  | No              | When adding tests for parsers, repositories, analytics, config             |
| `tests/integration/`                | CLI + ASGI + sync-engine integration tests using `httpx.MockTransport`                           | No              | When adding tests that span CLI ↔ DB ↔ control plane                       |
| `scripts/`                          | `seed_sqlite.py`, `smoke_local.py`, `generate_openapi.py`, `check_api.py`                       | No              | When adding new operational/CI helper scripts                              |
| `docs/`                             | User + contributor documentation                                                                 | No              | When user-visible behaviour or interfaces change                           |
| `Dockerfile`, `docker-compose.yml`, `entrypoint.sh` | Container build + runtime                                                            | No              | When changing the deployment surface                                       |
| `local/`                            | Gitignored runtime data (SQLite, openapi.json, refactor notes, task tracker, review reports)    | No              | Do not commit. Inspect read-only.                                          |
| `legacy/v0.2/`                      | Historical v0.2 source (Streamlit dashboard, urllib client). Reference only.                     | No              | **Do not modify.** Read for context only.                                  |
| `config-example.yaml`, `.env.example` | Public configuration templates                                                                 | No              | Update together with schema changes                                        |

## Confirmed commands

| Command                                                                                                     | Purpose                                                              | Sandbox notes                                                |
| ----------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------- | ------------------------------------------------------------ |
| `pip install -e ".[dev]"`                                                                                   | Editable install + dev tooling                                       | Needs network unless wheels are cached                       |
| `PYTHONPATH=src python -m pytest -q`                                                                        | Full unit + integration suite                                        | Offline; <5s on a modern laptop                              |
| `python -m ruff check src tests scripts cli.py main.py serve.py`                                            | Lint                                                                 | Offline                                                      |
| `python -m ruff format --check src tests scripts cli.py main.py serve.py`                                   | Format check                                                         | Offline                                                      |
| `python scripts/seed_sqlite.py --db local/data/cloudflare_ai_gateway.sqlite --count 200`                    | Seed deterministic synthetic data                                    | Offline                                                      |
| `python scripts/generate_openapi.py --output local/openapi.json`                                            | Dump OpenAPI                                                         | Offline                                                      |
| `python scripts/check_api.py`                                                                               | Boot FastAPI in-process and exercise GET routes                      | Offline (ASGI transport)                                     |
| `python scripts/smoke_local.py`                                                                             | Aggregate: ruff + pytest + openapi + api smoke                       | Offline                                                      |
| `python cli.py --help`                                                                                      | List CLI subcommands                                                 | Offline                                                      |
| `python cli.py config show`                                                                                 | Print redacted effective configuration                               | Offline                                                      |
| `python cli.py serve`                                                                                       | Start FastAPI on `127.0.0.1:8765`                                    | Long-running                                                 |
| `cd web && npm ci && npm run build`                                                                         | Build the panel into `web/dist`                                      | Needs network for first install                              |
| `docker compose build`                                                                                      | Build the runtime image                                              | Needs network                                                |

## Global rules

- Default communication is Chinese; code, paths, commands, API names stay English.
- Python 3.10+, ruff line length 100. No Black.
- Pydantic v2 everywhere (no v1 compat). FastAPI 0.111+. Typer 0.12+. httpx 0.27+. tenacity 8+.
- React 18 + Vite 5 + TypeScript 5 strict. Tailwind with the dark-by-default theme defined in `web/tailwind.config.js`.
- All Cloudflare HTTP calls go through `cf_aigw_analyzer.core.http_client.HttpClient`. No new ad-hoc requests/urllib clients.
- Repositories own all SQL writes. Analytics modules open the DB read-only.
- Auth is uniform: `control.auth_token` non-empty → every `/api/v1/*` route requires Bearer, including GETs and `/docs`.
- Never persist request/response bodies. The sanitizer runs before any `raw_json` write.
- `legacy/v0.2/` is read-only reference. Do not edit, even for "obvious" lint fixes.

## Validation policy

- **Schema/repository change** → `pytest tests/unit/test_repository.py -v` + `pytest tests/unit/test_analytics.py`.
- **Parser change** → `pytest tests/unit/test_usage_parser.py` + relevant integration tests.
- **Route change** → `pytest tests/integration/test_control.py` + `python scripts/generate_openapi.py` (commit the regenerated file when applicable) + `python scripts/check_api.py`.
- **CLI change** → `pytest tests/integration/test_cli.py` + `python cli.py --help`.
- **Frontend change** → `cd web && npm run lint && npm run build`. If the change is visible, also boot the panel via `python cli.py serve` and verify in a browser.

If a step cannot run (missing dependency, network unavailable), state that clearly in the final response.

## Do not

- Do not commit `local/`, `config.yaml`, `web/dist/`, SQLite/WAL files, `.env`, or `legacy/v0.2/` edits.
- Do not bypass `core.sanitizer.sanitize_log_metadata` for any reason.
- Do not introduce a new dashboard process. The only UI surface is `web/` + FastAPI.
- Do not add a license claim. Licensing decision is the user's.
- Do not run live Cloudflare smoke commands in CI/tests. Live validation belongs in `scripts/` with explicit credential checks.
- Do not regress to urllib / Streamlit / threadpool sync.

## Commit hygiene

Focused commits along these axes:

1. Guardrails / packaging (`pyproject.toml`, `.gitignore`, requirements files).
2. Implementation + tests (`src/`, `tests/`).
3. Documentation + agent instructions (`README.md`, `docs/`, `AGENTS.md`, `CLAUDE.md`, `CHANGELOG.md`).

Before each commit:

```bash
git status --short --ignored
git diff --check
```

## Notes for future agents

- `local/refactor/plan.md` documents the v0.3 rewrite plan and decision log.
- `local/task-tracker.md` tracks the YOLO-mode execution that produced v0.3.
- `local/copilot-check.md` carries the post-rewrite code review report.
- `CHANGELOG.md` records the public diff between v0.2 and v0.3.
- `CLAUDE.md` is project-level guidance for Claude/AI assistants.
