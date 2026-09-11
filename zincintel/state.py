from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .utils import DATA_DIR, age_days, read_json, safe_float, write_json

PROC_PATH = DATA_DIR / "procurement_state.json"
HISTORY_PATH = DATA_DIR / "history.json"
SIGNAL_PATH = DATA_DIR / "signal_journal.json"
TRADES_PATH = DATA_DIR / "paper_trades.json"
LATEST_PATH = DATA_DIR / "latest_snapshot.json"


def update_procurement_state(inventory_input: Any, demand_input: Any) -> dict:
    state = read_json(PROC_PATH, {})
    now = datetime.now(timezone.utc).isoformat()
    inv = safe_float(inventory_input)
    dem = safe_float(demand_input)

    if inv is not None:
        if inv < 0:
            raise ValueError("current_inventory_t must be >= 0")
        state["current_inventory_t"] = inv
        state["inventory_updated_at"] = now
        state["inventory_source"] = "workflow/manual input"

    if dem is not None:
        if dem <= 0:
            raise ValueError("demand_60d_t must be > 0")
        state["demand_60d_t"] = dem
        state["demand_updated_at"] = now
        state["demand_source"] = "workflow/manual input"

    write_json(PROC_PATH, state)
    return state


def procurement_input_status(state: dict) -> dict:
    inv_age = age_days(state.get("inventory_updated_at"))
    dem_age = age_days(state.get("demand_updated_at"))
    ages = [x for x in [inv_age, dem_age] if x is not None]
    max_age = max(ages) if ages else None
    return {"inventory_age_days": inv_age, "demand_age_days": dem_age, "max_age_days": max_age}


def append_record(path: Path, record: dict, max_records: int = 5000) -> None:
    rows = read_json(path, [])
    rows.append(record)
    if len(rows) > max_records:
        rows = rows[-max_records:]
    write_json(path, rows)


def append_history(record: dict) -> None:
    append_record(HISTORY_PATH, record)


def append_signal(record: dict) -> None:
    append_record(SIGNAL_PATH, record)


def load_trades() -> list[dict]:
    return read_json(TRADES_PATH, [])


def save_trades(trades: list[dict]) -> None:
    write_json(TRADES_PATH, trades)


def save_latest(snapshot: dict) -> None:
    write_json(LATEST_PATH, snapshot)
    date_key = snapshot.get("run_date", "unknown")
    snap_dir = DATA_DIR / "snapshots"
    snap_dir.mkdir(parents=True, exist_ok=True)
    write_json(snap_dir / f"{date_key}.json", snapshot)
