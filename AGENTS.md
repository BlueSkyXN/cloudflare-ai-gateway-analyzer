# Repository agent instructions

## Purpose

`cloudflare-ai-gateway-analyzer` is a Python 3.10+ tool that pulls Cloudflare AI Gateway log metadata into a local SQLite file, parses provider response usage, stores analytics-ready rows in one `log_events` fact table, and serves a FastAPI control plane plus a React/Vite/TypeScript panel for local analytics.

## Codex startup behavior

- Codex is normally started from the repository root. This file is the startup router.
- Subdirectory `AGENTS.md` files (when present) are navigation cards; read them before editing under those subtrees.
- If a future `AGENTS.override.md` appears, pause and confirm with the user before treating it as the new card.
- When adding a future subdirectory `AGENTS.md`, update the directory map here with when to read it.

## On-demand cat protocol

- Before editing any path whose directory-map row says `Local AGENTS.md: Yes`, read that local card first.
- If a future `AGENTS.override.md` exists in or above the target path, stop and ask whether to follow the override or revise the instruction layout.
- Do not create subdirectory cards unless the subtree has distinct invariants, generated/readonly boundaries, or validation commands not covered here.

## Directory map

| Path                                | Responsibility                                                                                   | Local AGENTS.md | Read when                                                                  |
| ----------------------------------- | ------------------------------------------------------------------------------------------------ | --------------: | -------------------------------------------------------------------------- |
| `cli.py`, `main.py`, `serve.py`     | Top-level entry points (Typer + sync + serve)                                                    | No              | When changing CLI surface or packaging                                     |
| `src/cf_aigw_analyzer/cli/`         | Typer subcommands (split per file)                                                               | No              | When adding/altering subcommands or flags                                  |
| `src/cf_aigw_analyzer/config/`      | Pydantic Settings, YAML loader, template renderer, redactor                                      | No              | When changing config schema, env precedence, or redaction                  |
| `src/cf_aigw_analyzer/core/`        | httpx-based Cloudflare client, retry policy, parsers, sync engine                                | No              | When touching HTTP behaviour, retries, usage parsing, or sync orchestration |
| `src/cf_aigw_analyzer/data/`        | SQLite schema v6, migrations, repositories, row models                                          | No              | Before any DB schema, index, or repository contract change                 |
| `src/cf_aigw_analyzer/analytics/`   | Unified read-only SQL aggregation over `log_events`                                              | No              | When changing aggregation logic, filter semantics, or `/api/v1/analytics` payloads |
| `src/cf_aigw_analyzer/control/`     | FastAPI app, routes, schemas, auth, lifespan, static panel hosting, async job registry          | No              | When adding routes, changing schemas, or modifying auth                    |
| `src/cf_aigw_analyzer/models/`      | Shared enums (`FetchStatus`, `OutputFormat`, `LogFormat`)                                       | No              | When adding new domain enums                                               |
| `src/cf_aigw_analyzer/utils/`       | Console helpers, time/path utilities                                                             | No              | When introducing utility primitives                                        |
| `web/`                              | React 18 + Vite + TypeScript + ECharts + Tailwind panel                                          | No              | When changing the frontend (pages, hooks, types, theme)                    |
| `tests/unit/`                       | Pure-Python unit tests (offline, deterministic)                                                  | No              | When adding tests for parsers, repositories, analytics, config             |
| `tests/integration/`                | CLI + ASGI + sync-engine integration tests using `httpx.MockTransport`                           | No              | When adding tests that span CLI ↔ DB ↔ control plane                       |
| `scripts/`                          | `seed_sqlite.py`, `smoke_local.py`, `generate_openapi.py`, `check_api.py`                       | No              | When adding new operational/CI helper scripts                              |
| `docs/`                             | User + contributor documentation                                                                 | No              | When user-visible behaviour or interfaces change                           |
| `Dockerfile`, `docker-compose.yml`, `entrypoint.sh` | Container build + runtime                                                            | No              | When changing the deployment surface                                       |
| `local/`                            | Gitignored runtime data, generated OpenAPI, runbooks, and local-only notes                       | No              | Do not commit. Auxiliary context only; tracked code/docs remain authoritative. |
| `legacy/v0.2/`                      | Historical v0.2 source (Streamlit dashboard, urllib client). Reference only.                     | No              | **Do not modify.** Read for context only.                                  |
| `config-example.yaml`, `.env.example` | Public configuration templates                                                                 | No              | Update together with schema changes                                        |

## Confirmed commands

| Command                                                                                                     | Purpose                                                              | Sandbox notes                                                |
| ----------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------- | ------------------------------------------------------------ |
| `pip install -e ".[dev]"`                                                                                   | Editable install + dev tooling                                       | Needs network unless wheels are cached                       |
| `PYTHONPATH=src python3 -m pytest -q`                                                                       | Full unit + integration suite                                        | Offline; <5s on a modern laptop                              |
| `python3 -m ruff check src tests scripts cli.py main.py serve.py`                                           | Lint                                                                 | Offline                                                      |
| `python3 -m ruff format --check src tests scripts cli.py main.py serve.py`                                  | Format check                                                         | Offline                                                      |
| `python3 scripts/seed_sqlite.py --db local/data/cloudflare_ai_gateway.sqlite --count 200`                   | Seed deterministic synthetic data                                    | Offline                                                      |
| `python3 scripts/generate_openapi.py --output local/openapi.json`                                           | Dump OpenAPI to a gitignored local file                              | Offline                                                      |
| `python3 scripts/check_api.py`                                                                              | Boot FastAPI in-process and exercise GET routes                      | Offline (ASGI transport)                                     |
| `python3 scripts/smoke_local.py`                                                                            | Aggregate: ruff + pytest + openapi + api smoke                       | Offline                                                      |
| `python3 cli.py --help`                                                                                     | List CLI subcommands                                                 | Offline                                                      |
| `python3 cli.py config show`                                                                                | Print redacted effective configuration                               | Offline                                                      |
| `python3 cli.py serve`                                                                                      | Start FastAPI on `127.0.0.1:8765`                                    | Long-running                                                 |
| `cd web && npm install`                                                                                     | Install panel dependencies                                           | Needs network for first install; use `npm ci` only after a lockfile exists |
| `cd web && npm run lint`                                                                                    | Type-check app + Vite config without emitting JS                     | Offline after deps installed                                 |
| `cd web && npm run build`                                                                                   | Build the panel into gitignored `web/dist`                           | Offline after deps installed                                 |
| `docker compose build`                                                                                      | Build the runtime image                                              | Needs network                                                |

## Global rules

- Default communication is Chinese; code, paths, commands, API names stay English.
- Python 3.10+, ruff line length 100. No Black.
- Pydantic v2 everywhere (no v1 compat). FastAPI 0.111+. Typer 0.12+. httpx 0.27+. tenacity 8+.
- React 18 + Vite 5 + TypeScript 5 strict. Tailwind with the dark-by-default theme defined in `web/tailwind.config.js`.
- Frontend imports may use `@/` for `web/src`; keep `tsconfig.json` paths and `vite.config.ts` alias in sync.
- All Cloudflare HTTP calls go through `cf_aigw_analyzer.core.http_client.HttpClient`. No new ad-hoc requests/urllib clients.
- Repositories own all SQL writes. Analytics modules open the DB read-only.
- SQLite schema v6 keeps `log_events` as the single analytics fact table and `log_raw` as the sanitized JSON side table.
- `provider` is the only channel dimension. Do not add a `channel` column or API alias.
- Auth is uniform: `control.auth_token` non-empty -> every `/api/v1/*` route requires Bearer, including GETs and `/docs`.
- Sync trigger limits are positive integers only; `usage_workers` / `workers` stay within `1..64`.
- Docker healthcheck must remain compatible with `CF_AIGW_CONTROL__AUTH_TOKEN`; do not add unauthenticated `/api/v1/health` exemptions.
- Never persist request/response bodies. The sanitizer runs before any `raw_json` write.
- `legacy/v0.2/` is read-only reference. Do not edit, even for "obvious" lint fixes.

## Validation policy

- **Schema/repository change** -> `pytest tests/unit/test_repository.py -v` + `pytest tests/unit/test_analytics.py`.
- **Parser change** -> `pytest tests/unit/test_usage_parser.py` + relevant integration tests.
- **Sync orchestration change** -> `pytest tests/integration/test_sync_engine.py` + relevant repository tests.
- **Route change** -> `pytest tests/integration/test_control.py` + `python3 scripts/generate_openapi.py --output local/openapi.json` + `python3 scripts/check_api.py`; `local/openapi.json` is gitignored unless project policy changes.
- **CLI change** -> `pytest tests/integration/test_cli.py` + `python3 cli.py --help`.
- **Frontend change** -> `cd web && npm run lint && npm run build`. If the change is visible, also boot the panel with an isolated temp DB and verify in a browser.
- **Docker/compose change** -> parse with `docker compose config` when Docker is available; otherwise at least verify YAML parsing and state Docker was unavailable.

If a step cannot run (missing dependency, network unavailable), state that clearly in the final response.

## Do not

- Do not commit `local/`, `config.yaml`, `web/dist/`, `web/node_modules/`, SQLite/WAL/SHM files, `.env`, TypeScript build info, Vite emitted config JS/DTS, or `legacy/v0.2/` edits.
- Do not bypass `core.sanitizer.sanitize_log_metadata` for any reason.
- Do not reintroduce the retired split analytics tables `logs`, `log_usage`, `log_metrics`, or `logs_raw`.
- Do not introduce a new dashboard process. The only UI surface is `web/` + FastAPI.
- Do not add a license claim. Licensing decision is the user's.
- Do not run live Cloudflare smoke commands in CI/tests. Live validation belongs in `scripts/` with explicit credential checks.
- Do not regress to urllib / Streamlit / threadpool sync.

## Commit hygiene

Focused commits along these axes:

1. Guardrails / packaging (`pyproject.toml`, `.gitignore`, requirements files).
2. Implementation + tests (`src/`, `tests`).
3. Documentation + agent instructions (`README.md`, `docs/`, `AGENTS.md`, `CLAUDE.md`, `CHANGELOG.md`).

Before each commit:

```bash
git status --short --ignored
git diff --check
```

## Notes for future agents

- `local/` may contain gitignored runbooks, generated OpenAPI snapshots, SQLite files, and scratch reports. Treat it as local context only; do not use it as the source of truth for commands, schema, API contracts, or roadmap status.
- `CHANGELOG.md` records public changes across released and unreleased versions.
- `CLAUDE.md` is project-level guidance for Claude/AI assistants.
