from datetime import UTC, datetime
import unittest

from deepagents_logs.core.layout import iso_timestamp


class LayoutTests(unittest.TestCase):
    def test_iso_timestamp_uses_filename_safe_z_suffix(self):
        timestamp = iso_timestamp(datetime(2026, 4, 15, 9, 50, 8, 705000, tzinfo=UTC))
        self.assertEqual(timestamp, "2026-04-15T09-50-08.705Z")


if __name__ == "__main__":
    unittest.main()
