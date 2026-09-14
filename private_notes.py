"""Private chart observations, deliberately separate from OHLC history."""

from __future__ import annotations

from datetime import date
import json
import os
from pathlib import Path
import re
from threading import Lock
from urllib.parse import urlsplit

_LOCK = Lock()
FIELDS = ("chart_url", "market", "contract", "observed_on", "last_trading_day", "moving_averages", "verification", "observations", "attachment")


def normalize_note(raw: dict) -> dict:
    if not isinstance(raw, dict):
        raise ValueError("Observation must be an object")
    note = {key: str(raw.get(key, "")).strip() for key in FIELDS}
    for key, limit in (("chart_url", 1200), ("market", 80), ("contract", 80), ("observations", 2000)):
        if len(note[key]) > limit:
            raise ValueError(f"{key} is too long")
    if not all(note[key] for key in ("chart_url", "market", "contract", "observed_on", "last_trading_day")):
        raise ValueError("Missing required chart/source identity or dates")
    url = urlsplit(note["chart_url"])
    if url.scheme != "https" or not url.hostname or url.username or url.password:
        raise ValueError("Chart link must be an HTTPS URL without embedded credentials")
    try:
        observed = date.fromisoformat(note["observed_on"])
        trading = date.fromisoformat(note["last_trading_day"])
    except ValueError as exc:
        raise ValueError("Invalid ISO date") from exc
    if observed.isoformat() != note["observed_on"] or trading.isoformat() != note["last_trading_day"] or trading > observed or observed > date.today():
        raise ValueError("Inconsistent observation/trading dates")
    if note["verification"] not in {"已核對", "待核對"}:
        raise ValueError("Verification must be 已核對 or 待核對")
    if note["moving_averages"] not in {"無", "MA5", "MA20", "MA50", "MA5/MA20", "MA20/MA50", "MA5/MA20/MA50"}:
        raise ValueError("Unsupported MA selection")
    if note["attachment"]:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,100}\.(?:png|jpg|jpeg|webp)", note["attachment"], re.IGNORECASE):
            raise ValueError("Attachment must be a simple image filename, not a path")
        if raw.get("attachment_allowed") is not True:
            raise ValueError("Confirm permission before referencing a saved image")
    return note


def read_notes(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def add_note(path: Path, raw: dict) -> dict:
    note = normalize_note(raw)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with _LOCK:
        with os.fdopen(os.open(path, os.O_CREAT | os.O_APPEND | os.O_WRONLY, 0o600), "a", encoding="utf-8") as stream:
            stream.write(json.dumps(note, ensure_ascii=False) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
    return note
