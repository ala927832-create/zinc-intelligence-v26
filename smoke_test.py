from zincintel.models import procurement_metrics, strategy_recommendation
from zincintel.config import load_settings


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
    print("smoke test passed")


if __name__ == "__main__":
    main()
