import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from zincintel.dashboard_v27 import _primary_watch, _today_market_matrix, _today_posture, _zinc_context
from zincintel.research_pages import build_research_pages


class ResearchPagesTest(unittest.TestCase):
    def test_pages_and_hidden_health(self):
        plan = {"market":"Gold", "decision":"NO_TRADE", "direction":"NEUTRAL",
                "data_gate":"PASS", "regime_gate":"NEUTRAL", "strategy_gate":"BLOCKED",
                "trigger_gate":"BLOCKED", "execution_gate":"BLOCKED", "execution_check":{"status":"NOT_AVAILABLE"},
                "daily_plan":{}, "no_trade_reasons":["Mixed structure"],
                "evidence":[{"factor":"OI", "status":"NOT_INTEGRATED", "value":None}],
                "decision_audit":{f"{i}_question":"answer" for i in range(1,9)}}
        snapshot = {"run_date":"2026-10-13", "decision_book":{"markets":{"gold":plan}},
                    "market_research":{"cross_assets":{"gold":{"unit":"USD/oz"}}}, "market":{"data_health":{}}}
        original = deepcopy(snapshot)
        with tempfile.TemporaryDirectory() as folder, patch("zincintel.research_pages.PUBLIC_DIR", Path(folder)):
            paths = build_research_pages(snapshot)
            self.assertEqual({p.name for p in paths}, {"markets.html","radar.html","journal.html","system-status.html"})
            markets = (Path(folder)/"markets.html").read_text()
            self.assertIn("Actual R:R", markets)
            self.assertIn("Decision brief · eight required questions", markets)
            self.assertIn("Asset-specific evidence", markets)
            self.assertIn("Market comparison · first decision layer", markets)
            self.assertIn("class='market-detail'", markets)
            self.assertIn("1. 市場方向", markets)
            self.assertIn("8. No-Trade 理由", markets)
            self.assertIn("RESEARCH ONLY", markets)
            self.assertEqual(markets.count("Execution approval boundary"), 1)
            self.assertNotIn("Evidence availability %", markets)
            self.assertNotIn("name=\"account_equity\"", markets)
            indexable = "".join((Path(folder)/name).read_text() for name in ("markets.html","radar.html","journal.html"))
            self.assertNotIn("system-status.html", indexable)
            self.assertEqual(snapshot, original)

    def test_today_is_a_compact_decision_layer(self):
        plan = {
            "market": "LME Zinc Cash primary / 3M technical reference",
            "decision": "WAIT_FOR_TRIGGER", "direction": "STRONG_BEAR",
            "evidence_alignment": "PARTIAL", "as_of": "2026-10-13",
            "reference": {"cash": 3811.0},
            "daily_plan": {"setup_zone": [3760, 3810], "trigger_price": 3711,
                           "hard_stop": 3955, "t1": 3224, "t2": 2980},
            "no_trade_reasons": ["Trigger not confirmed."],
        }
        snapshot = {
            "run_date": "2026-10-13", "market_regime": "STRONG_BULL",
            "core_data_gate": {"status": "HEALTHY"},
            "decision_book": {"markets": {"lme_zinc": plan}},
        }
        html = (_today_posture(snapshot) + _today_market_matrix(snapshot)
                + _primary_watch(snapshot) + _zinc_context(snapshot))
        self.assertIn("TODAY'S MARKET POSTURE", html)
        self.assertIn("WAIT FOR TRIGGER", html)
        self.assertIn("CROSS-MARKET DECISION MATRIX", html)
        self.assertIn("PRIMARY WATCH", html)
        self.assertIn("Physical / procurement condition", html)
        self.assertIn("Close-only technical trend", html)
        self.assertNotIn("TECHNICAL DATA · METHODOLOGY", html)


if __name__ == "__main__":
    unittest.main()
