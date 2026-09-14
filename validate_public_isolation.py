"""Fail closed if private OHLC crosses into the public repository or Pages."""

from __future__ import annotations

import json
from pathlib import Path


def validate(root: Path) -> None:
    data = root / "data"
    public = root / "public"
    forbidden = [
        *data.rglob("*ohlc*"),
        *data.rglob("*candle*"),
        *data.glob("lme_zinc_3m_*.csv"),
        *public.rglob("*candle*.png"),
    ]
    forbidden = sorted({p for p in forbidden if p.is_file()})
    if forbidden:
        raise ValueError("Private OHLC or candle assets in public state: " + ", ".join(str(p.relative_to(root)) for p in forbidden))

    snapshot = json.loads((data / "latest_snapshot.json").read_text(encoding="utf-8"))
    candle = snapshot.get("daily_candle_status", {})
    if candle.get("status") != "MISSING" or candle.get("complete_sessions") != 0:
        raise ValueError("Public snapshot must not publish OHLC sessions")
    if snapshot.get("technical_mode") == "FULL_OHLC":
        raise ValueError("Public snapshot must not use private OHLC for technical research")

    page = (public / "index.html").read_text(encoding="utf-8")
    if "assets/candle_" in page:
        raise ValueError("Public page must not reference a private candle chart")


if __name__ == "__main__":
    validate(Path(__file__).resolve().parent)
    print("Public OHLC isolation: PASS")
