import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from zincintel.research_pages import build_research_pages


class ResearchPagesTest(unittest.TestCase):
    def test_pages_and_hidden_health(self):
        plan = {"market":"Gold", "decision":"NO_TRADE", "direction":"NEUTRAL",
                "data_gate":"PASS", "regime_gate":"NEUTRAL", "strategy_gate":"BLOCKED",
                "trigger_gate":"BLOCKED", "execution_gate":"BLOCKED", "execution_check":{"status":"NOT_AVAILABLE"},
                "daily_plan":{}, "no_trade_reasons":["Mixed structure"]}
        snapshot = {"run_date":"2026-10-13", "decision_book":{"markets":{"gold":plan}},
                    "market_research":{"cross_assets":{"gold":{"unit":"USD/oz"}}}, "market":{"data_health":{}}}
        with tempfile.TemporaryDirectory() as folder, patch("zincintel.research_pages.PUBLIC_DIR", Path(folder)):
            paths = build_research_pages(snapshot)
            self.assertEqual({p.name for p in paths}, {"markets.html","radar.html","journal.html","system-status.html"})
            markets = (Path(folder)/"markets.html").read_text()
            self.assertIn("Actual R:R", markets)
            indexable = "".join((Path(folder)/name).read_text() for name in ("markets.html","radar.html","journal.html"))
            self.assertNotIn("system-status.html", indexable)


if __name__ == "__main__":
    unittest.main()
