# Data Model

The default SQLite database path is:

```text
local/data/cloudflare_ai_gateway.sqlite
```

All accounts and gateways share this single database. The primary log identity is:

```text
(account_id, gateway_id, log_id)
```

## Tables

### `gateways`

Stores gateway metadata discovered from Cloudflare.

Primary key:

```text
(account_id, gateway_id)
```

Important columns:

- `account_id`
- `gateway_id`
- `name`
- `collect_logs`
- `raw_json`
- `fetched_at`

### `logs`

Stores one row per Cloudflare AI Gateway log metadata record.

Primary key:

```text
(account_id, gateway_id, log_id)
```

This table stores metadata fields such as:

- `created_at`
- `provider`
- `model`
- `model_type`
- `success`
- `cached`
- `status_code`
- `cost_usd`
- `tokens_in`
- `tokens_out`
- `raw_json`
- `synced_at`

`raw_json` is sanitized before storage. Request and response body-like keys are removed recursively.

### `log_usage`

Stores parsed usage data in a 1:1 relationship with `logs`.

Primary key:

```text
(account_id, gateway_id, log_id)
```

Important columns:

- `input_tokens`
- `output_tokens`
- `total_tokens`
- `cached_tokens`
- `reasoning_tokens`
- `cache_write_tokens`
- `source`
- `fetch_status`
- `http_status_code`
- `error_message`

`fetch_status` values:

- `parsed`: usage fields were found.
- `no_usage`: response was available but no usable usage object was found, or Cloudflare returned response-body-unavailable semantics.
- `failed`: the fetch failed in a way worth retrying.

### `log_metrics`

Stores derived per-log metrics in a 1:1 relationship with `logs`.

Important columns:

- `duration_ms`
- `latency_ms`
- `total_ms`
- `generation_ms`
- `output_tps`
- `ms_per_output_token`
- `visible_output_tokens`
- `visible_output_tps`
- `computed_at`

### `sync_runs`

Stores sync run summaries for operational visibility.

## Privacy Boundary

The database is local runtime data. It may contain account IDs, gateway IDs, model usage, costs, token counts, timing data, and other operational metadata. Keep it under `local/` and do not commit or upload it.

