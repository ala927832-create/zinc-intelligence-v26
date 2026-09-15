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
    assert ready["sma_14"] is not None and ready["sma_30"] is not None
    assert ready["material_gap_count"] == 0
    assert len(ready["chart_points"]) == 61
    assert ready["chart_points"][-1]["close"] == ready["latest_close"]
    assert ready["chart_points"][-1]["sma14"] == ready["sma_14"]
    assert ready["chart_points"][-1]["ema20"] == ready["ema_20"]
    assert ready["open_status"] == "MISSING_UNVERIFIED_SOURCE"
    assert ready["weekly_close_ranges"][-1]["last_close"] == ready["latest_close"]
    assert ready["ema_20"] is not None and 0 <= ready["rsi_14"] <= 100
    assert short["sma_30"] is None and short["ema_20"] is not None
    assert describe_close_series(series(14), "westmetall_lme_3m_reference")["rsi_14"] is None
    broken = pd.concat([series(60).iloc[:40], series(60).iloc[50:]])
    interrupted = describe_close_series(broken, "westmetall_lme_3m_reference")
    assert interrupted["material_gap_count"] == 1
    assert interrupted["close_indicator_sessions"] == 10
    assert interrupted["returns_20"] == 9 and interrupted["volatility_20_pct"] is None
    assert interrupted["sma_14"] is None and interrupted["rsi_14"] is None
    duplicate = pd.concat([series(61), series(61).tail(1)])
    assert describe_close_series(duplicate, "westmetall_lme_3m_reference")["status"] == "MISSING"
    page = _research_panel({"market_research": {"close_series": ready},
                            "daily_candle_status": {"status": "MISSING", "complete_sessions": 0}})
    assert "收盤價趨勢：可分析" in page and "SMA14" in page and "SMA30" in page
    assert "EMA20" in page and "RSI14" in page
    assert "資料缺口" in page and "最後交易日" in page
    assert "Long-term LME zinc 3M reference Close" in page
    assert "週收盤價區間圖" in page and "非真實 OHLC／週 K" in page
    assert "MISSING_UNVERIFIED_SOURCE" in page
    assert "ATR" not in page
    assert ready["as_of"] in page and "B_PUBLIC_REFERENCE" in page
    assert "獲利機率" in page
    print("market research tests passed")


if __name__ == "__main__":
    main()
