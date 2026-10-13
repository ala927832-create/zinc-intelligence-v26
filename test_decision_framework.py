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
        self.assertLessEqual(result["daily_plan"]["risk_distance_atr"], 3)

    def test_excessive_structural_stop_distance_forces_no_trade(self):
        points = []
        for i in range(80):
            close = 100 + i
            points.append({"date":f"2026-01-{(i%28)+1:02d}", "open":close-1, "high":close+2,
                           "low":close-2, "close":close, "ema20":100, "sma60":90,
                           "atr14":4, "rsi14":58})
        result = build_ohlc_plan({"status":"AVAILABLE", "name":"Wide risk", "observations":80,
                                  "chart_points":points, "latest_session":points[-1]})
        self.assertEqual(result["decision"], "NO_TRADE")
        self.assertEqual(result["strategy_gate"], "BLOCKED_RISK_DISTANCE")
        self.assertIn("exceeds the 3.00 ATR limit", result["no_trade_reasons"][0])

    def test_close_only_lme_never_creates_candle_plan(self):
        points = [{"date":f"2026-09-{i+1:02d}", "close":3800+i*5} for i in range(20)]
        result = build_lme_close_only_plan({"status":"AVAILABLE", "observations":430,
            "latest_close":3895, "as_of":"2026-10-12", "trend":{"regime":"BULL"},
            "chart_points":points, "ema_20":3860, "sma_30":3820},
            {"lme_cash":3910, "lme_3m":3895, "cash_3m":15})
        self.assertEqual(result["decision"], "WAIT_FOR_TRIGGER")
        self.assertEqual(result["daily_plan"]["plan_basis"], "LME_3M_CLOSE_ONLY_RESEARCH")
        self.assertNotIn("atr14", result["daily_plan"])
        self.assertNotIn("candle", result["daily_plan"])
        self.assertIn("no candle pattern or ATR is inferred", result["no_trade_reasons"][0])
        self.assertEqual(result["reference"]["cash"], 3910)
        self.assertEqual(len(result["decision_audit"]), 8)

    def test_every_market_has_eight_question_audit_and_missing_evidence_is_disclosed(self):
        points = []
        for i in range(80):
            close = 100 + i
            points.append({"date":f"2026-01-{(i%28)+1:02d}", "open":close-1, "high":close+2,
                           "low":close-2, "close":close, "ema20":close-5, "sma60":close-12,
                           "atr14":4, "rsi14":58})
        full = {"status":"AVAILABLE", "name":"Gold", "observations":80, "series_type":"FULL_OHLC",
                "chart_points":points, "latest_session":points[-1]}
        book = build_decision_book({"status":"MISSING"}, {"status":"MISSING"}, {"gold":full})
        gold = book["markets"]["gold"]
        self.assertEqual(len(gold["decision_audit"]), 8)
        self.assertEqual(gold["evidence_alignment"], "PARTIAL_TECHNICAL_ONLY")
        self.assertLess(gold["evidence_completeness"], 100)


if __name__ == "__main__":
    unittest.main()
