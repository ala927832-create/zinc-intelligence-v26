"""Regression checks for the public/private OHLC boundary."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from validate_public_isolation import validate


def run() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "data").mkdir()
        (root / "public" / "assets").mkdir(parents=True)
        (root / "data" / "latest_snapshot.json").write_text(json.dumps({
            "daily_candle_status": {"status": "MISSING", "complete_sessions": 0},
            "technical_mode": "CLOSE_ONLY",
        }))
        page = root / "public" / "index.html"
        page.write_text("Public market summary")
        validate(root)

        for path in (root / "data" / "history" / "lme_zinc_3m_ohlc.csv",
                     root / "public" / "assets" / "candle_daily.png"):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("private")
            try:
                validate(root)
                raise AssertionError(f"Private artifact passed validation: {path}")
            except ValueError:
                pass
            path.unlink()

        page.write_text("<img src='assets/candle_daily.png'>")
        try:
            validate(root)
            raise AssertionError("Private chart reference passed validation")
        except ValueError:
            pass

    workflow = (Path(__file__).parent / ".github/workflows/daily_monitor.yml").read_text()
    assert "CANDLE_API_KEY:" not in workflow
    assert "ZINC_DAILY_CANDLE_URL:" not in workflow
    source = (Path(__file__).parent / "main.py").read_text()
    assert "load_verified_daily_candles()" not in source


if __name__ == "__main__":
    run()
    print("Public OHLC isolation tests: PASS")
