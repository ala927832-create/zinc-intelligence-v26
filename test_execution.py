import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from zincintel.execution import append_trade, performance_summary, read_trades, simulate_execution


class ExecutionTest(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 13, 2, 31, tzinfo=timezone.utc)
        self.quote = {"market":"Gold", "contract":"GCZ26", "side":"LONG",
                      "quote_timestamp":"2026-10-13T02:30:30+00:00", "bid":99, "ask":100,
                      "hard_stop":95, "t1":111, "t2":116, "account_equity":100000,
                      "risk_pct":1, "contract_multiplier":10, "tick_size":0.1,
                      "fees_per_contract":1, "slippage_ticks":1, "max_spread_ticks":12,
                      "max_quote_age_seconds":120, "mark_price":105}

    def test_approved_simulation_includes_live_quote_risk_and_pnl(self):
        result = simulate_execution(self.quote, now=self.now)
        self.assertEqual(result["status"], "APPROVED_FOR_SIMULATION")
        self.assertFalse(result["order_transmitted"])
        self.assertGreaterEqual(result["planned_rr_t1"], 2)
        self.assertGreater(result["contract_quantity"], 0)
        self.assertEqual(result["contract_multiplier"], 10)
        self.assertGreater(result["unrealized_pnl"], 0)

    def test_stale_quote_and_wide_spread_are_rejected(self):
        raw = {**self.quote, "quote_timestamp":"2026-10-13T02:00:00+00:00",
               "bid":98, "ask":100, "max_spread_ticks":4}
        result = simulate_execution(raw, now=self.now)
        self.assertEqual(result["status"], "REJECTED")
        self.assertIn("QUOTE_STALE", result["blockers"])
        self.assertIn("SPREAD_TOO_WIDE", result["blockers"])

    def test_trade_journal_is_private_append_only_and_marks_small_sample(self):
        raw = {"setup_id":"gold-20261013-a", "market":"Gold", "contract":"GCZ26", "side":"LONG",
               "planned_entry":100, "hard_stop":95, "t1":111, "t2":116, "actual_fill":100.2,
               "exit_price":111, "quantity":2, "contract_multiplier":10, "fees":4,
               "opened_at":"2026-10-13T10:30:00+08:00", "closed_at":"2026-10-16T10:30:00+08:00",
               "exit_reason":"T1", "rule_followed":True}
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "execution_journal.jsonl"
            trade = append_trade(path, raw)
            self.assertGreater(trade["actual_r"], 0)
            self.assertEqual(performance_summary(read_trades(path))["status"], "INSUFFICIENT_SAMPLE")
            with self.assertRaisesRegex(ValueError, "already exists"):
                append_trade(path, raw)


if __name__ == "__main__":
    unittest.main()
