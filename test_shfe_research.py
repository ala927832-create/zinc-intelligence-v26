import unittest

import pandas as pd

from zincintel.shfe_research import describe_history, parse_daily_payload


class ShfeResearchTests(unittest.TestCase):
 def test_selects_highest_open_interest_and_validates_identity(self):
    def row(month, oi, volume, o, h, l, c):
        return {"PRODUCTID":"zn_f", "DELIVERYMONTH":month, "OPENINTEREST":oi, "VOLUME":volume,
                "OPENPRICE":o, "HIGHESTPRICE":h, "LOWESTPRICE":l, "CLOSEPRICE":c,
                "SETTLEMENTPRICE":c, "OPENINTERESTCHG":1}
    payload={"o_curinstrument":[row("2610",100,200,20000,20200,19900,20100), row("2611",300,100,21000,21200,20900,21100)]}
    from datetime import date
    selected=parse_daily_payload(payload,date(2026,9,14))
    self.assertEqual(selected["contract"], "zn2611")
    self.assertEqual(selected["market"], "SHFE")
    self.assertEqual(selected["source_grade"], "A_OFFICIAL_EXCHANGE")


 def test_description_preserves_roll_and_ohlc(self):
    rows=[]
    for i in range(60):
        close=20000+i
        rows.append({"date":f"2026-01-{i+1:02d}","contract":"zn2603" if i<30 else "zn2604",
                     "open":close-2,"high":close+5,"low":close-5,"close":close,
                     "volume":100,"open_interest":200})
    result=describe_history(pd.DataFrame(rows))
    self.assertEqual(result["status"], "AVAILABLE")
    self.assertEqual(result["observations"], 60)
    self.assertEqual(result["roll_count"], 1)
    self.assertIsNotNone(result["chart_points"][-1]["sma50"])


if __name__ == "__main__":
    unittest.main()
