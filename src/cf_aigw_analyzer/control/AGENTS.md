# src/cf_aigw_analyzer/control navigation card

FastAPI control plane for config/status/analytics/sync APIs, auth, app lifecycle, static panel hosting, and in-process job tracking.
Read this card before editing routes, schemas, auth, middleware, lifespan state, static hosting, or background sync jobs.
Key files: `app.py`, `auth.py`, `deps.py`, `lifecycle.py`, `tasks.py`, `static.py`, `routes/`, and `schemas/`.

## Local invariants

- Every public control API stays under `/api/v1`.
- When `control.auth_token` is non-empty, every `/api/v1/*` route requires Bearer auth, including GET routes and docs/openapi.
- Read-only route dependencies must use readonly SQLite connections.
- Sync trigger requests must enforce positive limits and worker bounds `1..64`.
- Background jobs stay in-process through the current job registry; there is no external queue in this project.
- The React panel is served by this FastAPI process after `web/dist` exists.

## Local rules

- Route or schema changes should update OpenAPI output and any affected frontend API types/usages.
- Auth changes must keep Docker healthcheck compatibility with `CF_AIGW_CONTROL__AUTH_TOKEN`.
- Keep API errors deterministic enough for integration tests; do not rely on live Cloudflare behavior in route tests.

## Do not

- Do not add unauthenticated health or docs exemptions when auth is configured.
- Do not add a second dashboard server or background worker service.
- Do not write to SQLite from analytics/read-only GET paths.

## Validation

- `PYTHONPATH=src python3 -m pytest tests/integration/test_control.py`
- `python3 scripts/generate_openapi.py --output local/openapi.json`
- `python3 scripts/check_api.py`
