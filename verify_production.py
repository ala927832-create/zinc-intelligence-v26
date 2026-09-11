from __future__ import annotations

import html as html_lib
import json
import os
import re
import sys
import time
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen

SNAPSHOT_PATH = Path("data/latest_snapshot.json")


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if text:
            self.parts.append(text)


def _visible_text(raw_html: str) -> str:
    parser = _TextExtractor()
    parser.feed(raw_html)
    return " ".join(html_lib.unescape(x) for x in parser.parts)


def _norm(text: object) -> str:
    return re.sub(r"\s+", " ", str(text)).strip()


def _fmt(value, digits: int = 1) -> str:
    if value is None:
        return "—"
    return f"{float(value):,.{digits}f}"


def _cache_bust(url: str, run_id: str) -> str:
    parts = urlsplit(url)
    q = urlencode({"verify_run": run_id, "ts": int(time.time())})
    return urlunsplit((parts.scheme, parts.netloc, parts.path, q, parts.fragment))


def _fetch(url: str, run_id: str, attempts: int = 12, sleep_seconds: int = 10) -> str:
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        target = _cache_bust(url, run_id)
        req = Request(target, headers={
            "User-Agent": "ZincIntelligenceProductionVerifier/2.7.4",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        })
        try:
            with urlopen(req, timeout=30) as resp:
                body = resp.read().decode("utf-8", errors="replace")
                if resp.status == 200 and "ZINC INTELLIGENCE V2.7" in body:
                    print(f"production fetch ok: HTTP {resp.status}, attempt {attempt}")
                    return body
                last_error = RuntimeError(f"unexpected response HTTP {resp.status}; V2.7 marker={ 'ZINC INTELLIGENCE V2.7' in body }")
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            last_error = exc
        print(f"production not ready on attempt {attempt}: {last_error}")
        if attempt < attempts:
            time.sleep(sleep_seconds)
    raise RuntimeError(f"production page verification fetch failed after {attempts} attempts: {last_error}")


def _expect(text: str, token: str, failures: list[str], label: str | None = None) -> None:
    if _norm(token) not in _norm(text):
        failures.append(f"missing rendered token: {label or token!r} expected {token!r}")


def main() -> int:
    page_url = os.getenv("PRODUCTION_URL", "https://ala927832-create.github.io/zinc-intelligence-v26/")
    run_id = os.getenv("GITHUB_RUN_ID", "local")
    snapshot = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    market = snapshot.get("market", {})
    health = market.get("data_health", {})
    tc = snapshot.get("china_tc", {})
    gate = snapshot.get("core_data_gate", {})

    raw_html = _fetch(page_url, run_id)
    text = _visible_text(raw_html)
    failures: list[str] = []

    # Version and integrity markers.
    _expect(text, "Zn · ZINC INTELLIGENCE V2.7", failures)
    _expect(text, f"Model {snapshot.get('model_version')}", failures, "model version")
    _expect(text, str(gate.get("status", "—")), failures, "core data gate")
    _expect(text, "PAPER RESEARCH ONLY", failures)

    # LME core values must be visible, not only present in JSON.
    _expect(text, _fmt(market.get("lme_cash"), 1), failures, "LME Cash")
    _expect(text, _fmt(market.get("lme_3m"), 1), failures, "LME 3M")
    _expect(text, f"Cash−3M {_fmt(market.get('cash_3m'), 1)}", failures, "Cash-3M")
    _expect(text, _fmt(market.get("lme_inventory_t"), 0), failures, "inventory")
    _expect(text, f"Live {_fmt(market.get('live_warrants_t'), 0)}", failures, "live warrants")
    _expect(text, f"Cancelled {_fmt(market.get('cancelled_warrants_t'), 0)}", failures, "cancelled warrants")
    _expect(text, f"Ratio {_fmt(market.get('cancelled_ratio_pct'), 1)}%", failures, "cancelled ratio")

    # Data-health provenance, date and freshness must be rendered for every core field.
    for field in ["lme_cash", "lme_3m", "lme_inventory_t", "live_warrants_t", "cancelled_warrants_t"]:
        h = health.get(field, {})
        _expect(text, str(h.get("as_of") or "—"), failures, f"{field} as-of")
        _expect(text, str(h.get("expected_update") or "—"), failures, f"{field} expected update")
        _expect(text, str(h.get("source_grade") or "—"), failures, f"{field} source grade")
        _expect(text, str(h.get("source") or "—"), failures, f"{field} provider")
        _expect(text, str(h.get("freshness") or "—"), failures, f"{field} freshness")
        age = h.get("age_days")
        if age is not None:
            _expect(text, f"{float(age):.1f} d", failures, f"{field} age")

    # China TC series: value or explicit missing marker, unit, provenance, date,
    # cadence and freshness age must appear.  AVAILABLE/VERIFIED series are
    # required to carry age_days so a current-looking value cannot lose its date context.
    tc_specs = [
        ("import_weekly", "China Import TC · Weekly"),
        ("domestic_weekly", "China Domestic TC · Weekly"),
        ("domestic_monthly", "China Domestic TC · Monthly"),
        ("annual_benchmark", "Annual Benchmark TC"),
    ]
    for key, title in tc_specs:
        item = tc.get(key, {})
        _expect(text, title, failures)
        value = item.get("value")
        _expect(text, _fmt(value, 2) if value is not None else "—", failures, f"{key} value")
        _expect(text, str(item.get("unit") or "—"), failures, f"{key} unit")
        _expect(text, f"As of {item.get('as_of') or '—'}", failures, f"{key} as-of")
        _expect(text, str(item.get("expected_update") or "—"), failures, f"{key} cadence")
        _expect(text, str(item.get("source_grade") or "—"), failures, f"{key} source grade")
        _expect(text, str(item.get("source") or "—"), failures, f"{key} source")
        status = str(item.get("status") or "—")
        _expect(text, status, failures, f"{key} status")
        age = item.get("age_days")
        if age is not None:
            _expect(text, f"{float(age):.1f} d", failures, f"{key} age")
        elif status in {"AVAILABLE", "VERIFIED_REFERENCE"}:
            failures.append(f"snapshot governance failure: {key} has status {status} but no age_days")

    # Public privacy guarantee: exact internal inventory and demand must not be rendered.
    if not snapshot.get("privacy", {}).get("public_dashboard_include_private", False):
        _expect(text, "Public privacy mode", failures, "privacy banner")
        _expect(text, "•••• / ••••", failures, "masked procurement inputs")
        current_inventory = snapshot.get("procurement_state", {}).get("current_inventory_t")
        demand_60d = snapshot.get("procurement_state", {}).get("demand_60d_t")
        private_pair = f"{_fmt(current_inventory, 0)} / {_fmt(demand_60d, 0)}"
        if private_pair in _norm(text):
            failures.append("privacy failure: exact inventory / demand pair is visible on public page")

    if failures:
        print("PRODUCTION VERIFICATION FAILED")
        for failure in failures:
            print(f" - {failure}")
        return 1

    print("PRODUCTION VERIFICATION PASSED")
    print(f"verified URL: {page_url}")
    print(f"snapshot run_time: {snapshot.get('run_time')}")
    print(f"core gate: {gate.get('status')}")
    print(f"China import TC: {tc.get('import_weekly', {}).get('value')} {tc.get('import_weekly', {}).get('unit')}")
    print(f"China domestic weekly TC: {tc.get('domestic_weekly', {}).get('value')} {tc.get('domestic_weekly', {}).get('unit')}")
    print(f"China domestic monthly TC: {tc.get('domestic_monthly', {}).get('value')} {tc.get('domestic_monthly', {}).get('unit')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
