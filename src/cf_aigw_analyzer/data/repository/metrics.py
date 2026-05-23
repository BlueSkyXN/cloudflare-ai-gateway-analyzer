"""Metrics repository: recompute usage-dependent derived metrics."""

from __future__ import annotations

import sqlite3

from cf_aigw_analyzer.data.models import UsageFields
from cf_aigw_analyzer.utils.time import utc_now


class MetricsRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def refresh_usage_dependent(
        self,
        account_id: str,
        gateway_id: str,
        log_id: str,
        usage: UsageFields,
    ) -> None:
        """Recompute ``output_tps`` / ``visible_*`` columns after usage upsert."""

        row = self.conn.execute(
            """
            SELECT l.tokens_out, m.generation_ms
            FROM logs l
            LEFT JOIN log_metrics m
              ON l.account_id = m.account_id
             AND l.gateway_id = m.gateway_id
             AND l.log_id = m.log_id
            WHERE l.account_id=? AND l.gateway_id=? AND l.log_id=?
            """,
            (account_id, gateway_id, log_id),
        ).fetchone()
        if not row:
            return

        tokens_out_raw = row["tokens_out"]
        if tokens_out_raw in (None, 0):
            tokens_out_raw = usage.output_tokens
        output_tokens = float(tokens_out_raw) if tokens_out_raw is not None else None

        generation_ms = float(row["generation_ms"]) if row["generation_ms"] is not None else None
        reasoning_tokens = (
            float(usage.reasoning_tokens) if usage.reasoning_tokens is not None else None
        )

        output_tps: float | None = None
        ms_per_output_token: float | None = None
        if output_tokens and generation_ms and generation_ms > 0:
            output_tps = output_tokens / (generation_ms / 1000.0)
            ms_per_output_token = generation_ms / output_tokens

        visible_output_tokens: int | None = None
        visible_output_tps: float | None = None
        if output_tokens is not None and reasoning_tokens is not None:
            visible_output_tokens = int(max(output_tokens - reasoning_tokens, 0))
            if generation_ms and generation_ms > 0:
                visible_output_tps = visible_output_tokens / (generation_ms / 1000.0)

        self.conn.execute(
            """
            UPDATE log_metrics
            SET
                output_tps            = COALESCE(?, output_tps),
                ms_per_output_token   = COALESCE(?, ms_per_output_token),
                visible_output_tokens = COALESCE(?, visible_output_tokens),
                visible_output_tps    = COALESCE(?, visible_output_tps),
                computed_at           = ?
            WHERE account_id=? AND gateway_id=? AND log_id=?
            """,
            (
                output_tps,
                ms_per_output_token,
                visible_output_tokens,
                visible_output_tps,
                utc_now(),
                account_id,
                gateway_id,
                log_id,
            ),
        )
