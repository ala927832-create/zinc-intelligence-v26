from datetime import datetime, timezone
import xml.etree.ElementTree as ET

import pandas as pd

from zincintel.china_tc import _parse_smm_product, _parse_smm_zinc_table
from zincintel.config import load_settings
from zincintel.data_governance import annotate_data_health, apply_last_known_good, core_data_gate
from zincintel.free_data import _extract_lme_public, _extract_smm_public
from zincintel.free_mirrors import parse_grillo, parse_westmetall
from zincintel.models import procurement_metrics, strategy_recommendation
from zincintel.providers import LmeXmlAdapter, _normalize_candles


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
    assert pub_values["lme_cash"] == 3685.5
    assert pub_values["lme_3m"] == 3621.0
    assert pub_values["lme_closing_3m"] == 3673.5
    assert pub_values["lme_inventory_t"] == 105800.0
    assert pub_values["cancelled_warrants_t"] == 19775.0
    assert pub_date == "2026-09-10"

    grillo_html = '''<html><body>
    Last modified (day-delayed): 10.09.2026
    Cash desk Money: 3.685,00 $/t Letter: 3.685,50 $/t
    3-months Money: 3.619,00 $/t Letter: 3.621,00 $/t
    LME-Zinc Stock (10.09.2026) Opening stock 105.800 Live warrants 83.950 Cancelled warrants 21.850
    </body></html>'''
    gv, gd = parse_grillo(grillo_html)
    assert gv["lme_cash"] == 3685.5
    assert gv["lme_3m"] == 3621.0
    assert gv["lme_inventory_t"] == 105800.0
    assert gv["live_warrants_t"] == 83950.0
    assert gv["cancelled_warrants_t"] == 21850.0
    assert gd == "2026-09-10"

    west_html = '''<table><thead><tr><th>Date</th><th>Zinc Cash Settlement</th><th>Zinc 3-month</th><th>Zinc stock</th></tr></thead>
    <tbody><tr><td>09.09.2026</td><td>3.670,00</td><td>3.610,00</td><td>106.000</td></tr>
    <tr><td>10.09.2026</td><td>3.685,50</td><td>3.621,00</td><td>105.800</td></tr></tbody></table>'''
    wv, wd, wh = parse_westmetall(west_html)
    assert wv["lme_cash"] == 3685.5
    assert wv["lme_3m"] == 3621.0
    assert wv["lme_inventory_t"] == 105800.0
    assert wd == "2026-09-10"
    assert len(wh) == 2

    smm_html = '''<table><tr><th>Price description</th><th>Avg.</th><th>Date</th></tr>
    <tr><td>SMM 0# Zinc Ingot premium (USD/tonne)</td><td>-13.82</td><td>Sep 10, 2026</td></tr>
    <tr><td>SMM Zinc Concentrate TC Index (Weekly) (USD/dmt)</td><td>-124.5</td><td>Sep 04, 2026</td></tr></table>'''
    smm_values, _ = _extract_smm_public(smm_html)
    assert smm_values["tc_usd_t"] == -124.5
    assert smm_values["physical_premium_usd_t"] == -13.82

    product_html = '''<html><body><h1>SMM Zinc Concentrate TC Index (Weekly) Price, USD/dmt</h1><div>Avg.:-124.5</div><div>Sep 04, 2026</div><div>Update Time: 17:00 GMT+8</div></body></html>'''
    tc_product = _parse_smm_product(product_html)
    assert tc_product["value"] == -124.5
    assert tc_product["unit"].lower() == "usd/dmt"
    assert tc_product["as_of"] == "2026-09-04"

    zinc_table_html = '''<table><tr><th>Price description</th><th>Price Range</th><th>Avg.</th><th>Change</th><th>Date</th></tr>
    <tr><td>Domestic Zinc Concentrate TC (Monthly) (USD/tonne)</td><td>-328.44--262.75</td><td>-295.59</td><td>-184.48</td><td>Sep 01, 2026</td></tr>
    <tr><td>Domestic Zinc Concentrate TC (Weekly) (USD/tonne)</td><td>-315.3--236.48</td><td>-275.89</td><td>-32.88</td><td>Sep 04, 2026</td></tr>
    <tr><td>SMM Zinc Concentrate TC Index (Weekly) (USD/dmt)</td><td>-124.5--124.5</td><td>-124.5</td><td>-1.25</td><td>Sep 04, 2026</td></tr></table>'''
    zinc_table = _parse_smm_zinc_table(zinc_table_html)
    assert zinc_table["domestic_weekly"]["value"] == -275.89
    assert zinc_table["domestic_weekly"]["unit"].lower() == "usd/tonne"
    assert zinc_table["domestic_weekly"]["as_of"] == "2026-09-04"
    assert zinc_table["domestic_monthly"]["value"] == -295.59
    assert zinc_table["import_weekly"]["value"] == -124.5

    raw = pd.DataFrame([{"timestamp": "2026-09-10T18:00:00Z", "Open": 3000, "High": 3050, "Low": 2980, "Close": 3020}])
    normalized = _normalize_candles(raw)
    assert not normalized.empty
    assert float(normalized.iloc[-1]["Close"]) == 3020.0

    close_only = pd.DataFrame([{"timestamp": "2026-09-10T18:00:00Z", "Close": 3020}])
    assert _normalize_candles(close_only).empty


def governance_tests():
    today = datetime.now(timezone.utc).date().isoformat()
    previous = {
        "lme_cash": 3685.5,
        "lme_3m": 3621.0,
        "lme_inventory_t": 105800.0,
        "live_warrants_t": 83950.0,
        "cancelled_warrants_t": 21850.0,
        "field_sources": {
            key: {"provider": "lme_xml_test", "status": "OFFICIAL_NEXT_DAY", "as_of": today}
            for key in ["lme_cash", "lme_3m", "lme_inventory_t", "live_warrants_t", "cancelled_warrants_t"]
        },
    }
    current = {"field_sources": {}, "provider_status": {}}
    carried = apply_last_known_good(current, previous)
    assert carried["lme_cash"] == 3685.5
    assert carried["field_sources"]["lme_cash"]["status"] == "CARRY_FORWARD"
    annotated = annotate_data_health(carried)
    gate = core_data_gate(annotated)
    assert gate["status"] == "HEALTHY"
    assert len(gate["usable_core"]) == 5


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
    governance_tests()
    print("smoke test passed")


if __name__ == "__main__":
    main()
