from datetime import datetime, timedelta, timezone

import pandas as pd

from zincintel.dashboard_v27 import _research_panel
from zincintel.market_research import describe_close_series


def series(count: int) -> pd.DataFrame:
    end = datetime.now(timezone.utc).date() - timedelta(days=1)
    dates = pd.bdate_range(end=end, periods=count, tz="UTC")
    return pd.DataFrame({"Close": [100 + i * 0.2 + (i % 3) for i in range(count)]}, index=dates)


def main() -> None:
    assert describe_close_series(series(61), "mixed_reference")["status"] == "MISSING"
    short = describe_close_series(series(20), "westmetall_lme_3m_reference")
    assert short["status"] == "INSUFFICIENT_HISTORY"
    assert short["volatility_20_pct"] is None and short["returns_20"] == 19
    ready = describe_close_series(series(61), "westmetall_lme_3m_reference")
    assert ready["status"] == "AVAILABLE"
    assert ready["returns_20"] == 20 and ready["returns_60"] == 60
    assert ready["volatility_20_pct"] > 0 and ready["volatility_60_pct"] > 0
    duplicate = pd.concat([series(61), series(61).tail(1)])
    assert describe_close_series(duplicate, "westmetall_lme_3m_reference")["status"] == "MISSING"
    page = _research_panel({"market_research": {"close_series": ready},
                            "daily_candle_status": {"status": "MISSING", "complete_sessions": 0}})
    assert "Open / High / Low / Close 全部缺少" in page
    assert ready["as_of"] in page and "B_PUBLIC_REFERENCE" in page
    assert "獲利機率" in page
    print("market research tests passed")


if __name__ == "__main__":
    main()
