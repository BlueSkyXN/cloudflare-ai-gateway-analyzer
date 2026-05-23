# Security & Privacy

The analyzer is intended to live on the operator's machine (or a private container) and to never expose Cloudflare credentials or raw model traffic to the outside world.

## Trust boundaries

1. **Cloudflare API** — outbound HTTPS only, TLS pinned to the system trust store augmented with `certifi`.
2. **Local SQLite** — full operational metadata. Treat as sensitive; do **not** ship the file off-box without redaction.
3. **FastAPI control plane** — binds 127.0.0.1 by default. Crossing the loopback boundary requires both `control.host != 127.0.0.1` and `control.auth_token` set.
4. **React panel** — served by the FastAPI process. Cannot read the database directly.

## Credentials

- Recommended: set `CF_API_TOKEN` in your shell or `.env`. Token scopes should be limited to AI Gateway reads.
- Legacy: `CF_EMAIL` + `CF_API_KEY` (Global API Key) is supported but discouraged.
- The CLI exposes `--api-token` / `--email` / `--api-key` flags only via `config.yaml` indirection; we deliberately did not add direct command-line flags to keep credentials out of shell history.
- `redact_settings` returns `"***"` for any `SecretStr` field, used by `cf-aigw-analyzer config show` and `GET /api/v1/config`.

## Body content

`cf_aigw_analyzer.core.sanitizer.sanitize_log_metadata` recursively strips any dict key matching a deny-list (`request`, `response`, `messages`, `prompt`, `input`, `text`, etc., case-insensitive) before persistence. Both `logs.raw_json` (legacy column, dropped in v0.3) and the new `logs_raw` table are populated only with the sanitized form. The `/response` endpoint is contacted solely to parse usage; the body itself is never written to disk.

## Sharing exports

`cf-aigw-analyzer query` excludes `raw_json`, `account_id`, and `gateway_id` from JSON/CSV/table output by default. Use `--include-raw-json` / `--include-scope` only for local inspection. The dashboard's events endpoint applies the same field whitelist.

## Auth model

| `control.auth_token`         | Loopback                           | Non-loopback (`0.0.0.0` etc.)                                  |
| ---------------------------- | ---------------------------------- | -------------------------------------------------------------- |
| empty (default)              | Open. Trusted local machine.       | Refuses to start (config validation surfaces the warning).      |
| any string                   | All `/api/v1/*` and `/docs` need `Authorization: Bearer …`. | Same as loopback case.                                          |

There is no per-route exemption. GET endpoints can leak summary statistics, sync state, and (redacted) configuration, so we apply uniform bearer auth.

## Logging & tracing

- The CLI uses Rich for human output and prints structured failure messages, never raw secrets.
- FastAPI access logs come from Uvicorn; redirecting them to a file is left to the operator.
- Bearer tokens are compared with constant-length string equality. There is no token rotation flow in v0.3.

## Git hygiene

`/local/`, `/config.yaml`, `*.sqlite`, `*.sqlite-wal`, `*.sqlite-shm`, `web/dist/`, `web/node_modules/` are all gitignored. Run `git status --short --ignored` before pushing to confirm.

The `legacy/v0.2/` directory contains the old single-file Streamlit implementation as a reference. It must not be edited; treat its tests as historical.

## Threat model coverage

| Threat                                     | Mitigation                                                              |
| ------------------------------------------ | ----------------------------------------------------------------------- |
| Browser cross-site request to dashboard    | Loopback-only bind + optional bearer token.                              |
| Body content leak via SQLite               | Recursive sanitizer + `logs_raw` separation.                             |
| Credential exposure in process list        | No `--api-token` CLI flag; env vars only.                                |
| Credential exposure in config dump         | `redact_settings` enforces `"***"`.                                       |
| Replay of stale sync state                 | `sync_runs` records every invocation; `missing_only` is opt-in.          |
| Cloudflare TLS interception                | `certifi`-backed default context, no plaintext fallback.                 |

## Out of scope

- Multi-tenant access control. The analyzer assumes a single operator.
- Audit log tamper-evidence. The `sync_runs` table is best-effort; combine with filesystem snapshots if you need stronger guarantees.
- Network egress isolation. Use a containerized deployment plus an outbound firewall if you need to limit Cloudflare reachability.
