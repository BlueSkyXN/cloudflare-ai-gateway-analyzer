from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from cf_aigw_analyzer.database import AnalyzerDatabase
from cf_aigw_analyzer.usage import UsageFields


class DatabaseTest(unittest.TestCase):
    def test_upsert_logs_and_usage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "aigw.sqlite"
            with AnalyzerDatabase(db_path) as db:
                inserted = db.upsert_logs(
                    "account",
                    "gateway",
                    [
                        {
                            "id": "log-1",
                            "created_at": "2026-05-22T00:00:00Z",
                            "provider": "openai",
                            "model": "gpt-test",
                            "success": True,
                            "cached": False,
                            "status_code": 200,
                            "tokens_in": 0,
                            "tokens_out": None,
                            "duration": 123.4,
                            "timings": {"total": 2500, "latency": 400},
                            "request": {"messages": ["do not store"]},
                            "response": {"text": "do not store"},
                        }
                    ],
                )
                self.assertEqual(inserted, 1)

                self.assertEqual(db.usage_targets("account", "gateway"), ["log-1"])
                db.upsert_usage(
                    "account",
                    "gateway",
                    "log-1",
                    UsageFields(input_tokens=11, output_tokens=9, total_tokens=20, source="usage"),
                    fetch_status="parsed",
                    http_status_code=200,
                    error_message=None,
                )

                rows = db.query_logs("account", "gateway")
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0]["tokens_in"], 11)
                self.assertEqual(rows[0]["tokens_out"], 9)
                self.assertEqual(rows[0]["usage_total_tokens"], 20)
                self.assertEqual(rows[0]["duration_ms"], 123.4)
                self.assertEqual(rows[0]["generation_ms"], 2100.0)
                self.assertAlmostEqual(rows[0]["output_tps"], 9 / 2.1)
                self.assertNotIn("do not store", rows[0]["raw_json"])

                summary = db.summary("account", "gateway")
                self.assertEqual(summary["total_logs"], 1)
                self.assertEqual(summary["usage_parsed"], 1)

                table_names = {
                    row["name"]
                    for row in db.conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
                }
                self.assertIn("log_metrics", table_names)

    def test_retry_failed_usage_targets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "aigw.sqlite"
            with AnalyzerDatabase(db_path) as db:
                db.upsert_logs("account", "gateway", [{"id": "log-1"}, {"id": "log-2"}])
                db.upsert_usage(
                    "account",
                    "gateway",
                    "log-1",
                    UsageFields(),
                    fetch_status="failed",
                    http_status_code=500,
                    error_message="boom",
                )
                self.assertEqual(db.usage_targets("account", "gateway", retry_failed=False), ["log-2"])
                self.assertEqual(set(db.usage_targets("account", "gateway", retry_failed=True)), {"log-1", "log-2"})

                db.upsert_usage(
                    "account",
                    "gateway",
                    "log-2",
                    UsageFields(),
                    fetch_status="no_usage",
                    http_status_code=200,
                    error_message=None,
                )
                self.assertEqual(db.usage_targets("account", "gateway", retry_failed=False), [])
                self.assertEqual(db.usage_targets("account", "gateway", retry_failed=True), ["log-1"])

    def test_resolve_gateway_id_from_saved_gateway_name(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "aigw.sqlite"
            with AnalyzerDatabase(db_path) as db:
                db.upsert_gateways("account", [{"id": "gw-open-id", "name": "open"}])

                self.assertEqual(db.resolve_gateway_id("account", "open"), "gw-open-id")
                self.assertEqual(db.resolve_gateway_id("account", "gw-open-id"), "gw-open-id")

    def test_scope_summary_isolated_by_gateway(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "aigw.sqlite"
            with AnalyzerDatabase(db_path) as db:
                db.upsert_logs("account", "gateway-a", [{"id": "a"}])
                db.upsert_logs("account", "gateway-b", [{"id": "b"}])

                self.assertEqual(db.summary("account", "gateway-a")["total_logs"], 1)
                self.assertEqual(db.summary("account", "gateway-b")["total_logs"], 1)
                self.assertEqual(db.summary("account")["total_logs"], 2)


if __name__ == "__main__":
    unittest.main()
