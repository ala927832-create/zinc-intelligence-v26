"""Synthetic-only regression tests; no licensed market rows or network access."""
import json
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from private_zscs import import_saved, outside_repo, parse_chart


def sample(day="20250102", prices="100,110,90,105"):
    return "var country='future';var code='zscs';globalData.push([1,2,'" + day + "'," + prices + ",0]);"


class PrivateZSCS(unittest.TestCase):
    def test_identity_and_ranges(self):
        for text in [sample().replace("zscs", "other"), sample(prices="100,90,80,105"),
                     sample(prices="100,NaN,90,105"), sample()+sample(), sample("20300101")]:
            with self.subTest(text=text), self.assertRaises(ValueError):
                parse_chart(text, today=date(2026, 10, 16))

    def test_flags_not_silent_deletion(self):
        rows = parse_chart(sample("20251225"), today=date(2026, 10, 16))
        self.assertEqual(rows[0]["flag"], "HOLIDAY_DATE_CONFLICT")

    def test_private_paths(self):
        root = Path(__file__).resolve().parent
        for path in [root / "data/x", root / "public/x"]:
            with self.assertRaises(ValueError):
                outside_repo(path)

    def test_preserve_revision_and_last_known_good(self):
        with TemporaryDirectory() as tmp:
            src = Path(tmp) / "source.html"
            dest = Path(tmp) / "private"
            src.write_text(sample())
            result = import_saved(src, dest, today=date(2026, 10, 16))
            self.assertEqual(result["rows"], 1)
            path = dest / "cnyes_zscs_private_archive.json"
            before = path.read_bytes()
            src.write_text("empty")
            with self.assertRaises(ValueError):
                import_saved(src, dest, today=date(2026, 10, 16))
            self.assertEqual(path.read_bytes(), before)
            src.write_text(sample(prices="100,110,90,106"))
            with self.assertRaises(ValueError):
                import_saved(src, dest, today=date(2026, 10, 16))
            self.assertEqual(path.read_bytes(), before)
            import_saved(src, dest, today=date(2026, 10, 16), accept_revisions=True)
            archive = json.loads(path.read_text())
            self.assertEqual(len(archive["revisions"]), 1)
            self.assertFalse(archive["strategy_enabled"])
            self.assertEqual(archive["usage_permission"], "UNCONFIRMED")
            chart = (dest / "index.html").read_text()
            self.assertNotIn("__ZSCS_ROWS__", chart)
            self.assertNotIn("fetch(", chart)
            self.assertIn("DEFINITION_UNVERIFIED", chart)


if __name__ == "__main__":
    unittest.main()
