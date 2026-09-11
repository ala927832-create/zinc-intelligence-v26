from zincintel.models import procurement_metrics, strategy_recommendation
from zincintel.config import load_settings
from zincintel.free_data import _extract_lme_public, _extract_smm_public
from zincintel.providers import LmeXmlAdapter, _normalize_candles
import pandas as pd
import xml.etree.ElementTree as ET


def provider_tests():
    ofs = ET.fromstring('''<lme status="0"><date>20260910</date><officials status="0"><row_official status="0" code="ZS" type="M"><currency>USD</currency><settlement>3020.0</settlement><of_item prompt_date="CASH"><bid>3019.0</bid><ask>3020.0</ask></of_item><of_item prompt_date="3M"><bid>2989.0</bid><ask>2991.0</ask></of_item></row_official></officials></lme>''')
    values, _ = LmeXmlAdapter.parse_ofs(ofs)
    assert values["lme_cash"] == 3020.0
    assert values["lme_3m"] == 2991.0

    wsm = ET.fromstring('''<lme status="0"><date>20260910</date><wsmreport status="0"><identification report_code="WSM" report_date="20260909" report_time="0900" report_version="100"/><datawsm><row_wsm code="ZS"><location/><grade_code/><stock_status>I</stock_status><stock_qty>105800</stock_qty><expiry/></row_wsm><row_wsm code="ZS"><location/><grade_code/><stock_status>e</stock_status><stock_qty>83950</stock_qty><expiry/></row_wsm><row_wsm code="ZS"><location/><grade_code/><stock_status>f</stock_status><stock_qty>21850</stock_qty><expiry/></row_wsm></datawsm></wsmreport></lme>''')
    values2, _ = LmeXmlAdapter.parse_wsm(wsm)
    assert values2["lme_inventory_t"] == 105800.0
    assert values2["cancelled_warrants_t"] == 21850.0

    public_html = '''<html><body><div>Data valid for 10 Sep 2026</div>
    <table><tr><th>Contract</th><th>Bid</th><th>Offer</th></tr>
    <tr><td>Cash</td><td>3685.00</td><td>3685.50</td></tr>
    <tr><td>3-month</td><td>3619.00</td><td>3621.00</td></tr></table>
    <table><tr><th>Contract</th><th>Price</th></tr><tr><td>3-month</td><td>3673.50</td></tr></table>
    <table><tr><th>Stocks</th><th>Amount</th></tr><tr><td>Opening Stock</td><td>105800</td></tr>
    <tr><td>Live warrants</td><td>83950</td></tr><tr><td>Cancelled warrants</td><td>19775</td></tr></table></body></html>'''
    pub_values, pub_date = _extract_lme_public(public_html)
    assert pub_values["lme_cash_bid"] == 3685.0
    assert pub_values["lme_cash_offer"] == 3685.5
    assert pub_values["lme_3m_bid"] == 3619.0
    assert pub_values["lme_3m_offer"] == 3621.0
    assert pub_values["lme_closing_3m"] == 3673.5
    assert pub_values["lme_inventory_t"] == 105800.0
    assert pub_values["cancelled_warrants_t"] == 19775.0
    assert pub_date == "2026-09-10"

    smm_html = '''<table><tr><th>Price description</th><th>Avg.</th><th>Date</th></tr>
    <tr><td>SMM 0# Zinc Ingot premium (USD/tonne)</td><td>-13.82</td><td>Sep 10, 2026</td></tr>
    <tr><td>SMM Zinc Concentrate TC Index (Weekly) (USD/dmt)</td><td>-124.5</td><td>Sep 04, 2026</td></tr></table>'''
    smm_values, _ = _extract_smm_public(smm_html)
    assert smm_values["tc_usd_t"] == -124.5
    assert smm_values["physical_premium_usd_t"] == -13.82

    raw = pd.DataFrame([{"timestamp": "2026-09-10T18:00:00Z", "Open": 3000, "High": 3050, "Low": 2980, "Close": 3020}])
    normalized = _normalize_candles(raw)
    assert not normalized.empty
    assert float(normalized.iloc[-1]["Close"]) == 3020.0

    close_only = pd.DataFrame([{"timestamp": "2026-09-10T18:00:00Z", "Close": 3020}])
    assert _normalize_candles(close_only).empty


def main():
    s = load_settings()
    p = procurement_metrics({"current_inventory_t": 420.0, "demand_60d_t": 1200.0}, "BULL", s)
    assert p["coverage_days"] == 21.0
    assert p["uncovered_demand_t"] == 780.0
    assert p["action"] in {"NORMALIZE", "ACCELERATE", "PARTIAL_COVER", "MAINTAIN"}
    rec = strategy_recommendation(
        "conservative", 70.0, 90.0,
        {"Close": 2850.0, "ATR14": 40.0, "EMA20": 2845.0, "EMA50": 2800.0, "EMA200": 2700.0, "ROC20": 2.0},
        s, {"n": 0, "wins": 0}
    )
    assert rec["paper_only"] is True
    assert rec["suggested_stop"] < rec["reference_price"]
    provider_tests()
    print("smoke test passed")


if __name__ == "__main__":
    main()
