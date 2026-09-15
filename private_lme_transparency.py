"""Private-only LMEselect 3M OHLC reconstruction from licensed transparency files.

This utility is intentionally disconnected from ``main.py`` and ``public/``.
The output is a reconstruction from trades, not the official LME OHLC product.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import pandas as pd


def reconstruct(trades_path: Path, instruments_path: Path, output: Path) -> pd.DataFrame:
    trades, instruments = pd.read_csv(trades_path), pd.read_csv(instruments_path)
    required_trades = {"trade_id", "trade_date", "event_time", "isin", "price", "volume", "action"}
    required_instruments = {"isin", "metal", "venue", "contract"}
    if not required_trades <= set(trades) or not required_instruments <= set(instruments):
        raise ValueError("Input columns do not match the documented normalized schema")
    instruments = instruments[(instruments.metal.str.upper() == "ZINC") &
                              (instruments.venue.str.upper() == "LMESELECT") &
                              (instruments.contract.str.upper().isin({"3M", "3-MONTH"}))]
    work = trades.merge(instruments[["isin"]].drop_duplicates(), on="isin", how="inner")
    work = work.sort_values(["event_time", "trade_id"])
    # Last publication action wins; CANCEL rows remove the trade.
    work = work.drop_duplicates("trade_id", keep="last")
    work = work[work.action.str.upper().isin({"NEW", "CORRECT"})]
    work["price"] = pd.to_numeric(work.price, errors="coerce")
    work["volume"] = pd.to_numeric(work.volume, errors="coerce")
    work["event_time"] = pd.to_datetime(work.event_time, errors="coerce", utc=True)
    work = work.dropna(subset=["event_time", "price", "volume"])
    work = work[(work.price > 0) & (work.volume > 0)]
    rows = []
    for day, group in work.groupby("trade_date", sort=True):
        group = group.sort_values("event_time")
        rows.append({"date": day, "open": group.price.iloc[0], "high": group.price.max(),
                     "low": group.price.min(), "close": group.price.iloc[-1], "volume": group.volume.sum(),
                     "trades": len(group), "status": "RECONSTRUCTED_NOT_OFFICIAL",
                     "method": "first/max/min/last eligible LMEselect 3M transparency trade"})
    result = pd.DataFrame(rows)
    output.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(output, index=False)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trades", type=Path, required=True)
    parser.add_argument("--instruments", type=Path, required=True)
    private_root = Path(os.environ.get("ZINC_PRIVATE_DIR", str(Path.home() / "zinc-private")))
    parser.add_argument("--output", type=Path, default=private_root / "lme_zinc_3m_reconstructed_ohlc.csv")
    args = parser.parse_args()
    frame = reconstruct(args.trades, args.instruments, args.output)
    print(f"Private reconstructed sessions: {len(frame)} -> {args.output}")


if __name__ == "__main__":
    main()
