from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from cf_aigw_analyzer.analytics import (
    AnalyticsFilters,
    build_context_buckets,
    build_insights,
    build_model_stats,
    build_recent_events,
    build_summary,
    build_timeseries,
    fetch_rows,
    open_readonly_database,
)
from cf_aigw_analyzer.database import AnalyzerDatabase
from cf_aigw_analyzer.usage import UsageFields


class AnalyticsTest(unittest.TestCase):
    def test_builds_dashboard_aggregates_without_raw_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "aigw.sqlite"
            with AnalyzerDatabase(db_path) as db:
                db.upsert_logs(
                    "account",
                    "gateway",
                    [
                        {
                            "id": "log-1",
                            "created_at": "2026-05-22T00:10:00Z",
                            "provider": "provider-a",
                            "model": "model-a",
                            "success": True,
                            "tokens_in": 100,
                            "tokens_out": 10,
                            "timings": {"total": 1000, "latency": 300},
                        },
                        {
                            "id": "log-2",
                            "created_at": "2026-05-22T00:20:00Z",
                            "provider": "provider-a",
                            "model": "model-b",
                            "success": False,
                            "tokens_in": 120_000,
                            "tokens_out": 20,
                            "timings": {"total": 4000, "latency": 1000},
                        },
                    ],
                )
                db.upsert_usage(
                    "account",
                    "gateway",
                    "log-1",
                    UsageFields(input_tokens=100, output_tokens=10, total_tokens=110, cached_tokens=50),
                    "parsed",
                    200,
                    None,
                )
                db.upsert_usage(
                    "account",
                    "gateway",
                    "log-2",
                    UsageFields(input_tokens=120_000, output_tokens=20, total_tokens=120_020),
                    "parsed",
                    200,
                    None,
                )

            with open_readonly_database(db_path) as conn:
                rows = fetch_rows(conn, AnalyticsFilters(account_id="account", gateway_id="gateway"))

            summary = build_summary(rows)
            self.assertEqual(summary["requests"], 2)
            self.assertEqual(summary["failed_count"], 1)
            self.assertEqual(summary["total_tokens"], 120_130)
            self.assertAlmostEqual(summary["cache_ratio"], 0.00041631973355509367)

            model_stats = build_model_stats(rows)
            self.assertEqual([item["model"] for item in model_stats], ["model-a", "model-b"])

            context_buckets = build_context_buckets(rows)
            self.assertEqual([item["context_bucket"] for item in context_buckets], ["<1k", "100k-500k"])

            timeseries = build_timeseries(rows)
            self.assertEqual(timeseries[0]["hour"], "2026-05-22T00:00:00Z")
            self.assertEqual(timeseries[0]["requests"], 2)

            events = build_recent_events(rows)
            self.assertEqual(events[0]["log_id"], "log-2")
            self.assertNotIn("raw_json", events[0])
            self.assertNotIn("account_id", events[0])

            self.assertTrue(build_insights(rows))


if __name__ == "__main__":
    unittest.main()
