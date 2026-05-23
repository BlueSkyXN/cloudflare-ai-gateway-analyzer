from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

from cf_aigw_analyzer.dashboard import build_streamlit_command


class DashboardTest(unittest.TestCase):
    def test_build_streamlit_command_passes_scope_arguments(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "cloudflare.sqlite"
            command = build_streamlit_command(
                db_path,
                host="127.0.0.1",
                port=9999,
                account_id="account",
                gateway_name="open",
            )

        self.assertEqual(command[:3], [sys.executable, "-m", "streamlit"])
        self.assertIn("--server.address", command)
        self.assertIn("127.0.0.1", command)
        self.assertIn("--server.port", command)
        self.assertIn("9999", command)
        self.assertIn("--db", command)
        self.assertIn("--account-id", command)
        self.assertIn("account", command)
        self.assertIn("--gateway-name", command)
        self.assertIn("open", command)


if __name__ == "__main__":
    unittest.main()
