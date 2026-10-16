"""Offline import of saved Cnyes ZSCS chart HTML into an isolated private archive.

No network calls, scheduled ingestion, public data writes or strategy signals.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import tempfile

ROOT = Path(__file__).resolve().parent
SERIES = "CNYES_ZSCS_REFERENCE"
SOURCE = "https://www.cnyes.com/futures/html5chart/ZSCS.html"
HOLIDAYS = {"2025-12-25", "2026-04-03"}  # Known conflicts, not a full calendar.


def outside_repo(path: Path) -> Path:
    path = path.resolve()
    if path == ROOT or ROOT in path.parents:
        raise ValueError("Private input/output must be outside the public repository")
    # Also reject other Git checkouts and public site output directories.
    if any((p / ".git").exists() for p in (path, *path.parents)):
        raise ValueError("Private files cannot be inside a Git checkout")
    if "public" in path.parts or "dist" in path.parts:
        raise ValueError("Private files cannot be in deployment asset directories")
    return path


def parse_chart(text: str, *, today: date) -> list[dict]:
    if not re.search(r"var\s+code\s*=\s*['\"]zscs['\"]", text, re.I):
        raise ValueError("Expected the saved ZSCS chart frame, not another instrument")
    if not re.search(r"var\s+country\s*=\s*['\"]future['\"]|country='future'", text):
        raise ValueError("Missing chart market identity")
    result = {}
    for payload in re.findall(r"globalData\.push\(\[(.*?)\]\)", text):
        fields = [x.strip() for x in payload.split(",")]
        if len(fields) < 7:
            raise ValueError("Incomplete chart row")
        raw_day = fields[2].strip("'\"")
        if not re.fullmatch(r"\d{8}", raw_day):
            raise ValueError("Invalid source date")
        day = date(int(raw_day[:4]), int(raw_day[4:6]), int(raw_day[6:]))
        if day >= today:
            raise ValueError("Current/future source bar needs completion review")
        if day < date(2025, 1, 1):
            continue
        o, h, l, c = map(float, fields[3:7])
        if not all(math.isfinite(v) and v > 0 for v in (o, h, l, c)) or not l <= min(o, c) <= max(o, c) <= h:
            raise ValueError("Invalid OHLC range")
        key = day.isoformat()
        if key in result:
            raise ValueError("Duplicate source date")
        flags = (["HOLIDAY_DATE_CONFLICT"] if key in HOLIDAYS else [])
        if day.weekday() > 4:
            flags.append("WEEKEND_DATE_CONFLICT")
        result[key] = dict(date=key, open=o, high=h, low=l, close=c,
                           source="鉅亨 ZSCS／Refinitiv reference · DEFINITION_UNVERIFIED",
                           flag=";".join(flags))
    if not result:
        raise ValueError("No source OHLC; refuse to replace last-known-good")
    return sorted(result.values(), key=lambda row: row["date"])


def atomic_write(path: Path, text: str) -> None:
    fd, name = tempfile.mkstemp(dir=path.parent, prefix=".zscs-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(text)
        os.chmod(name, 0o600)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def import_saved(source: Path, destination: Path, *, today: date, accept_revisions=False) -> dict:
    source = outside_repo(source)
    destination = outside_repo(destination)
    text = source.read_text(encoding="utf-8-sig")
    incoming = parse_chart(text, today=today)
    archive_path = destination / "cnyes_zscs_private_archive.json"
    old = json.loads(archive_path.read_text()) if archive_path.exists() else {}
    if old and old.get("series") != SERIES:
        raise ValueError("Archive identity mismatch")
    existing = {r["date"]: r for r in old.get("rows", [])}
    revisions = list(old.get("revisions", []))
    now = datetime.now(timezone.utc).isoformat()
    for row in incoming:
        previous = existing.get(row["date"])
        if previous is not None and previous != row:
            if not accept_revisions:
                raise ValueError("Historical revision requires --accept-revisions")
            revisions.append(dict(date=row["date"], previous=previous, replacement=row, recorded_at=now))
        existing[row["date"]] = row
    rows = sorted(existing.values(), key=lambda r: r["date"])
    archive = dict(series=SERIES, source_url=SOURCE, currency="USD", unit="USD/t",
                   basis="UNVERIFIED_CASH_REFERENCE", session="UNVERIFIED", timezone="UNVERIFIED",
                   usage_permission="UNCONFIRMED", strategy_enabled=False, calendar_audit="PARTIAL",
                   fetched_at=None, imported_at=now,
                   source_sha256=hashlib.sha256(text.encode()).hexdigest(), rows=rows, revisions=revisions)
    template = (ROOT / "tools/private_zscs_chart.html").read_text()
    chart = template.replace("__ZSCS_ROWS__", json.dumps(rows, ensure_ascii=False).replace("<", "\\u003c"))
    chart = chart.replace("__GENERATED_AT__", now)
    destination.mkdir(parents=True, exist_ok=True, mode=0o700)
    atomic_write(archive_path, json.dumps(archive, ensure_ascii=False, indent=2))
    atomic_write(destination / "index.html", chart)
    return dict(status="IMPORTED_PRIVATE_REFERENCE", rows=len(rows), flagged=sum(bool(r["flag"]) for r in rows),
                strategy_enabled=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="Saved ZSCS chart-frame HTML")
    parser.add_argument("--private-dir", type=Path, required=True)
    parser.add_argument("--accept-revisions", action="store_true")
    args = parser.parse_args()
    # Source-date boundaries use the user's Taiwan date, not runner UTC.
    from zoneinfo import ZoneInfo
    result = import_saved(args.input, args.private_dir,
                          today=datetime.now(ZoneInfo("Asia/Taipei")).date(),
                          accept_revisions=args.accept_revisions)
    print(json.dumps(result))  # Counts only; never emit prices/raw rows.


if __name__ == "__main__":
    main()
