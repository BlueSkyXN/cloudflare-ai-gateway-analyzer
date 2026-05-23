"""SQLite schema definition for the analyzer.

Schema version 3 layout (v0.3.0 refactor):

* ``gateways``       — gateway metadata (1 row per gateway)
* ``logs``           — sanitized log metadata (no raw_json)
* ``logs_raw``       — sanitized raw_json (1:1 with logs, queried on demand)
* ``log_usage``      — parsed token usage (1:1 with logs)
* ``log_metrics``    — derived per-log metrics (1:1 with logs)
* ``sync_runs``      — sync run audit log
* ``migrations``     — applied schema version history

All log-keyed tables share ``(account_id, gateway_id, log_id)`` so scope is
explicit at every read.
"""

from __future__ import annotations

SCHEMA_VERSION = 3

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

CREATE TABLE IF NOT EXISTS logs (
    account_id   TEXT NOT NULL,
    gateway_id   TEXT NOT NULL,
    log_id       TEXT NOT NULL,
    created_at   TEXT,
    provider     TEXT,
    model        TEXT,
    model_type   TEXT,
    success      INTEGER,
    cached       INTEGER,
    status_code  INTEGER,
    cost_usd     REAL,
    tokens_in    INTEGER,
    tokens_out   INTEGER,
    synced_at    TEXT NOT NULL,
    PRIMARY KEY (account_id, gateway_id, log_id)
);

CREATE TABLE IF NOT EXISTS logs_raw (
    account_id   TEXT NOT NULL,
    gateway_id   TEXT NOT NULL,
    log_id       TEXT NOT NULL,
    raw_json     TEXT NOT NULL,
    updated_at   TEXT NOT NULL,
    PRIMARY KEY (account_id, gateway_id, log_id),
    FOREIGN KEY (account_id, gateway_id, log_id)
        REFERENCES logs(account_id, gateway_id, log_id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS log_metrics (
    account_id            TEXT NOT NULL,
    gateway_id            TEXT NOT NULL,
    log_id                TEXT NOT NULL,
    duration_ms           REAL,
    latency_ms            REAL,
    total_ms              REAL,
    generation_ms         REAL,
    output_tps            REAL,
    ms_per_output_token   REAL,
    visible_output_tokens INTEGER,
    visible_output_tps    REAL,
    computed_at           TEXT NOT NULL,
    PRIMARY KEY (account_id, gateway_id, log_id),
    FOREIGN KEY (account_id, gateway_id, log_id)
        REFERENCES logs(account_id, gateway_id, log_id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS log_usage (
    account_id         TEXT NOT NULL,
    gateway_id         TEXT NOT NULL,
    log_id             TEXT NOT NULL,
    input_tokens       INTEGER,
    output_tokens      INTEGER,
    total_tokens       INTEGER,
    cached_tokens      INTEGER,
    reasoning_tokens   INTEGER,
    cache_write_tokens INTEGER,
    source             TEXT,
    fetch_status       TEXT NOT NULL CHECK (fetch_status IN ('parsed','no_usage','failed')),
    http_status_code   INTEGER,
    error_message      TEXT,
    fetched_at         TEXT NOT NULL,
    updated_at         TEXT NOT NULL,
    PRIMARY KEY (account_id, gateway_id, log_id),
    FOREIGN KEY (account_id, gateway_id, log_id)
        REFERENCES logs(account_id, gateway_id, log_id)
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

CREATE INDEX IF NOT EXISTS idx_logs_scope_time
    ON logs(account_id, gateway_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_logs_provider_model
    ON logs(account_id, gateway_id, provider, model);
CREATE INDEX IF NOT EXISTS idx_logs_global_time
    ON logs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_usage_scope_status
    ON log_usage(account_id, gateway_id, fetch_status);
CREATE INDEX IF NOT EXISTS idx_metrics_scope
    ON log_metrics(account_id, gateway_id);
CREATE INDEX IF NOT EXISTS idx_sync_runs_scope_time
    ON sync_runs(account_id, gateway_id, started_at DESC);
"""
