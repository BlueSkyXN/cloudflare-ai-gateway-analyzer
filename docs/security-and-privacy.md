# Security & Privacy

The analyzer is intended to live on the operator's machine (or a private container) and to never expose Cloudflare credentials or raw model traffic to the outside world.

## Trust boundaries

1. **Cloudflare API** — outbound HTTPS only, TLS pinned to the system trust store augmented with `certifi`.
2. **Local SQLite** — operational metadata and token/timing statistics. Treat as sensitive; do **not** ship the file off-box without redaction.
3. **FastAPI control plane** — binds 127.0.0.1 by default. If you set `control.host` to a non-loopback address, also set `control.auth_token`; the current runtime does not enforce that guard for you.
4. **React panel** — served by the FastAPI process. Cannot read the database directly.

## Credentials

- Recommended: set `CF_API_TOKEN` in your shell or `.env`. Token scopes should be limited to AI Gateway reads.
- Legacy: `CF_EMAIL` + `CF_API_KEY` (Global API Key) is supported but discouraged.
- The CLI exposes `--api-token` / `--email` / `--api-key` flags only via `config.yaml` indirection; we deliberately did not add direct command-line flags to keep credentials out of shell history.
- `redact_settings` returns `"***"` for any `SecretStr` field, used by `cf-aigw-analyzer config show` and `GET /api/v1/config`.

## Body content

`cf_aigw_analyzer.core.sanitizer.sanitize_log_metadata` is fail-closed. It keeps only a documented set of analytics-safe scalar fields plus numeric timing fields; unknown objects, body aliases, arbitrary payloads, paths, and stringified metadata are discarded before persistence. This protects against new Cloudflare field names such as camelCase body aliases being retained by default. The sanitized snapshot is stored in `log_raw.raw_json` only for local inspection. The `/response` endpoint is contacted solely to parse usage; its body is never written to disk.

Gateway configuration uses a separate recursive sanitizer before writing
`gateways.raw_json`. It preserves policy shape but redacts recognized credentials,
including camelCase and acronym forms such as `secretKey`, `privateKey`, `IDToken`,
`APIToken`, `AuthorizationHeader`, `secretAccessKey`, and `AWSSecretAccessKey`.
These rules apply to future writes and
re-synced gateways; existing SQLite snapshots are not rewritten automatically.

## Sharing exports

`cf-aigw-analyzer query` excludes `raw_json`, `account_id`, and `gateway_id` from JSON/CSV/table output by default. Use `--include-raw-json` / `--include-scope` only for local inspection. The dashboard's analytics payload returns recent event rows from `log_events` and does not include raw JSON.

## Auth model

| `control.auth_token`         | Loopback                           | Non-loopback (`0.0.0.0` etc.)                                  |
| ---------------------------- | ---------------------------------- | -------------------------------------------------------------- |
| empty (default)              | Open. Trusted local machine.       | Starts if configured, but is unsafe; do not expose this way.    |
| any string                   | All `/api/v1/*` and `/docs` need `Authorization: Bearer ...`. | Same as loopback case.                                          |

There is no per-route exemption. GET endpoints can leak summary statistics, sync state, and (redacted) configuration, so we apply uniform bearer auth.

## Logging & tracing

- The CLI uses Rich for human output and prints structured failure messages, never raw secrets.
- FastAPI access logs come from Uvicorn; redirecting them to a file is left to the operator.
- Bearer tokens are compared with constant-length string equality. There is no token rotation flow.

## Git hygiene

`/local/`, `/config.yaml`, `*.sqlite`, `*.sqlite-wal`, `*.sqlite-shm`, `web/dist/`, `web/node_modules/` are all gitignored. Run `git status --short --ignored` before pushing to confirm.

The `legacy/v0.2/` directory contains the old single-file Streamlit implementation as a reference. It must not be edited; treat its tests as historical.

## Threat model coverage

| Threat                                     | Mitigation                                                              |
| ------------------------------------------ | ----------------------------------------------------------------------- |
| Browser cross-site request to dashboard    | Loopback-only bind + optional bearer token.                             |
| Body content leak via SQLite               | Fail-closed log-field allow-list + `log_raw` separation; `/response` body not stored. |
| Credential exposure in process list        | No `--api-token` CLI flag; env vars only.                               |
| Credential exposure in config dump         | `redact_settings` enforces `"***"`.                                      |
| Replay of stale sync state                 | `sync_runs` records every invocation; `sync_state` only advances checkpoints and `sync_locks` prevent duplicate concurrent writers. |
| Cloudflare TLS interception                | `certifi`-backed default context, no plaintext fallback.                |

## Out of scope

- Multi-tenant access control. The analyzer assumes a single operator.
- Audit log tamper-evidence. The `sync_runs` table is best-effort; combine with filesystem snapshots if you need stronger guarantees.
- Network egress isolation. Use a containerized deployment plus an outbound firewall if you need to limit Cloudflare reachability.
