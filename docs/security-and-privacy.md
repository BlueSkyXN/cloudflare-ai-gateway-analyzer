# Security and Privacy

This project is intended to be safe for a public repository, but local runtime data is private by default.

## Do Not Commit

Never commit:

- `local/`
- SQLite databases and WAL/SHM files
- `.env` files
- Cloudflare API tokens
- Cloudflare Global API keys
- real account IDs if they identify a private account
- private endpoint URLs
- customer data
- request or response body content
- generated exports containing sensitive operational data

The `.gitignore` file excludes the expected local runtime paths and SQLite files. Always check `git status --short --ignored` before committing.

## Credential Handling

Use environment variables at runtime:

```bash
export CF_API_TOKEN="your-token"
```

Do not add credentials to source files or documentation. CLI credential flags exist for runtime compatibility, but environment variables are safer because command-line flags can appear in shell history or process listings. When sharing command transcripts, redact tokens, keys, account IDs, private gateway names, and local machine paths if needed.

## Request and Response Bodies

The `logs` table stores sanitized metadata only. The sanitizer removes request and response body-like keys recursively before writing `raw_json`.

The `/response` endpoint is called only to parse token usage. Response bodies are not persisted.

`query` removes `raw_json`, `account_id`, and `gateway_id` from output by default. `--include-raw-json` and `--include-scope` are private-inspection flags.

## Local Database Sensitivity

The SQLite database can still reveal operational details:

- account and gateway identifiers
- model names
- provider names
- timestamps
- costs
- token counts
- cache and reasoning token counts
- success and status-code patterns

Treat `local/data/cloudflare_ai_gateway.sqlite` as private runtime data.

## Local Dashboard

The dashboard is intended for local inspection only:

- It reads SQLite locally and does not call Cloudflare.
- It binds to `127.0.0.1` by default.
- It can display model names, gateway names, timestamps, token counts, costs, and timing patterns.
- Do not expose it on a public interface or share screenshots without reviewing the visible data.

## License Boundary

No open-source license has been selected yet. Until a license file is added, the repository contents are visible source code but no reuse license is granted.
