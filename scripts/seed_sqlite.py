"""Seed the SQLite database with synthetic logs for local development.

Usage::

    python scripts/seed_sqlite.py --db local/data/cloudflare_ai_gateway.sqlite \\
        --account acct-demo --gateway gw-demo --count 200

No Cloudflare API calls are made. All data is deterministic given the seed.
"""

from __future__ import annotations

import argparse
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if SRC.is_dir() and str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from cf_aigw_analyzer.data import AnalyzerDatabase, UsageFields  # noqa: E402
from cf_aigw_analyzer.models.enums import FetchStatus  # noqa: E402

MODELS = (
    ("openai", "gpt-4o-mini", "chat"),
    ("openai", "gpt-4o", "chat"),
    ("anthropic", "claude-3-5-sonnet", "chat"),
    ("anthropic", "claude-3-haiku", "chat"),
    ("google-ai-studio", "gemini-2.0-flash", "chat"),
    ("deepseek", "deepseek-chat", "chat"),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, help="SQLite path to seed")
    parser.add_argument("--account", default="acct-demo")
    parser.add_argument("--gateway", default="gw-demo")
    parser.add_argument("--count", type=int, default=200)
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    rng = random.Random(args.seed)
    db_path = Path(args.db).expanduser().resolve()
    db_path.parent.mkdir(parents=True, exist_ok=True)

    with AnalyzerDatabase(db_path) as db:
        db.gateways.upsert_many(
            args.account,
            [{"id": args.gateway, "name": args.gateway, "collect_logs": True}],
        )

        base_time = datetime(2026, 5, 22, 0, 0, 0, tzinfo=timezone.utc)
        logs: list[dict] = []
        for index in range(args.count):
            provider, model, model_type = rng.choice(MODELS)
            created = base_time + timedelta(minutes=index * 3 + rng.randint(0, 60))
            success = rng.random() > 0.05
            cached = rng.random() > 0.85
            tokens_in = rng.randint(20, 200_000)
            tokens_out = rng.randint(10, 4_000)
            total_ms = rng.uniform(120, 9_000)
            latency_ms = min(total_ms - 10, rng.uniform(40, 1_000))
            logs.append(
                {
                    "id": f"log-{index:05d}",
                    "created_at": created.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "provider": provider,
                    "model": model,
                    "model_type": model_type,
                    "success": success,
                    "cached": cached,
                    "status_code": 200 if success else rng.choice([400, 500, 502, 504]),
                    "cost": round(tokens_in * 1e-7 + tokens_out * 5e-7, 6),
                    "tokens_in": tokens_in,
                    "tokens_out": tokens_out,
                    "duration": total_ms,
                    "timings": {"total": total_ms, "latency": latency_ms},
                }
            )

        db.logs.upsert_many(args.account, args.gateway, logs)

        for log in logs:
            if not log["success"]:
                db.logs.upsert_usage(
                    args.account,
                    args.gateway,
                    log["id"],
                    UsageFields(),
                    FetchStatus.NO_USAGE,
                    404,
                    "response unavailable",
                )
                continue
            reasoning = rng.randint(0, max(1, log["tokens_out"] // 4))
            usage = UsageFields(
                input_tokens=log["tokens_in"],
                output_tokens=log["tokens_out"],
                total_tokens=log["tokens_in"] + log["tokens_out"],
                cached_tokens=rng.randint(0, log["tokens_in"] // 4),
                reasoning_tokens=reasoning,
                source="usage",
            )
            db.logs.upsert_usage(
                args.account,
                args.gateway,
                log["id"],
                usage,
                FetchStatus.PARSED,
                200,
                None,
            )

        db.sync_runs.record(
            args.account,
            args.gateway,
            mode="seed",
            params={"count": args.count, "seed": args.seed},
            logs_count=args.count,
            usage_fetched=args.count,
            usage_parsed=sum(1 for log in logs if log["success"]),
            usage_no_usage=sum(1 for log in logs if not log["success"]),
        )

    print(f"seeded {args.count} logs into {db_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
