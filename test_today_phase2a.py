"""Phase 2A tests for the enriched Today decision layer."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from zincintel.dashboard_v27 import (_market_card, _market_summary,
                                     _today_market_metrics)


ROOT = Path(__file__).resolve().parent


class TodayPhase2ATest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.snapshot = json.loads(
            (ROOT / "data" / "latest_snapshot.json").read_text(encoding="utf-8")
        )

    def test_lme_changes_use_same_source_3m_close_not_cash_headline(self) -> None:
        plan = self.snapshot["decision_book"]["markets"]["lme_zinc"]
        points = self.snapshot["market_research"]["close_series"]["chart_points"]
        metrics = _today_market_metrics(self.snapshot, "lme_zinc", plan)
        expected = (points[-1]["close"] / points[-2]["close"] - 1) * 100
        self.assertAlmostEqual(expected, metrics["change_1d"])
        self.assertEqual("LME 3M Close", metrics["change_basis"])
        self.assertEqual("20D Close", metrics["range_basis"])
        self.assertTrue(metrics["trend_since"])

    def test_full_ohlc_assets_use_observed_high_low_range(self) -> None:
        plan = self.snapshot["decision_book"]["markets"]["gold"]
        points = self.snapshot["market_research"]["cross_assets"]["gold"]["chart_points"][-20:]
        metrics = _today_market_metrics(self.snapshot, "gold", plan)
        self.assertEqual("20D H/L", metrics["range_basis"])
        self.assertAlmostEqual(min(item["low"] for item in points), metrics["support"])
        self.assertAlmostEqual(max(item["high"] for item in points), metrics["resistance"])

    def test_card_explains_changes_position_range_trigger_and_basis(self) -> None:
        card = _market_card(self.snapshot, "gold", "COMEX GOLD")
        for required in ("1D", "5D", "20D", "vs EMA20", "vs SMA60",
                         "20D H/L", "Next trigger", "今日重點", "Daily Close"):
            self.assertIn(required, card)
        self.assertNotIn("Actual fill", card)
        self.assertNotIn("contract_quantity", card)

    def test_lme_summary_keeps_curve_and_technical_direction_separate(self) -> None:
        plan = self.snapshot["decision_book"]["markets"]["lme_zinc"]
        metrics = _today_market_metrics(self.snapshot, "lme_zinc", plan)
        summary = _market_summary(self.snapshot, "lme_zinc", plan, metrics)
        self.assertIn("現貨", summary)
        self.assertIn("3M技術方向", summary)
        self.assertIn(plan["direction"], summary)

    def test_missing_treasury_does_not_invent_metrics(self) -> None:
        from copy import deepcopy
        snapshot = deepcopy(self.snapshot)
        snapshot.get('market_research', {}).pop('rates', None)
        card = _market_card(snapshot, "us_treasury", "US TREASURY 10Y", placeholder=True)
        self.assertIn("NO VERIFIED SERIES", card)
        self.assertIn("1D</span><b>N/A", card)
        self.assertIn("不判斷利率方向", card)
        self.assertNotIn("WAIT_FOR_TRIGGER", card)


if __name__ == "__main__":
    unittest.main()
