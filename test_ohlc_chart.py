"""Tests use synthetic rows only; none are included in production history."""

from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import pandas as pd

from zincintel import dashboard, dashboard_v27, ohlc_history, providers


def row(days_ago: int, close: float = 100.0) -> dict:
    return {
        "date": (datetime.now(timezone.utc).date() - timedelta(days=days_ago)).isoformat(),
        "open": 99.0, "high": 102.0, "low": 98.0, "close": close,
        "market": "LME", "contract": "ZINC_3M", "currency": "USD",
        "source": "synthetic_test_only", "public_display_allowed": True,
    }


def must_reject(rows: list[dict]) -> None:
    try:
        ohlc_history.validate_daily_rows(pd.DataFrame(rows))
    except ValueError:
        return
    raise AssertionError("invalid OHLC unexpectedly passed")


def main() -> None:
    must_reject([{**row(2), "market": "SHFE"}])
    must_reject([{**row(2), "public_display_allowed": False}])
    must_reject([{**row(2), "high": 97}])
    must_reject([row(0)])
    must_reject([row(2), row(2)])
    must_reject([{"date": row(2)["date"], "close": 100}])

    with TemporaryDirectory() as tmp:
        history = Path(tmp) / "history.csv"
        public = Path(tmp) / "public"
        with patch.object(ohlc_history, "HISTORY_PATH", history), patch.object(dashboard_v27, "PUBLIC_DIR", public), patch.object(dashboard_v27, "build_legacy_dashboard", lambda *args: None):
            with patch.object(providers, "_read_table", return_value=pd.DataFrame()):
                missing, missing_source = providers.load_verified_daily_candles()
                assert missing.empty and missing_source == "missing"
            rows = ohlc_history.persist_daily_rows(pd.DataFrame([row(3), row(2)]))
            assert len(rows) == 2
            assert len(ohlc_history.persist_daily_rows(pd.DataFrame([row(2)]))) == 2
            try:
                ohlc_history.persist_daily_rows(pd.DataFrame([row(2, close=101)]))
            except ValueError:
                pass
            else:
                raise AssertionError("conflicting trading date was overwritten")
            assert len(ohlc_history.load_verified_history()) == 2
            frame = ohlc_history.chart_frame(rows)
            assert len(frame) == 2 and frame.index.is_monotonic_increasing
            with patch.object(dashboard, "PUBLIC_DIR", public):
                assert dashboard._make_candle_chart(frame, [], filename="integration.png")
                assert (public / "assets" / "integration.png").read_bytes().startswith(b"\x89PNG")
                assert dashboard._make_candle_chart(pd.DataFrame(), [], filename="integration.png") is None
                assert not (public / "assets" / "integration.png").exists()

            assets = public / "assets"
            assets.mkdir(parents=True, exist_ok=True)
            (assets / "candle_daily.png").write_bytes(b"chart-for-test")
            (assets / "candle_weekly.png").write_bytes(b"chart-for-test")
            status = {"status": "INSUFFICIENT_HISTORY", "complete_sessions": 2,
                      "last_complete_date": rows.iloc[-1]["date"], "source": "synthetic_test_only"}
            snapshot = {"daily_candle_status": status, "technical_mode": "CLOSE_ONLY"}
            dashboard_v27.build_dashboard_v27(snapshot, {"daily": frame}, [], {})
            rendered = (public / "index.html").read_text()
            assert "2 verified sessions" in rendered and "assets/candle_daily.png" in rendered
            assert len(status["image_sha256"]) == 64

            snapshot["daily_candle_status"] = {"status": "MISSING", "complete_sessions": 0, "source": "missing"}
            dashboard_v27.build_dashboard_v27(snapshot, {"daily": pd.DataFrame()}, [], {})
            assert not (assets / "candle_daily.png").exists()
            assert not (assets / "candle_weekly.png").exists()
            assert "assets/candle_daily.png" not in (public / "index.html").read_text()
    print("OHLC chart tests passed")


if __name__ == "__main__":
    main()
