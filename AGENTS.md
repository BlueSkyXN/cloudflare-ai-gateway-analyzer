# Repository agent instructions

## Purpose

`cloudflare-ai-gateway-analyzer` is a Python 3.10+ local analytics tool for Cloudflare AI Gateway logs. It syncs sanitized log metadata into SQLite schema v7, parses provider response usage, stores analytics-ready facts in `log_events`, and serves a FastAPI control plane plus an embedded React/Vite/TypeScript panel.

## Codex startup behavior

- Codex is normally started from the repository root. This file is the root router and the first repo-local instruction source.
- Subdirectory `AGENTS.md` files are navigation cards. They are not assumed to be in startup context when Codex starts at the root.
- Before editing a path whose directory-map row says `Local AGENTS.md: Yes`, read the local card first with `cat <path>/AGENTS.md`.
- If multiple nested `AGENTS.md` files ever exist on the path to a target file, read them from shallow to deep before changing files.
- If an `AGENTS.override.md` appears in or above the target path, pause and ask the user whether to follow the override or revise the instruction layout. Do not silently write a normal `AGENTS.md` that the override would shadow.
- When adding or removing any future subdirectory `AGENTS.md`, update the directory map in this file in the same change.

## On-demand cat protocol

1. Locate the target path in the directory map.
2. If `Local AGENTS.md` is `Yes`, read that card before editing.
3. Apply the more specific card for local invariants and validation. Root rules still apply unless the local card explicitly narrows them.
4. Do not create subdirectory cards unless the subtree has distinct invariants, generated or readonly boundaries, high-risk behavior, or validation commands not covered here.

## Directory map

| Path | Responsibility | Local AGENTS.md | Read when |
|---|---|---:|---|
| `cli.py`, `main.py`, `serve.py` | Top-level entry points for Typer, compatibility dispatch, and FastAPI serve mode. | No | When changing startup, packaging, command dispatch, or compatibility behavior. |
| `src/cf_aigw_analyzer/cli/` | Typer command modules split by command area. | No | When adding or changing subcommands, options, output formats, or CLI validation. |
| `src/cf_aigw_analyzer/config/` | Pydantic v2 settings, YAML loader, env precedence, template rendering, validators, and redaction. | No | When changing config schema, defaults, env vars, secret handling, or `config show`. |
| `src/cf_aigw_analyzer/core/` | Cloudflare client, shared HTTP client, retry behavior, sanitizer, usage parser, and sync engine. | Yes | Before changing Cloudflare HTTP behavior, sync orchestration, usage parsing, concurrency, or sanitizer rules. |
| `src/cf_aigw_analyzer/data/` | SQLite schema v7, migrations, DB connections, row models, and repositories. | Yes | Before changing schema, migrations, indexes, repository writes, readonly connection behavior, or data contracts. |
| `src/cf_aigw_analyzer/analytics/` | Read-only SQL aggregation over `log_events` for `/api/v1/analytics`. | No | When changing aggregate metrics, filter semantics, time windows, or analytics payload shape. |
| `src/cf_aigw_analyzer/control/` | FastAPI app, routes, schemas, auth, middleware, lifespan, static panel hosting, and async job registry. | Yes | Before adding routes, changing auth, schemas, OpenAPI behavior, static hosting, or background sync jobs. |
| `src/cf_aigw_analyzer/models/` | Shared enums such as `FetchStatus`, `OutputFormat`, and `LogFormat`. | No | When adding shared domain enums or changing enum wire values. |
| `src/cf_aigw_analyzer/utils/` | Console, time, and path helpers. | No | When introducing shared utility primitives used across CLI/control/core. |
| `web/` | React 18 + Vite 5 + TypeScript 5 strict panel using ECharts, React Query, Zustand, and Tailwind. | Yes | Before changing frontend pages, hooks, API types, routing, theme, build config, or visible UI. |
| `tests/unit/` | Offline deterministic tests for parsers, repositories, analytics, sanitizer, config, and helpers. | No | When adding tests for pure Python units or updating tests alongside touched modules. |
| `tests/integration/` | CLI, ASGI, and sync-engine integration tests using local SQLite and `httpx.MockTransport`. | No | When testing behavior across CLI, DB, control plane, and sync engine. |
| `scripts/` | Operational helpers: seed data, non-live smoke, OpenAPI export, and API smoke. | No | When adding or changing repo-local scripts; keep them offline unless explicitly documented otherwise. |
| `docs/` | User and contributor documentation: architecture, API contract, config, data model, operations, privacy, and development. | No | When user-visible behavior, API shape, config, operations, schema, or security posture changes. |
| `Dockerfile`, `docker-compose.yml`, `entrypoint.sh` | Container build, runtime image, compose service, entrypoint command mapping, and healthcheck. | No | When changing deployment surface, exposed ports, healthcheck auth, runtime env, or embedded panel build. |
| `config-example.yaml`, `.env.example` | Public configuration templates and documented environment variables. | No | Update together with config schema/default/env changes. Never put real credentials here. |
| `requirements.txt`, `requirements-dev.txt`, `pyproject.toml` | Python package metadata, install dependencies, dev dependencies, scripts, hatch build config, pytest and ruff config. | No | When changing dependency surface, Python support, packaging, lint/test configuration, or entry points. |
| `README.md`, `CHANGELOG.md`, `CLAUDE.md` | Human-facing overview, public change log, and non-Codex assistant guidance. | No | When public behavior changes; do not treat them as substitutes for this root router. |
| `local/` | Gitignored runtime data, generated OpenAPI snapshots, SQLite files, logs, and local notes. | No | Auxiliary context only. Do not commit; do not use as source of truth for contracts or roadmap. |
| `legacy/v0.2/` | Historical v0.2 Streamlit/urllib implementation. Reference only. | No | Read for context only. Do not modify, even for lint or instruction-card cleanup. |

## Confirmed commands

Commands were confirmed from repo config/docs. Prefer `python3`.

| Command | Purpose | Scope | Sandbox notes |
|---|---|---|---|
| `pip install -e ".[dev]"` | Editable install with dev tools. | repo | Needs network unless wheels are cached. |
| `PYTHONPATH=src python3 -m pytest -q` | Full Python unit + integration suite. | repo | Offline; tests use local SQLite and mocks. |
| `python3 -m ruff check src tests scripts cli.py main.py serve.py` | Python lint. | repo | Offline after dev dependencies are installed. |
| `python3 -m ruff format --check src tests scripts cli.py main.py serve.py` | Python format check. | repo | Offline after dev dependencies are installed. |
| `python3 scripts/smoke_local.py` | Canonical non-live backend smoke: ruff, pytest, OpenAPI export, API smoke. | repo | Offline; writes ignored artifacts such as `local/openapi.json`. |
| `python3 scripts/generate_openapi.py --output local/openapi.json` | Export FastAPI OpenAPI schema. | control/API | Offline; do not commit `local/openapi.json`. |
| `python3 scripts/check_api.py` | Exercise read-only GET routes with ASGI transport. | control/API | Offline; uses temporary local SQLite. |
| `python3 scripts/seed_sqlite.py --db local/data/cloudflare_ai_gateway.sqlite --count 200` | Seed deterministic synthetic data for local panel work. | local data | Offline; writes ignored SQLite files under `local/`. |
| `python3 cli.py --help` | List CLI commands and top-level options. | CLI | Offline. |
| `python3 cli.py config show` | Print redacted effective configuration. | config/CLI | Offline; do not expose secrets. |
| `python3 cli.py accounts`, `gateways`, `sync`, `sync-usage` | Live Cloudflare discovery and sync commands. | live CLI/sync | Require credentials and network; see Practical live workflow below. |
| `python3 cli.py status`, `python3 cli.py query` | Inspect local sync state and local events. | CLI/DB | Offline if DB exists. |
| `python3 cli.py serve` | Start FastAPI + embedded static panel. | control/web | Long-running; default bind is `127.0.0.1:56000` unless config/flags override. |
| `cd web && npm install` | Install panel dependencies. | web | Needs network for first install; use `npm ci` only after a lockfile exists. |
| `cd web && npm run dev` | Start Vite dev server for panel development. | web | Long-running; proxies `/api` to the control plane port. |
| `cd web && npm run lint` | Type-check app and Vite config without emitting JS. | web | Offline after npm deps are installed. |
| `cd web && npm run build` | Type-check and build panel into `web/dist/`. | web | Offline after npm deps are installed; output is gitignored. |
| `docker compose config` | Parse compose file. | Docker | Requires Docker Compose plugin; no Cloudflare credentials needed for parse. |
| `docker compose build` | Build runtime image, including web build and Python dependency install. | Docker | Requires Docker and network unless layers/deps are cached. |

## Global rules

- Default user-facing communication is Chinese; code, commands, paths, API names, config keys, libraries, and agent/skill names stay English.
- Python support is 3.10+. Ruff line length is 100. Ruff format is the formatter; do not introduce Black.
- Pydantic v2 only. No v1 shims.
- FastAPI 0.111+, Typer 0.12+, httpx 0.27+, tenacity 8+ are the established backend stack.
- React 18 + Vite 5 + TypeScript 5 strict are the frontend stack. Tailwind dark theme is defined in `web/tailwind.config.js`.
- Frontend `@/` imports must stay aligned in `web/tsconfig.json` and `web/vite.config.ts`.
- All Cloudflare HTTP calls must go through `cf_aigw_analyzer.core.http_client.HttpClient`. Do not add ad-hoc `httpx`, `urllib`, `requests`, or shell `curl` clients inside app code.
- Repositories own SQL writes. Analytics and read-only control dependencies open SQLite read-only.
- SQLite schema v7 keeps `log_events` as the single analytics fact table and `log_raw` as the sanitized log JSON side table; `gateways.raw_json` stores sanitized gateway configuration snapshots.
- `provider` is the only channel dimension. Do not add a `channel` DB column, API alias, TypeScript alias, or UI filter name.
- Time-window filters use `julianday(created_at)` and the v7 expression indexes.
- `control.auth_token` non-empty means every `/api/v1/*` route requires Bearer auth, including GET routes and docs/openapi endpoints.
- Sync trigger limits are positive integers only. `usage_workers` / `workers` must stay within `1..64`.
- Docker healthcheck must remain compatible with `CF_AIGW_CONTROL__AUTH_TOKEN`; do not add unauthenticated `/api/v1/health` exemptions.
- Never persist request or response bodies. Use `sanitize_log_metadata` for log metadata and `sanitize_gateway_metadata` for gateway configuration before any `raw_json` write. `/response` bodies are only parsed for usage and then discarded.
- `serve --reload` is intentionally rejected by the CLI; preserve the explicit rejection behavior unless the user approves a dev-server design change.
- `legacy/v0.2/` is read-only reference material. Do not edit it, even for obvious lint fixes or new instruction cards.

## Practical live workflow

- Prefer `./.env.local` for local live work; inject it with `set -a; . ./.env.local; set +a`.
- Cloudflare auth must provide either `CF_API_TOKEN`, or `CF_EMAIL` plus `CF_API_KEY`.
- Cloudflare may omit a separate gateway `name`; use the stable gateway `id` for `--gateway-name`.
- Typical sequence:
  - `python3 cli.py accounts`
  - `python3 cli.py gateways -a <ACCOUNT_ID> --save`
  - `python3 cli.py sync -a <ACCOUNT_ID> --gateway-name <GATEWAY_NAME> --with-usage --missing-only`
  - `python3 cli.py status --account-id <ACCOUNT_ID> --gateway-name <GATEWAY_NAME>`
  - `python3 cli.py query -a <ACCOUNT_ID> --gateway-name <GATEWAY_NAME> --format table --limit 20`
- Drop `--with-usage` when usage backfill is not needed; add `--incremental` for checkpoint sync.
- Drop `--missing-only` only when intentionally overwriting existing usage state.
- Any `usage_failed > 0` is not automatically a bug. Inspect `/api/v1/analytics`, sync run records, or `sync-usage` logs before deciding on retry behavior.

## Validation policy

- **Schema/repository change**: read `src/cf_aigw_analyzer/data/AGENTS.md`; run `PYTHONPATH=src python3 -m pytest tests/unit/test_repository.py -v tests/unit/test_analytics.py`.
- **Migration change**: also verify `PRAGMA user_version`, `migrations` records, and docs/data-model expectations; at minimum run the repository tests covering migration paths.
- **Parser change**: read `src/cf_aigw_analyzer/core/AGENTS.md`; run `PYTHONPATH=src python3 -m pytest tests/unit/test_usage_parser.py`; add relevant integration coverage when sync behavior changes.
- **Sanitizer change**: run `PYTHONPATH=src python3 -m pytest tests/unit/test_sanitizer.py`; confirm request/response body deny-list behavior is still enforced.
- **Sync orchestration change**: run `PYTHONPATH=src python3 -m pytest tests/integration/test_sync_engine.py` plus relevant repository tests.
- **Config change**: run `PYTHONPATH=src python3 -m pytest tests/unit/test_config_loader.py`; update `config-example.yaml`, `.env.example`, and `docs/config.md` when public config changes.
- **Route/schema/auth change**: read `src/cf_aigw_analyzer/control/AGENTS.md`; run `PYTHONPATH=src python3 -m pytest tests/integration/test_control.py`, `python3 scripts/generate_openapi.py --output local/openapi.json`, and `python3 scripts/check_api.py`.
- **CLI change**: run `PYTHONPATH=src python3 -m pytest tests/integration/test_cli.py` and `python3 cli.py --help`.
- **Analytics change**: run `PYTHONPATH=src python3 -m pytest tests/unit/test_analytics.py tests/integration/test_control.py`.
- **Frontend change**: read `web/AGENTS.md`; run `cd web && npm run lint && npm run build`. If visible behavior changes, also boot the panel with an isolated temp DB and verify in a browser.
- **Docker/compose change**: run `docker compose config` when Docker is available. If Docker is unavailable, verify static YAML/Dockerfile syntax as far as possible and state the limitation.
- **Broad or release-facing change**: prefer `python3 scripts/smoke_local.py`; add web lint/build for frontend or embedded panel changes.

If validation cannot run because dependencies, Docker, network, credentials, or time are unavailable, state what was skipped and the remaining risk.

## Do not

- Do not commit or stage `local/`, `config.yaml`, `web/dist/`, `web/node_modules/`, SQLite/WAL/SHM files, `.env`, `.env.local`, TypeScript build info, Vite emitted config JS/DTS, caches, or `.DS_Store`.
- Do not write real credentials, private URLs, private local paths, `.env` contents, customer data, or personal information into commits, docs, PR bodies, logs, screenshots, or test snapshots.
- Do not bypass the appropriate sanitizer before any `raw_json` persistence: `core.sanitizer.sanitize_log_metadata` for logs and `core.sanitizer.sanitize_gateway_metadata` for gateway metadata.
- Do not reintroduce retired split analytics tables: `logs`, `log_usage`, `log_metrics`, or `logs_raw`.
- Do not introduce a second dashboard process. The only UI surface is `web/` served by FastAPI, with Vite only for local frontend development.
- Do not add a license claim. Licensing is the user's decision.
- Do not run live Cloudflare smoke commands in CI/tests. Live validation belongs in scripts or local workflows with explicit credential checks.
- Do not regress to urllib, Streamlit, or threadpool sync in active code.
- Do not modify `legacy/v0.2/`.

## Commit hygiene

Use focused commits along these axes when the user asks for commits:

1. Guardrails / packaging: `pyproject.toml`, `.gitignore`, requirements files, Docker metadata.
2. Implementation + tests: `src/`, `tests`, `scripts`.
3. Documentation + agent instructions: `README.md`, `docs/`, `AGENTS.md`, `CLAUDE.md`, `CHANGELOG.md`.

Before each commit:

```bash
git status --short --ignored
git diff --check
```

## Notes for future agents

- `local/` may contain useful scratch context, generated OpenAPI snapshots, SQLite files, and runbooks, but tracked code/docs remain authoritative.
- `CHANGELOG.md` records public changes across released and unreleased versions.
