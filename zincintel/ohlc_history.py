"""Validated, dated LME zinc 3M bars for the informational chart."""

from __future__ import annotations

import pandas as pd

from .utils import DATA_DIR

HISTORY_PATH = DATA_DIR / "history" / "lme_zinc_3m_ohlc.csv"
IDENTITY = {"market": "LME", "contract": "ZINC_3M", "currency": "USD"}
REQUIRED = ("date", "open", "high", "low", "close", "market", "contract", "currency", "source", "public_display_allowed")


def validate_daily_rows(raw: pd.DataFrame) -> pd.DataFrame:
    """Reject an entire batch if its identity, dates or OHLC are ambiguous."""
    if raw is None or raw.empty:
        raise ValueError("empty OHLC batch")
    df = raw.rename(columns={c: str(c).strip().lower() for c in raw.columns}).copy()
    if any(c not in df for c in REQUIRED):
        raise ValueError("OHLC requires date, four prices, market, contract, currency and source")
    df = df[list(REQUIRED)]
    for field, expected in IDENTITY.items():
        if not df[field].astype(str).str.strip().str.upper().eq(expected).all():
            raise ValueError(f"unexpected {field} in LME zinc 3M history")
    if df["source"].isna().any() or df["source"].astype(str).str.strip().eq("").any():
        raise ValueError("missing per-row source")
    if not df["public_display_allowed"].astype(str).str.lower().eq("true").all():
        raise ValueError("source is not cleared for public display and repository storage")
    df["public_display_allowed"] = "true"
    dates = pd.to_datetime(df["date"], errors="coerce", utc=True)
    if dates.isna().any() or not df["date"].astype(str).str.fullmatch(r"\d{4}-\d{2}-\d{2}").all():
        raise ValueError("daily bars require an explicit ISO trading date")
    if (dates.dt.date >= pd.Timestamp.now(tz="UTC").date()).any():
        raise ValueError("today's or a future bar is not yet complete")
    df["date"] = dates.dt.strftime("%Y-%m-%d")
    for field in ("open", "high", "low", "close"):
        df[field] = pd.to_numeric(df[field], errors="coerce")
    if df[["open", "high", "low", "close"]].isna().any().any():
        raise ValueError("incomplete OHLC bar")
    if (df[["open", "high", "low", "close"]] <= 0).any().any():
        raise ValueError("non-positive OHLC bar")
    if ((df["high"] < df[["open", "low", "close"]].max(axis=1)) |
            (df["low"] > df[["open", "high", "close"]].min(axis=1))).any():
        raise ValueError("invalid OHLC range")
    if df.duplicated("date").any():
        raise ValueError("duplicate trading date; corrections require explicit review")
    return df.sort_values("date").reset_index(drop=True)


def load_verified_history() -> pd.DataFrame:
    if not HISTORY_PATH.exists():
        return pd.DataFrame()
    return validate_daily_rows(pd.read_csv(HISTORY_PATH, dtype={"date": str}))


def persist_daily_rows(raw: pd.DataFrame) -> pd.DataFrame:
    incoming = validate_daily_rows(raw)
    existing = load_verified_history()
    if not existing.empty:
        overlap = existing.merge(incoming, on="date", suffixes=("_old", "_new"))
        for field in REQUIRED[1:]:
            if not overlap[f"{field}_old"].eq(overlap[f"{field}_new"]).all():
                raise ValueError(f"conflicting OHLC history: {field}")
    combined = pd.concat([existing, incoming], ignore_index=True)
    combined = combined.drop_duplicates("date").sort_values("date")
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    combined.to_csv(HISTORY_PATH, index=False)
    return combined


def chart_frame(rows: pd.DataFrame) -> pd.DataFrame:
    if rows.empty:
        return pd.DataFrame()
    result = rows.rename(columns={"open": "Open", "high": "High", "low": "Low", "close": "Close"}).copy()
    result["Volume"] = 0.0
    result.index = pd.to_datetime(result.pop("date"), utc=True)
    return result[["Open", "High", "Low", "Close", "Volume"]]
