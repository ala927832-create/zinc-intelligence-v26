import csv
from datetime import date, timedelta
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from private_research import import_file, load, normalize, page, private_dir


class PrivateResearchTest(unittest.TestCase):
    def setUp(self):
        self.row = dict(date=(date.today() - timedelta(days=2)).isoformat(), open="4000", high="4050",
                        low="3950", close="4020", market="LME", contract="ZINC_3M", currency="USD", source="verified_example")

    def test_data_quality_and_identity(self):
        self.assertEqual(normalize([self.row])[0]["close"], "4020")
        for changes in ({"high": "3999"}, {"low": "4021"}, {"date": date.today().isoformat()},
                        {"contract": "OTHER"}, {"source": ""}, {"open": "NaN"}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                normalize([{**self.row, **changes}])

    def test_archive_idempotent_and_conflict_safe(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            incoming, archive = base / "incoming.csv", base / "private" / "lme_zinc_3m_ohlc.csv"
            with incoming.open("w", newline="") as file:
                writer = csv.DictWriter(file, fieldnames=self.row.keys())
                writer.writeheader(); writer.writerow(self.row)
            self.assertEqual(import_file(incoming, archive), 1)
            self.assertEqual(import_file(incoming, archive), 1)
            self.assertEqual(len(load(archive)), 1)
            with incoming.open("w", newline="") as file:
                writer = csv.DictWriter(file, fieldnames=self.row.keys())
                writer.writeheader(); writer.writerow({**self.row, "close": "4010"})
            with self.assertRaisesRegex(ValueError, "Conflicting"):
                import_file(incoming, archive)
            self.assertEqual(load(archive)[0]["close"], "4020")

    def test_private_path_and_ui(self):
        with patch.dict(os.environ, {"ZINC_PRIVATE_DIR": str(Path(__file__).parent / "data" )}):
            with self.assertRaises(ValueError):
                private_dir()
        self.assertIn("MA20", page())
        self.assertIn("MA50", page())
        self.assertIn("較早", page())


if __name__ == "__main__":
    unittest.main()
