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


class _ClassBlockExtractor(HTMLParser):
    """Collect visible text for each element carrying a target CSS class.

    Production verification must prove that value/provenance tokens are rendered
    together in the intended card, not merely somewhere else on the page.
    """

    def __init__(self, target_class: str) -> None:
        super().__init__()
        self.target_class = target_class
        self.depth = 0
        self.current: list[str] | None = None
        self.blocks: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if self.current is not None:
            self.depth += 1
            return
        classes = ""
        for key, value in attrs:
            if key == "class" and value:
                classes = value
                break
        if self.target_class in classes.split():
            self.current = []
            self.depth = 1

    def handle_data(self, data: str) -> None:
        if self.current is not None:
            text = data.strip()
            if text:
                self.current.append(text)

    def handle_endtag(self, tag: str) -> None:
        if self.current is None:
            return
        self.depth -= 1
        if self.depth == 0:
            self.blocks.append(" ".join(html_lib.unescape(x) for x in self.current))
            self.current = None


def _visible_text(raw_html: str) -> str:
    parser = _TextExtractor()
    parser.feed(raw_html)
    return " ".join(html_lib.unescape(x) for x in parser.parts)


def _class_blocks(raw_html: str, class_name: str) -> list[str]:
    parser = _ClassBlockExtractor(class_name)
    parser.feed(raw_html)
    return parser.blocks


def _table_row_text(raw_html: str, label: str) -> str:
    for block in re.findall(r"<tr\b[^>]*>(.*?)</tr>", raw_html, flags=re.IGNORECASE | re.DOTALL):
        text = _visible_text(block)
        if _norm(label) in _norm(text):
            return text
    return ""


def _find_block(blocks: list[str], marker: str) -> str:
    marker_norm = _norm(marker)
    for block in blocks:
        if marker_norm in _norm(block):
            return block
    return ""


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
            "User-Agent": "ZincIntelligenceProductionVerifier/2.7.5",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        })
        try:
            with urlopen(req, timeout=30) as resp:
                body = resp.read().decode("utf-8", errors="replace")
                if resp.status == 200 and "ZINC RESEARCH COCKPIT" in body:
                    print(f"production fetch ok: HTTP {resp.status}, attempt {attempt}")
                    return body
                last_error = RuntimeError(f"unexpected response HTTP {resp.status}; cockpit marker={ 'ZINC RESEARCH COCKPIT' in body }")
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
    chart_src = "assets/candle_daily.png"
    if chart_src in raw_html or "assets/candle_weekly.png" in raw_html:
        failures.append("private candle element rendered on public page")

    # Version and integrity markers.
    _expect(text, "Zn · ZINC RESEARCH COCKPIT", failures)
    _expect(text, f"Model {snapshot.get('model_version')}", failures, "model version")
    _expect(text, str(gate.get("status", "—")), failures, "core data gate")
    _expect(text, "FUNDAMENTAL / PROCUREMENT REGIME", failures, "fundamental regime label")
    _expect(text, "Close-only 技術趨勢", failures, "regime boundary explanation")
    _expect(text, "PAPER RESEARCH ONLY", failures)
    _expect(raw_html, "class='side-nav'", failures, "left research navigation")
    _expect(raw_html, "class='compass-gauge'", failures, "semicircular trend compass")
    _expect(raw_html, "class='trend-band'", failures, "five-color trend regime band")
    for section_id in ("overview", "market-research", "shfe-zinc", "inventory", "tc-premiums", "data-health", "notes", "methodology"):
        _expect(raw_html, f"id='{section_id}'", failures, f"navigation target {section_id}")

    shfe = snapshot.get("market_research", {}).get("shfe_zinc", {})
    if shfe.get("status") == "AVAILABLE":
        _expect(text, "SHFE ZINC · TRUE DAILY OHLC", failures, "SHFE panel identity")
        _expect(text, str(shfe.get("as_of")), failures, "SHFE latest date")
        _expect(text, str(shfe.get("latest_contract")), failures, "SHFE contract")
        _expect(text, str(shfe.get("observations")), failures, "SHFE observations")
        _expect(raw_html, "shfe-chart-data", failures, "SHFE chart payload")

    # A descriptive research panel must match the same deployed snapshot.
    research_section = re.search(r"<section\b[^>]*id=['\"]market-research['\"][^>]*>(.*?)</section>",
                                 raw_html, flags=re.IGNORECASE | re.DOTALL)
    if not research_section:
        failures.append("missing market research panel")
    else:
        research_text = _visible_text(research_section.group(1))
        research = snapshot.get("market_research", {}).get("close_series", {})
        _expect(research_text, str(research.get("as_of") or "—"), failures, "close series date")
        _expect(research_text, str(research.get("source") or "—"), failures, "close series source")
        _expect(research_text, str(research.get("observations", 0)), failures, "close series count")
        _expect(research_text, str(research.get("coverage_start") or "—"), failures, "coverage start")
        _expect(research_text, str(research.get("coverage_end") or "—"), failures, "coverage end")
        _expect(research_section.group(1), "Long-term LME zinc 3M reference Close with moving averages by trading day", failures, "long-term close chart")
        _expect(research_section.group(1), f"data-chart-points='{len(research.get('chart_points') or [])}'", failures, "close chart point count")
        chart_points = research.get("chart_points") or []
        if chart_points:
            _expect(research_text, "交易日時間軸", failures, "trading-day axis label")
            _expect(research_text, str(chart_points[0].get("date")), failures, "chart first trading date")
            _expect(research_text, str(chart_points[-1].get("date")), failures, "chart last trading date")
            _expect(research_text, f"第 1/{len(chart_points)} 交易日", failures, "chart first trading-day index")
            _expect(research_text, f"第 {len(chart_points)}/{len(chart_points)} 交易日", failures, "chart last trading-day index")
        _expect(research_text, "週收盤價區間圖", failures, "weekly close-range chart")
        _expect(research_text, "非真實 OHLC／週 K", failures, "weekly close-range disclosure")
        _expect(research_text, str(research.get("open_status") or "—"), failures, "Open source status")
        for days in (20, 60, 120):
            _expect(research_section.group(1), f"data-close-days='{days}'", failures, f"{days}-day chart control")
        trend = research.get("trend") or {}
        _expect(research_text, str(trend.get("regime") or "INSUFFICIENT_DATA"), failures, "trend regime")
        _expect(research_text, str(trend.get("score") if trend.get("score") is not None else "—"), failures, "trend score")
        _expect(research_text, str(trend.get("persistence_days", 0)), failures, "trend persistence")
        _expect(research_text, str(trend.get("data_confidence") or "LOW"), failures, "trend data confidence")
        for field, min_sessions in (("latest_close", 1), ("sma_14", 14), ("sma_30", 30), ("ema_20", 20), ("rsi_14", 15)):
            value = research.get(field)
            expected = _fmt(value, 2) if value is not None and research.get("close_indicator_sessions", 0) >= min_sessions else "資料不足"
            _expect(research_text, expected, failures, f"close-only {field}")
        for length in (20, 60):
            _expect(research_text, _fmt(research.get(f"volatility_{length}_pct"), 2),
                    failures, f"historical volatility {length}")

    # Verify the core figures inside their actual KPI cards, so the deployment
    # cannot pass merely because the same number appears elsewhere on the page.
    market_cards = _class_blocks(raw_html, "mcard")
    cash_card = _find_block(market_cards, "Cash−3M")
    three_m_card = _find_block(market_cards, "Technical mode")
    inventory_card = _find_block(market_cards, "Cancelled")

    _expect(cash_card, _fmt(market.get("lme_cash"), 1), failures, "LME Cash card value")
    _expect(cash_card, f"Cash−3M {_fmt(market.get('cash_3m'), 1)}", failures, "Cash-3M card value")
    _expect(three_m_card, _fmt(market.get("lme_3m"), 1), failures, "LME 3M card value")
    _expect(inventory_card, _fmt(market.get("lme_inventory_t"), 0), failures, "inventory card value")
    _expect(inventory_card, f"Live {_fmt(market.get('live_warrants_t'), 0)}", failures, "live warrants card value")
    _expect(inventory_card, f"Cancelled {_fmt(market.get('cancelled_warrants_t'), 0)}", failures, "cancelled warrants card value")
    _expect(inventory_card, f"Ratio {_fmt(market.get('cancelled_ratio_pct'), 1)}%", failures, "cancelled ratio card value")

    # The headline cards must retain their visible date/age/source-grade context.
    for card, field, label in [
        (cash_card, "lme_cash", "LME Cash card"),
        (three_m_card, "lme_3m", "LME 3M card"),
        (inventory_card, "lme_inventory_t", "Inventory card"),
    ]:
        h = health.get(field, {})
        _expect(card, str(h.get("as_of") or "—"), failures, f"{label} as-of")
        _expect(card, str(h.get("source_grade") or "—"), failures, f"{label} source grade")
        age = h.get("age_days")
        if age is not None:
            _expect(card, f"{float(age):.1f} d", failures, f"{label} age")

    # Data-health provenance must be correct in each field's own table row.
    # This prevents a source/date token belonging to one series from satisfying
    # another series' verification by accident.
    health_labels = {
        "lme_cash": "LME Cash",
        "lme_3m": "LME 3M",
        "lme_inventory_t": "Opening / Total Stock",
        "live_warrants_t": "Live Warrants",
        "cancelled_warrants_t": "Cancelled Warrants",
    }
    for field, row_label in health_labels.items():
        h = health.get(field, {})
        row_text = _table_row_text(raw_html, row_label)
        if not row_text:
            failures.append(f"missing rendered data-health row: {row_label}")
            continue
        _expect(row_text, str(h.get("as_of") or "—"), failures, f"{field} as-of")
        _expect(row_text, str(h.get("expected_update") or "—"), failures, f"{field} expected update")
        _expect(row_text, str(h.get("source_grade") or "—"), failures, f"{field} source grade")
        _expect(row_text, str(h.get("source") or "—"), failures, f"{field} provider")
        _expect(row_text, str(h.get("freshness") or "—"), failures, f"{field} freshness")
        age = h.get("age_days")
        if age is not None:
            _expect(row_text, f"{float(age):.1f} d", failures, f"{field} age")

    # China TC series are verified card-by-card, preserving their different
    # units/bases and preventing provenance from one TC series satisfying another.
    tc_cards = _class_blocks(raw_html, "tc-card")
    tc_specs = [
        ("import_weekly", "China Import TC · Weekly"),
        ("domestic_weekly", "China Domestic TC · Weekly"),
        ("domestic_monthly", "China Domestic TC · Monthly"),
        ("annual_benchmark", "Annual Benchmark TC"),
    ]
    for key, title in tc_specs:
        item = tc.get(key, {})
        card = _find_block(tc_cards, title)
        if not card:
            failures.append(f"missing rendered TC card: {title}")
            continue
        value = item.get("value")
        _expect(card, _fmt(value, 2) if value is not None else "—", failures, f"{key} value")
        _expect(card, str(item.get("unit") or "—"), failures, f"{key} unit")
        _expect(card, f"As of {item.get('as_of') or '—'}", failures, f"{key} as-of")
        _expect(card, str(item.get("expected_update") or "—"), failures, f"{key} cadence")
        _expect(card, str(item.get("source_grade") or "—"), failures, f"{key} source grade")
        _expect(card, str(item.get("source") or "—"), failures, f"{key} source")
        status = str(item.get("status") or "—")
        _expect(card, status, failures, f"{key} status")
        age = item.get("age_days")
        if age is not None:
            _expect(card, f"{float(age):.1f} d", failures, f"{key} age")
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
