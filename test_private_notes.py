from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from private_notes import add_note, normalize_note, read_notes


class NotesTest(unittest.TestCase):
    def setUp(self):
        self.note = {"chart_url": "https://example.org/chart", "market": "Source-labelled market",
                     "contract": "Source-labelled contract", "observed_on": date.today().isoformat(),
                     "last_trading_day": date.today().isoformat(), "moving_averages": "MA5/MA20/MA50",
                     "verification": "待核對", "observations": "Observe only", "attachment": ""}

    def test_note_is_independent_from_ohlc(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "research_notes.jsonl"
            self.assertEqual(add_note(path, self.note)["verification"], "待核對")
            self.assertEqual(read_notes(path)[0]["chart_url"], self.note["chart_url"])
            self.assertFalse((Path(tmp) / "lme_zinc_3m_ohlc.csv").exists())

    def test_reject_untrusted_links_and_attachments(self):
        for changes in ({"chart_url": "http://example.org"}, {"attachment": "chart.png"},
                        {"attachment": "../chart.png", "attachment_allowed": True},
                        {"verification": "other"}, {"moving_averages": "MA999"}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                normalize_note({**self.note, **changes})
        self.assertEqual(normalize_note({**self.note, "attachment": "chart.png", "attachment_allowed": True})["attachment"], "chart.png")


if __name__ == "__main__":
    unittest.main()
