import unittest

from zincintel.decision_framework import build_decision_book, build_lme_close_only_plan, build_ohlc_plan


class DecisionFrameworkTest(unittest.TestCase):
    def test_ohlc_plan_is_not_executable_without_live_quote(self):
        points = []
        for i in range(80):
            close = 100 + i
            points.append({"date": f"2026-01-{(i%28)+1:02d}", "open": close-1, "high": close+2,
                           "low": close-2, "close": close, "ema20": close-5,
                           "sma60": close-12, "atr14": 4, "rsi14": 58})
        series = {"status":"AVAILABLE", "name":"Test", "symbol":"T", "as_of":"2026-04-01",
                  "chart_points":points, "latest_session":points[-1]}
        result = build_ohlc_plan(series)
        self.assertEqual(result["decision"], "WAIT_FOR_TRIGGER")
        self.assertEqual(result["execution_gate"], "PENDING_LIVE_QUOTE")
        self.assertGreaterEqual(result["daily_plan"]["planned_rr_t1"], 2)

    def test_close_only_lme_never_creates_candle_plan(self):
        result = build_lme_close_only_plan({"status":"AVAILABLE", "observations":430,
            "latest_close":3900, "as_of":"2026-10-12", "trend":{"regime":"BULL"}})
        self.assertEqual(result["decision"], "NO_TRADE")
        self.assertEqual(result["trigger_gate"], "BLOCKED_NO_LME_OHLC")
        self.assertEqual(result["daily_plan"], {})


if __name__ == "__main__":
    unittest.main()
