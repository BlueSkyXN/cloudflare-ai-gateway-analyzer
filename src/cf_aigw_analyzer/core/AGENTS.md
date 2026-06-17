# src/cf_aigw_analyzer/core navigation card

Core Cloudflare integration layer: HTTP client, API wrapper, sanitizer, usage parser, metrics helpers, and sync engine.
Read this card before editing Cloudflare requests, retry behavior, sync orchestration, response usage parsing, or sanitizer behavior.
Key files: `http_client.py`, `cloudflare.py`, `sync_engine.py`, `usage_parser.py`, `sanitizer.py`, and `metrics.py`.

## Local invariants

- All Cloudflare HTTP traffic goes through `HttpClient`; do not add ad-hoc `urllib`, `requests`, shell calls, or separate `httpx` clients.
- `/response` payloads are parsed for usage only and are not persisted.
- `sanitize_log_metadata` must run before log metadata is stored through repositories.
- `sanitize_gateway_metadata` must run before gateway configuration metadata is stored through repositories; preserve policy/config shape while redacting secret-bearing fields.
- Usage concurrency stays bounded by configured `usage_workers` / `workers` in `1..64`.
- Sync operations must remain restartable and idempotent through repository upserts, `sync_state`, and per-scope locks.

## Local rules

- Parser changes should add provider-shape fixtures in `tests/unit/test_usage_parser.py`.
- Sync changes should keep metadata sync and usage sync separable; `--with-usage` is orchestration, not a new storage path.
- Treat Cloudflare API behavior as external and unstable; cover retry/error parsing with mocked transports, not live tests.

## Do not

- Do not persist prompts, messages, request bodies, response bodies, or other denied content.
- Do not persist gateway configuration secrets such as authorization headers, tokens, API keys, or cookies.
- Do not bypass repository APIs for writes.
- Do not make live Cloudflare calls from tests.
- Do not replace async sync orchestration with threadpool sync.

## Validation

- Parser: `PYTHONPATH=src python3 -m pytest tests/unit/test_usage_parser.py`
- Sanitizer: `PYTHONPATH=src python3 -m pytest tests/unit/test_sanitizer.py`
- Sync engine: `PYTHONPATH=src python3 -m pytest tests/integration/test_sync_engine.py`
