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
from urllib.parse import urlencode, urljoin, urlsplit, urlunsplit
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


class _IdBlockExtractor(HTMLParser):
    """Collect visible text from the element carrying an exact id."""

    VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}

    def __init__(self, target_id: str) -> None:
        super().__init__()
        self.target_id = target_id
        self.depth = 0
        self.current: list[str] | None = None
        self.block = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if self.current is not None:
            if tag not in self.VOID_TAGS:
                self.depth += 1
            return
        if any(key == "id" and value == self.target_id for key, value in attrs):
            self.current = []
            self.depth = 1

    def handle_data(self, data: str) -> None:
        if self.current is not None and data.strip():
            self.current.append(data.strip())

    def handle_endtag(self, tag: str) -> None:
        if self.current is None:
            return
        self.depth -= 1
        if self.depth == 0:
            self.block = " ".join(html_lib.unescape(x) for x in self.current)
            self.current = None


def _visible_text(raw_html: str) -> str:
    parser = _TextExtractor()
    parser.feed(raw_html)
    return " ".join(html_lib.unescape(x) for x in parser.parts)


def _class_blocks(raw_html: str, class_name: str) -> list[str]:
    parser = _ClassBlockExtractor(class_name)
    parser.feed(raw_html)
    return parser.blocks


def _id_block(raw_html: str, element_id: str) -> str:
    parser = _IdBlockExtractor(element_id)
    parser.feed(raw_html)
    return parser.block


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


def _fetch(url: str, run_id: str, attempts: int = 12, sleep_seconds: int = 10,
           marker: str = "GLOBAL MACRO RESEARCH DESK") -> str:
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
                if resp.status == 200 and marker in body:
                    print(f"production fetch ok: HTTP {resp.status}, attempt {attempt}")
                    return body
                last_error = RuntimeError(f"unexpected response HTTP {resp.status}; page marker={marker in body}")
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

    market_index = _fetch(urljoin(page_url, "markets.html"), run_id, marker="CHARTS BEFORE COMMENTARY")
    for label in ("事實｜", "解讀｜", "觀察｜", "entry-price", "market-us_treasury.html"):
        _expect(market_index, label, failures, f"Markets research entry {label}")
    market_pages = {}
    for key in ("lme_zinc", "shfe_zinc", "gold", "usdjpy", "dxy", "us_treasury"):
        _expect(market_index, f"market-{key}.html", failures, f"Markets route {key}")
        market_pages[key] = _fetch(urljoin(page_url, f"market-{key}.html"), run_id, marker="CHARTS BEFORE COMMENTARY")
    markets_html = "".join(market_pages.values())
    markets_text = _visible_text(markets_html)
    decisions = snapshot.get("decision_book", {}).get("markets", {})
    for key in ("lme_zinc", "shfe_zinc", "gold", "usdjpy", "dxy"):
        plan = decisions.get(key, {})
        if not plan:
            failures.append(f"missing required primary market plan: {key}")
            continue
        _expect(markets_html, f"id='{key}'", failures, f"Markets card {key}")
        for number, label in enumerate(("市場方向", "證據一致性", "風險位置", "准許進場條件",
                                        "看錯損失", "出場計畫", "理論風報比", "No-Trade 理由"), 1):
            _expect(markets_html, f"{number}. {label}", failures, f"{key} audit question {number}")
    for marker in ("CHARTS BEFORE COMMENTARY", "Markets · price structure and conditional plans",
                   "Decision brief · eight required questions", "Asset-specific evidence",
                   "Conditional plan · RESEARCH ONLY", "Execution approval boundary",
                   "US Treasury · data source not integrated"):
        _expect(markets_html, marker, failures, f"Markets decision chain: {marker}")
    if markets_html.find("chart-first") > markets_html.find("Asset-specific evidence"):
        failures.append("Markets must render chart-first content before evidence commentary")
    for period in ("20D", "60D", "120D", "1Y", "ALL"):
        _expect(markets_html, period, failures, f"Markets chart period {period}")
    _expect(markets_html, "data-indicator='RSI14'", failures, "Markets close-based RSI14 chart")
    _expect(markets_html, "Separate China-market contract for cross-market confirmation", failures,
            "LME/SHFE market identity boundary")
    for obsolete_section in ("Market comparison · first decision layer", "CROSS-MARKET DECISION MATRIX"):
        if obsolete_section in markets_html or obsolete_section in raw_html:
            failures.append(f"obsolete repeated comparison remains: {obsolete_section}")
    for key, page in market_pages.items():
        if key != "us_treasury" and page.count("Execution approval boundary") != 1:
            failures.append(f"{key} must render the execution boundary exactly once")
    for private_marker in ("name=\"account_equity\"", "name='account_equity'", "/api/execution/preview", "/api/trades"):
        if private_marker in markets_html:
            failures.append(f"private execution control rendered publicly: {private_marker}")
    chart_src = "assets/candle_daily.png"
    if chart_src in raw_html or "assets/candle_weekly.png" in raw_html:
        failures.append("private candle element rendered on public page")

    # Version and integrity markers.
    _expect(text, "GLOBAL MACRO RESEARCH DESK", failures)
    _expect(text, f"Model {snapshot.get('model_version')}", failures, "model version")
    _expect(text, str(gate.get("status", "—")), failures, "core data gate")
    for marker in ("MARKET SNAPSHOT", "FIRST LOOK · PRICES BEFORE OPINIONS", "TODAY'S MARKET POSTURE",
                   "TODAY'S LARGEST MOVES / CONDITIONS", "1D", "5D", "20D", "vs EMA20",
                   "Next trigger", "今日重點", "PRIMARY WATCH", "US TREASURY 10Y", "SOURCE PENDING",
                   "LME ZINC · CONTEXT SPLIT", "WHAT PERMITS ACTION", "RESEARCH ONLY"):
        _expect(text, marker, failures, f"Today information architecture: {marker}")
    _expect(raw_html, "class='side-nav'", failures, "left research navigation")
    for section_id in ("overview", "data-health"):
        _expect(raw_html, f"id='{section_id}'", failures, f"Today section {section_id}")
    for obsolete_anchor in ("#market-research", "#shfe-zinc", "#inventory", "#tc-premiums", "#methodology"):
        if f"href='{obsolete_anchor}'" in raw_html:
            failures.append(f"obsolete mixed page/anchor navigation remains: {obsolete_anchor}")

    shfe = snapshot.get("market_research", {}).get("shfe_zinc", {})
    if shfe.get("status") == "AVAILABLE":
        shfe_block = _id_block(markets_html, "shfe_zinc")
        _expect(shfe_block, "SHFE Zinc", failures, "SHFE panel identity")
        _expect(shfe_block, str(shfe.get("as_of")), failures, "SHFE latest date")
        _expect(shfe_block, str(shfe.get("latest_contract")), failures, "SHFE contract")
        _expect(shfe_block, str(shfe.get("observations")), failures, "SHFE observations")
        _expect(markets_html, "data-chart-mode='OHLC'", failures, "SHFE candlestick chart")

    # The LME detail is the single source of truth for price structure, indicators and physical context.
    lme_block = _id_block(markets_html, "lme_zinc")
    research = snapshot.get("market_research", {}).get("close_series", {})
    _expect(lme_block, str(research.get("as_of") or "—"), failures, "LME close series date")
    _expect(lme_block, str(research.get("source") or "—"), failures, "LME close series source")
    _expect(lme_block, str(research.get("observations", 0)), failures, "LME close series count")
    _expect(lme_block, str(research.get("coverage_start") or "—"), failures, "LME coverage start")
    _expect(lme_block, str(research.get("coverage_end") or "—"), failures, "LME coverage end")
    for label, value in (("Close", research.get("latest_close")), ("SMA14", research.get("sma_14")),
                         ("SMA30", research.get("sma_30")), ("EMA20", research.get("ema_20")),
                         ("RSI14", research.get("rsi_14"))):
        _expect(lme_block, label, failures, f"LME indicator label {label}")
        _expect(lme_block, str(value if value is not None else "—"), failures, f"LME indicator {label}")
    _expect(markets_html, "data-chart-mode='CLOSE_ONLY'", failures, "LME close-only chart")
    for field, label in (("lme_cash", "LME Cash"), ("lme_3m", "LME 3M"),
                         ("lme_inventory_t", "Opening / Total Stock"), ("live_warrants_t", "Live Warrants"),
                         ("cancelled_warrants_t", "Cancelled Warrants")):
        h = health.get(field, {})
        _expect(lme_block, label, failures, f"LME physical field {label}")
        _expect(lme_block, str(market.get(field) if market.get(field) is not None else "—"), failures, f"{label} value")
        _expect(lme_block, str(h.get("as_of") or "—"), failures, f"{label} as-of")
        _expect(lme_block, str(h.get("source_grade") or "—"), failures, f"{label} source grade")

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

    # China TC series are verified row-by-row inside the LME physical appendix.
    tc_specs = [
        ("import_weekly", "China Import TC · Weekly"),
        ("domestic_weekly", "China Domestic TC · Weekly"),
        ("domestic_monthly", "China Domestic TC · Monthly"),
        ("annual_benchmark", "Annual Benchmark TC"),
    ]
    for key, title in tc_specs:
        item = tc.get(key, {})
        row = _table_row_text(markets_html, title)
        if not row:
            failures.append(f"missing rendered TC row: {title}")
            continue
        value = item.get("value")
        _expect(row, str(value) if value is not None else "—", failures, f"{key} value")
        _expect(row, str(item.get("unit") or "—"), failures, f"{key} unit")
        _expect(row, str(item.get("as_of") or "—"), failures, f"{key} as-of")
        _expect(row, str(item.get("expected_update") or "—"), failures, f"{key} cadence")
        _expect(row, str(item.get("source_grade") or "—"), failures, f"{key} source grade")
        _expect(row, str(item.get("source") or "—"), failures, f"{key} source")
        status = str(item.get("status") or "—")
        _expect(row, status, failures, f"{key} status")
        age = item.get("age_days")
        if age is not None:
            _expect(row, f"{age} d", failures, f"{key} age")
        elif status in {"AVAILABLE", "VERIFIED_REFERENCE"}:
            failures.append(f"snapshot governance failure: {key} has status {status} but no age_days")

    # Public privacy guarantee: exact internal inventory and demand must not be rendered.
    if not snapshot.get("privacy", {}).get("public_dashboard_include_private", False):
        _expect(lme_block, "Public privacy mode", failures, "privacy boundary")
        current_inventory = snapshot.get("procurement_state", {}).get("current_inventory_t")
        demand_60d = snapshot.get("procurement_state", {}).get("demand_60d_t")
        private_pair = f"{_fmt(current_inventory, 0)} / {_fmt(demand_60d, 0)}"
        public_text = _norm(text + " " + markets_text)
        if private_pair in public_text:
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
