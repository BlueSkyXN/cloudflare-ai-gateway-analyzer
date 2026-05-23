from __future__ import annotations

import unittest

from cf_aigw_analyzer.output import sanitize_output_rows


class OutputTest(unittest.TestCase):
    def test_sanitize_output_rows_excludes_private_fields_by_default(self) -> None:
        rows = [
            {
                "account_id": "account",
                "gateway_id": "gateway",
                "log_id": "log-1",
                "raw_json": "{}",
            }
        ]

        sanitized = sanitize_output_rows(rows)

        self.assertEqual(sanitized, [{"log_id": "log-1"}])

    def test_sanitize_output_rows_can_include_private_fields(self) -> None:
        rows = [
            {
                "account_id": "account",
                "gateway_id": "gateway",
                "log_id": "log-1",
                "raw_json": "{}",
            }
        ]

        sanitized = sanitize_output_rows(rows, include_raw_json=True, include_scope=True)

        self.assertEqual(sanitized, rows)


if __name__ == "__main__":
    unittest.main()
