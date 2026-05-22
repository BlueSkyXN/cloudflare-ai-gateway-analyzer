from __future__ import annotations

import unittest

from cf_aigw_analyzer.paths import DEFAULT_DB_FILENAME, resolve_db_path, safe_filename_part


class PathTest(unittest.TestCase):
    def test_safe_filename_part(self) -> None:
        self.assertEqual(safe_filename_part("gw/demo:one"), "gw_demo_one")
        self.assertEqual(safe_filename_part(""), "default")

    def test_default_db_is_single_file_for_all_gateways(self) -> None:
        self.assertEqual(resolve_db_path(data_dir="/tmp/aigw", gateway_id="gateway-a").name, DEFAULT_DB_FILENAME)
        self.assertEqual(
            resolve_db_path(data_dir="/tmp/aigw", gateway_id="gateway-a"),
            resolve_db_path(data_dir="/tmp/aigw", gateway_id="gateway-b"),
        )


if __name__ == "__main__":
    unittest.main()
