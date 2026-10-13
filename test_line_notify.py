import unittest

from zincintel.line_notify import (
    alert_market_keys, build_alert_message, build_daily_message,
    notification_plan, research_session_signature,
)


class LineNotifyTest(unittest.TestCase):
    def setUp(self):
        self.snapshot = {"run_date":"2026-10-13", "market_research":{
            "close_series":{"latest_close":3900,"as_of":"2026-10-12"},
            "shfe_zinc":{"latest_close":24000,"as_of":"2026-10-13"},
            "cross_assets":{"gold":{"latest_session":{"close":4100},"unit":"USD/oz","as_of":"2026-10-12"},
                            "usdjpy":{"latest_session":{"close":151},"unit":"JPY per USD","as_of":"2026-10-12"},
                            "dxy":{"latest_session":{"close":101},"unit":"index","as_of":"2026-10-12"}}},
            "decision_book":{"markets":{k:{"market":k,"direction":"NEUTRAL","decision":"NO_TRADE",
                "data_gate":"PASS","trigger_gate":"NOT_TRIGGERED",
                "no_trade_reasons":["No live quote"]} for k in ("lme_zinc","shfe_zinc","gold","usdjpy","dxy")}}}

    def test_daily_has_all_markets_and_execution_rule(self):
        text = build_daily_message(self.snapshot)
        for marker in ("LME Zn", "SHFE Zn", "Gold", "USD/JPY", "DXY", "Bid/Ask"):
            self.assertIn(marker, text)
        self.assertNotIn("inventory_t", text)

    def test_alert_is_not_execution_confirmation(self):
        text = build_alert_message(self.snapshot, ["gold"])
        self.assertIn("不是成交確認", text)

    def test_daily_mode_suppresses_duplicate_market_session(self):
        previous = {**self.snapshot, "run_date":"2026-10-12"}
        self.assertEqual(research_session_signature(self.snapshot), research_session_signature(previous))
        self.assertEqual(notification_plan(self.snapshot, previous, "daily"), {"daily":False,"alerts":[]})

    def test_daily_mode_sends_when_a_validated_session_advances(self):
        previous = {"market_research":{"close_series":{"as_of":"2026-10-09"}}}
        plan = notification_plan(self.snapshot, previous, "daily")
        self.assertTrue(plan["daily"])
        self.assertEqual(plan["alerts"], [])

    def test_alert_only_sends_new_direction_or_trigger(self):
        previous = {"decision_book":{"markets":{
            k:{"direction":"NEUTRAL","data_gate":"PASS","trigger_gate":"NOT_TRIGGERED"}
            for k in ("lme_zinc","shfe_zinc","gold","usdjpy","dxy")}}}
        self.snapshot["decision_book"]["markets"]["gold"]["direction"] = "BULL"
        self.snapshot["decision_book"]["markets"]["dxy"]["trigger_gate"] = "TRIGGERED"
        plan = notification_plan(self.snapshot, previous, "alert_only")
        self.assertFalse(plan["daily"])
        self.assertEqual(set(plan["alerts"]), {"gold", "dxy"})

    def test_disabled_mode_never_sends(self):
        self.assertEqual(notification_plan(self.snapshot, {}, "disabled"), {"daily":False,"alerts":[]})


if __name__ == "__main__":
    unittest.main()
