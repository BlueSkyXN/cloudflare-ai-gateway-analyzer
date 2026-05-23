"""Per-log derived metrics: latency split, throughput, visible-output adjusted TPS."""

from __future__ import annotations

from typing import Any

from cf_aigw_analyzer.data.models import MetricsFields


def compute_log_metrics(log: dict[str, Any]) -> MetricsFields:
    """Derive a :class:`MetricsFields` from a Cloudflare log record.

    Heuristics:

    * ``total_ms`` = log.timings.total or log._total_ms or duration
    * ``latency_ms`` = log.timings.latency or log._latency_ms
    * ``generation_ms`` = log._generation_ms or (total - latency)
    * ``output_tps`` = output_tokens / (generation_ms / 1000) when both known
    * ``ms_per_output_token`` = generation_ms / output_tokens (when positive)
    * ``visible_output_tokens`` = output_tokens - reasoning_tokens (floor at 0)
    * ``visible_output_tps`` = visible_output_tokens / (generation_ms / 1000)
    """

    maybe_timings = log.get("timings")
    timings: dict[str, Any] = maybe_timings if isinstance(maybe_timings, dict) else {}
    duration_ms = _as_float(log.get("duration"))
    total_ms = _as_float(log.get("_total_ms")) or _as_float(timings.get("total")) or duration_ms
    latency_ms = _as_float(log.get("_latency_ms")) or _as_float(timings.get("latency"))

    generation_ms = _as_float(log.get("_generation_ms"))
    if generation_ms is None and total_ms is not None and latency_ms is not None:
        generation_ms = max(total_ms - latency_ms, 0.0)

    output_tokens = _as_float(log.get("tokens_out"))
    reasoning_tokens = _as_float(log.get("_reasoning_tokens"))
    output_tps = _as_float(log.get("_output_tps"))
    ms_per_output_token: float | None = None

    if generation_ms and output_tokens and output_tokens > 0:
        if output_tps is None:
            output_tps = output_tokens / (generation_ms / 1000.0)
        ms_per_output_token = generation_ms / output_tokens

    visible_output_tokens: int | None = None
    visible_output_tps: float | None = None
    if output_tokens is not None and reasoning_tokens is not None:
        visible_output_tokens = int(max(output_tokens - reasoning_tokens, 0))
        if generation_ms and generation_ms > 0:
            visible_output_tps = visible_output_tokens / (generation_ms / 1000.0)

    return MetricsFields(
        duration_ms=duration_ms,
        latency_ms=latency_ms,
        total_ms=total_ms,
        generation_ms=generation_ms,
        output_tps=output_tps,
        ms_per_output_token=ms_per_output_token,
        visible_output_tokens=visible_output_tokens,
        visible_output_tps=visible_output_tps,
    )


def _as_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
