import unittest

from zincintel.line_notify import build_alert_message, build_daily_message


class LineNotifyTest(unittest.TestCase):
    def setUp(self):
        self.snapshot = {"run_date":"2026-10-13", "market_research":{
            "close_series":{"latest_close":3900}, "shfe_zinc":{"latest_close":24000},
            "cross_assets":{"gold":{"latest_session":{"close":4100},"unit":"USD/oz"},
                            "usdjpy":{"latest_session":{"close":151},"unit":"JPY per USD"},
                            "dxy":{"latest_session":{"close":101},"unit":"index"}}},
            "decision_book":{"markets":{k:{"market":k,"direction":"NEUTRAL","decision":"NO_TRADE",
                "no_trade_reasons":["No live quote"]} for k in ("lme_zinc","shfe_zinc","gold","usdjpy","dxy")}}}

    def test_daily_has_all_markets_and_execution_rule(self):
        text = build_daily_message(self.snapshot)
        for marker in ("LME Zn", "SHFE Zn", "Gold", "USD/JPY", "DXY", "Bid/Ask"):
            self.assertIn(marker, text)
        self.assertNotIn("inventory_t", text)

    def test_alert_is_not_execution_confirmation(self):
        text = build_alert_message(self.snapshot, ["gold"])
        self.assertIn("不是成交確認", text)


if __name__ == "__main__":
    unittest.main()
