"""SQLite schema definition for the analyzer.

Schema version 5 layout (single fact table + raw JSON side table):

* ``gateways``       — gateway metadata (1 row per gateway)
* ``log_events``     — one analytics-ready row per Cloudflare AI Gateway log
* ``log_raw``        — sanitized raw_json (1:1 with log_events, queried on demand)
* ``sync_runs``      — sync run audit log
* ``sync_state``     — per-scope incremental sync checkpoint
* ``sync_locks``     — per-scope writer lock to avoid duplicate concurrent sync
* ``migrations``     — applied schema version history

``provider`` is the channel dimension. The schema intentionally avoids a second
``channel`` alias so filtering and grouping have a single source of truth.
"""

from __future__ import annotations

SCHEMA_VERSION = 5

PRAGMAS = (
    "PRAGMA foreign_keys=ON",
    "PRAGMA journal_mode=WAL",
    "PRAGMA synchronous=NORMAL",
    "PRAGMA busy_timeout=5000",
    "PRAGMA temp_store=MEMORY",
    "PRAGMA mmap_size=268435456",
)

DDL = """
CREATE TABLE IF NOT EXISTS migrations (
    version     INTEGER PRIMARY KEY,
    applied_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS gateways (
    account_id   TEXT NOT NULL,
    gateway_id   TEXT NOT NULL,
    name         TEXT,
    collect_logs INTEGER,
    raw_json     TEXT NOT NULL,
    fetched_at   TEXT NOT NULL,
    PRIMARY KEY (account_id, gateway_id)
);

CREATE TABLE IF NOT EXISTS log_events (
    account_id             TEXT NOT NULL,
    gateway_id             TEXT NOT NULL,
    log_id                 TEXT NOT NULL,
    created_at             TEXT,
    provider               TEXT,
    model                  TEXT,
    model_type             TEXT,
    success                INTEGER,
    cached                 INTEGER,
    status_code            INTEGER,
    cost_usd               REAL,
    input_tokens           INTEGER,
    output_tokens          INTEGER,
    total_tokens           INTEGER,
    cached_tokens          INTEGER,
    reasoning_tokens       INTEGER,
    cache_write_tokens     INTEGER,
    duration_ms            REAL,
    latency_ms             REAL,
    total_ms               REAL,
    generation_ms          REAL,
    output_tps             REAL,
    ms_per_output_token    REAL,
    visible_output_tokens  INTEGER,
    visible_output_tps     REAL,
    usage_source           TEXT,
    usage_fetch_status     TEXT CHECK (
        usage_fetch_status IS NULL OR usage_fetch_status IN ('parsed','no_usage','failed')
    ),
    usage_http_status_code INTEGER,
    usage_error_message    TEXT,
    usage_fetched_at       TEXT,
    synced_at              TEXT NOT NULL,
    updated_at             TEXT NOT NULL,
    PRIMARY KEY (account_id, gateway_id, log_id)
);

CREATE TABLE IF NOT EXISTS log_raw (
    account_id   TEXT NOT NULL,
    gateway_id   TEXT NOT NULL,
    log_id       TEXT NOT NULL,
    raw_json     TEXT NOT NULL,
    updated_at   TEXT NOT NULL,
    PRIMARY KEY (account_id, gateway_id, log_id),
    FOREIGN KEY (account_id, gateway_id, log_id)
        REFERENCES log_events(account_id, gateway_id, log_id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS sync_runs (
    run_id           INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id       TEXT,
    gateway_id       TEXT,
    mode             TEXT NOT NULL,
    params_json      TEXT,
    logs_count       INTEGER NOT NULL DEFAULT 0,
    usage_fetched    INTEGER NOT NULL DEFAULT 0,
    usage_parsed     INTEGER NOT NULL DEFAULT 0,
    usage_no_usage   INTEGER NOT NULL DEFAULT 0,
    usage_failed     INTEGER NOT NULL DEFAULT 0,
    started_at       TEXT NOT NULL,
    finished_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sync_state (
    account_id           TEXT NOT NULL,
    gateway_id           TEXT NOT NULL,
    mode                 TEXT NOT NULL,
    last_success_at      TEXT,
    last_seen_created_at TEXT,
    last_seen_log_id     TEXT,
    updated_at           TEXT NOT NULL,
    PRIMARY KEY (account_id, gateway_id, mode)
);

CREATE TABLE IF NOT EXISTS sync_locks (
    account_id  TEXT NOT NULL,
    gateway_id  TEXT NOT NULL,
    mode        TEXT NOT NULL,
    owner       TEXT NOT NULL,
    acquired_at TEXT NOT NULL,
    expires_at  TEXT NOT NULL,
    PRIMARY KEY (account_id, gateway_id, mode)
);

CREATE INDEX IF NOT EXISTS idx_log_events_scope_time
    ON log_events(account_id, gateway_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_log_events_provider_model
    ON log_events(account_id, gateway_id, provider, model);
CREATE INDEX IF NOT EXISTS idx_log_events_global_time
    ON log_events(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_log_events_usage_status
    ON log_events(account_id, gateway_id, usage_fetch_status);
CREATE INDEX IF NOT EXISTS idx_sync_runs_scope_time
    ON sync_runs(account_id, gateway_id, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_sync_locks_expires
    ON sync_locks(expires_at);
"""
