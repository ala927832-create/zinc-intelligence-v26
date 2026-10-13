import unittest
from unittest.mock import Mock, patch

import pandas as pd

from zincintel.cross_asset_research import (
    Instrument, _alpha_fx, describe_close_history, describe_history,
)


class CrossAssetResearchTest(unittest.TestCase):
    def test_alpha_fx_parses_complete_ohlc(self):
        payload = {"Time Series FX (Daily)": {
            "2026-10-09":{"1. open":"150","2. high":"152","3. low":"149","4. close":"151"},
            "2026-10-08":{"1. open":"149","2. high":"151","3. low":"148","4. close":"150"},
        }}
        response = Mock(); response.json.return_value = payload; response.raise_for_status.return_value = None
        with patch("zincintel.cross_asset_research.requests.get", return_value=response):
            frame = _alpha_fx("test-key", "USD", "JPY")
        self.assertEqual(list(frame.columns), ["Open","High","Low","Close","Volume"])
        self.assertEqual(float(frame.iloc[-1]["Close"]), 151)

    def test_close_series_never_becomes_ohlc(self):
        idx = pd.date_range("2026-01-01", periods=80, freq="D")
        result = describe_close_history(pd.Series(range(100,180), index=idx), key="basket",
            name="Basket", symbol="B", identity="research", unit="index", source="test")
        self.assertEqual(result["series_type"], "CLOSE_ONLY")
        self.assertNotIn("open", result["chart_points"][-1])
        self.assertIsNotNone(result["latest_session"]["rsi14"])

    def test_malformed_ohlc_is_rejected(self):
        frame = pd.DataFrame({"Open":[10],"High":[9],"Low":[8],"Close":[10],"Volume":[1]},
                             index=pd.to_datetime(["2026-10-09"]))
        result = describe_history(frame, Instrument("x","X","X","test","u"))
        self.assertEqual(result["status"], "MISSING")


if __name__ == "__main__":
    unittest.main()
