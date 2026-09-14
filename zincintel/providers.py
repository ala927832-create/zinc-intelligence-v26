from __future__ import annotations

import io
import json
import os
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import pandas as pd
import requests
try:
    import yfinance as yf
except Exception:
    yf = None

from .utils import DATA_DIR, iso_now, read_json, safe_float

CORE_KEYS = [
    "lme_cash", "lme_3m", "lme_inventory_t", "cancelled_warrants_t",
    "tc_usd_t", "physical_premium_usd_t", "smelter_margin_usd_t",
    "china_demand_yoy_pct", "global_balance_kt", "smelter_utilization_pct",
]
EXTRA_KEYS = [
    "lme_cash_bid", "lme_cash_offer", "lme_3m_bid", "lme_3m_offer",
    "lme_settlement", "lme_closing_stock_t", "live_warrants_t",
    "delivered_in_t", "delivered_out_t", "tc_smelter_usd_t",
    "tc_trader_usd_t", "tc_annual_benchmark_usd_t",
]


def _f(value: Any) -> float | None:
    return safe_float(value)


def _first(*values: Any) -> float | None:
    for value in values:
        x = _f(value)
        if x is not None:
            return x
    return None


def _mid(bid: Any, ask: Any) -> float | None:
    b, a = _f(bid), _f(ask)
    if b is not None and a is not None:
        return (b + a) / 2
    return b if b is not None else a


def _record(out: dict, sources: dict, provider: str, status: str, as_of: str | None, values: dict) -> None:
    for key, value in values.items():
        if value is not None and out.get(key) is None:
            out[key] = value
            sources[key] = {"provider": provider, "status": status, "as_of": as_of}


class LmeXmlAdapter:
    """Licensed LME Next-Day XML: OFS prices + WSM warehouse stocks."""

    TOKEN_URL = "https://sso.lmelive.com/as/token.oauth2"
    FEED_URL = "https://ndxml.lmelive.com/XMLFeed.svc/lme.xml"
    CONTRACT = "ZS"

    def __init__(self) -> None:
        self.username = os.getenv("LME_XML_USERNAME", "").strip()
        self.password = os.getenv("LME_XML_PASSWORD", "").strip()
        self.client_id = os.getenv("LME_XML_CLIENT_ID", "xmlfeeds").strip() or "xmlfeeds"
        self.timeout = int(os.getenv("LME_XML_TIMEOUT_SECONDS", "20"))
        self.session = requests.Session()
        self._token: str | None = None

    @property
    def configured(self) -> bool:
        return bool(self.username and self.password)

    def _get_token(self) -> str:
        if self._token:
            return self._token
        r = self.session.post(
            self.TOKEN_URL,
            data={
                "grant_type": "password", "client_id": self.client_id,
                "username": self.username, "password": self.password,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=self.timeout,
        )
        r.raise_for_status()
        token = r.json().get("access_token")
        if not token:
            raise ValueError("LME token response missing access_token")
        self._token = str(token)
        return self._token

    def _request(self, report_type: str) -> ET.Element:
        r = self.session.get(
            self.FEED_URL,
            params={"contract": self.CONTRACT, "type": report_type, "date": 1},
            headers={"Authorization": f"Bearer {self._get_token()}"},
            timeout=self.timeout,
        )
        r.raise_for_status()
        root = ET.fromstring(r.content)
        if root.attrib.get("status") not in (None, "0"):
            raise ValueError(root.findtext("reason") or "LME XML request failed")
        return root

    @staticmethod
    def parse_ofs(root: ET.Element) -> tuple[dict, str | None]:
        row = next((x for x in root.findall(".//row_official") if x.attrib.get("code", "").upper() == "ZS"), None)
        if row is None:
            return {}, root.findtext("date")
        settlement = _f(row.findtext("settlement"))
        cash_bid = cash_ask = m3_bid = m3_ask = None
        for item in row.findall("of_item"):
            prompt = (item.attrib.get("prompt_date") or "").upper()
            if prompt == "CASH":
                cash_bid, cash_ask = _f(item.findtext("bid")), _f(item.findtext("ask"))
            elif prompt == "3M":
                m3_bid, m3_ask = _f(item.findtext("bid")), _f(item.findtext("ask"))
        return {
            "lme_cash": _first(settlement, cash_ask, _mid(cash_bid, cash_ask)),
            "lme_3m": _first(m3_ask, _mid(m3_bid, m3_ask)),
            "lme_cash_bid": cash_bid, "lme_cash_offer": cash_ask,
            "lme_3m_bid": m3_bid, "lme_3m_offer": m3_ask,
            "lme_settlement": settlement,
        }, root.findtext("date")

    @staticmethod
    def parse_wsm(root: ET.Element) -> tuple[dict, str | None]:
        totals: dict[str, float] = {}
        for row in root.findall(".//row_wsm"):
            if row.attrib.get("code", "").upper() != "ZS":
                continue
            if (row.findtext("location") or "").strip() or (row.findtext("grade_code") or "").strip():
                continue
            status = (row.findtext("stock_status") or "").strip()
            qty = _f(row.findtext("stock_qty"))
            if status and qty is not None:
                totals[status] = qty
        ident = root.find(".//wsmreport/identification")
        as_of = ident.attrib.get("report_date") if ident is not None else root.findtext("date")
        return {
            "lme_inventory_t": _first(totals.get("I"), totals.get("S")),
            "lme_closing_stock_t": totals.get("S"),
            "live_warrants_t": totals.get("e"),
            "cancelled_warrants_t": totals.get("f"),
            "delivered_in_t": totals.get("J"),
            "delivered_out_t": totals.get("K"),
        }, as_of

    def prices(self) -> tuple[dict, str | None, str, str | None]:
        if not self.configured:
            return {}, None, "NOT_CONFIGURED", None
        try:
            values, as_of = self.parse_ofs(self._request("OFS"))
            return values, as_of, "OFFICIAL_NEXT_DAY", None
        except Exception as exc:
            return {}, None, "ERROR", str(exc)

    def warehouse(self) -> tuple[dict, str | None, str, str | None]:
        if not self.configured:
            return {}, None, "NOT_CONFIGURED", None
        try:
            values, as_of = self.parse_wsm(self._request("WSM"))
            return values, as_of, "OFFICIAL_NEXT_DAY", None
        except Exception as exc:
            return {}, None, "ERROR", str(exc)


class WarehouseFileAdapter:
    """Fallback official/licensed warehouse XLSX/CSV adapter."""

    def fetch(self) -> tuple[dict, str | None, str, str | None]:
        source = os.getenv("LME_WAREHOUSE_REPORT_URL", "").strip() or os.getenv(
            "LME_WAREHOUSE_REPORT_FILE", "data/lme_warehouse_stock.xlsx"
        ).strip()
        try:
            if source.startswith(("http://", "https://")):
                r = requests.get(source, timeout=30)
                r.raise_for_status()
                content = r.content
            else:
                p = Path(source)
                if not p.is_absolute():
                    p = Path(__file__).resolve().parents[1] / p
                if not p.exists():
                    return {}, None, "MISSING", f"{p} not found"
                content = p.read_bytes()
            frames: list[pd.DataFrame] = []
            if source.lower().split("?", 1)[0].endswith(".csv"):
                frames = [pd.read_csv(io.BytesIO(content))]
            else:
                book = pd.ExcelFile(io.BytesIO(content))
                for sheet in book.sheet_names:
                    for header in range(0, 6):
                        try:
                            frames.append(pd.read_excel(book, sheet_name=sheet, header=header))
                        except Exception:
                            pass
            for df in frames:
                values = self._extract(df)
                if values:
                    return values, iso_now(), "OFFICIAL_OR_LICENSED_FILE", None
            return {}, None, "MISSING", "Zinc stock columns not found"
        except Exception as exc:
            return {}, None, "ERROR", str(exc)

    @staticmethod
    def _extract(df: pd.DataFrame) -> dict:
        if df is None or df.empty:
            return {}
        norm = {"".join(ch.lower() for ch in str(c) if ch.isalnum()): c for c in df.columns}
        def col(*parts: str) -> str | None:
            for k, original in norm.items():
                if any(p in k for p in parts):
                    return original
            return None
        metal = col("metal", "commodity", "contract", "product")
        work = df.copy()
        if metal:
            mask = work[metal].astype(str).str.upper().str.contains(r"\bZS\b|ZINC", regex=True, na=False)
            if mask.any():
                work = work[mask]
            else:
                return {}
        elif len(work) > 1:
            return {}
        mapping = {
            "lme_inventory_t": ("openingstock", "opening"),
            "lme_closing_stock_t": ("closingstock", "closing"),
            "live_warrants_t": ("livewarrant", "openwarrant", "opentonnage", "live"),
            "cancelled_warrants_t": ("cancelledwarrant", "canceledwarrant", "cancelledtonnage", "cancelled", "canceled"),
            "delivered_in_t": ("deliveredin", "stockin"),
            "delivered_out_t": ("deliveredout", "stockout"),
        }
        out: dict[str, float | None] = {}
        for field, patterns in mapping.items():
            c = col(*patterns)
            s = pd.to_numeric(work[c], errors="coerce").dropna() if c else pd.Series(dtype=float)
            out[field] = float(s.sum()) if not s.empty else None
        if out.get("lme_inventory_t") is None:
            out["lme_inventory_t"] = out.get("lme_closing_stock_t")
        return out if any(v is not None for v in out.values()) else {}


class TcAdapter:
    """TC API -> local CSV. Licensed vendor schemas are normalized at the gateway."""

    @staticmethod
    def _normalize(raw: dict) -> dict:
        smelter = _first(raw.get("tc_smelter_usd_t"), raw.get("smelter_tc"), raw.get("smelter_mid"))
        trader = _first(raw.get("tc_trader_usd_t"), raw.get("trader_tc"), raw.get("trader_mid"))
        legacy = _first(raw.get("tc_usd_t"), raw.get("tc"), raw.get("spot_tc"))
        return {
            "tc_usd_t": _first(smelter, legacy, trader),
            "tc_smelter_usd_t": smelter,
            "tc_trader_usd_t": trader,
            "tc_annual_benchmark_usd_t": _first(raw.get("tc_annual_benchmark_usd_t"), raw.get("annual_benchmark")),
        }

    def fetch(self) -> tuple[dict, str | None, str, str | None]:
        url, key = os.getenv("TC_API_URL", "").strip(), os.getenv("TC_API_KEY", "").strip()
        if url:
            try:
                header = os.getenv("TC_API_AUTH_HEADER", "Authorization")
                prefix = os.getenv("TC_API_AUTH_PREFIX", "Bearer")
                headers = {header: f"{prefix} {key}".strip()} if key else {}
                r = requests.get(url, headers=headers, timeout=20)
                r.raise_for_status()
                raw = r.json()
                if isinstance(raw, list):
                    raw = raw[-1] if raw else {}
                if isinstance(raw, dict):
                    values = self._normalize(raw)
                    if any(v is not None for v in values.values()):
                        return values, str(raw.get("as_of") or raw.get("date") or iso_now()), "LIVE_OR_LICENSED", None
            except Exception as exc:
                api_error = str(exc)
            else:
                api_error = "no TC fields"
        else:
            api_error = None
        p = Path(os.getenv("TC_CSV_FILE", "data/tc_manual.csv"))
        if not p.is_absolute():
            p = Path(__file__).resolve().parents[1] / p
        if p.exists():
            try:
                df = pd.read_csv(p)
                if not df.empty:
                    date_col = next((c for c in df.columns if c.lower() in {"date", "as_of", "timestamp"}), None)
                    if date_col:
                        df["_dt"] = pd.to_datetime(df[date_col], errors="coerce", utc=True)
                        df = df.sort_values("_dt")
                    raw = df.iloc[-1].to_dict()
                    values = self._normalize(raw)
                    if any(v is not None for v in values.values()):
                        return values, str(raw.get(date_col) if date_col else iso_now()), "MANUAL_CSV", api_error
            except Exception as exc:
                return {}, None, "ERROR", "; ".join(x for x in [api_error, str(exc)] if x)
        return {}, None, "MISSING", api_error


def _generic_market() -> tuple[dict, str | None, str, str | None]:
    url, key = os.getenv("ZINC_MARKET_API_URL", "").strip(), os.getenv("ZINC_MARKET_API_KEY", "").strip()
    if not url:
        return {}, None, "NOT_CONFIGURED", None
    try:
        headers = {"Authorization": f"Bearer {key}"} if key else {}
        r = requests.get(url, headers=headers, timeout=15)
        r.raise_for_status()
        raw = r.json()
        if not isinstance(raw, dict):
            raise ValueError("market API must return JSON object")
        return {k: _f(raw.get(k)) for k in CORE_KEYS + EXTRA_KEYS}, str(raw.get("as_of") or iso_now()), "API", None
    except Exception as exc:
        return {}, None, "ERROR", str(exc)


def fetch_market_snapshot() -> dict:
    """Field-level chain: LME XML -> Warehouse -> TC -> generic API -> manual fallback."""
    out = {k: None for k in CORE_KEYS + EXTRA_KEYS}
    sources: dict[str, dict] = {}
    provider_status: dict[str, dict] = {}

    lme = LmeXmlAdapter()
    steps = [
        ("lme_xml_ofs", lme.prices()),
        ("lme_xml_wsm", lme.warehouse()),
        ("lme_warehouse_report", WarehouseFileAdapter().fetch()),
        ("tc", TcAdapter().fetch()),
        ("generic_market_api", _generic_market()),
    ]
    manual = read_json(DATA_DIR / "manual_market.json", {})
    steps.append(("manual_market", ({k: _f(manual.get(k)) for k in CORE_KEYS + EXTRA_KEYS}, str(manual.get("as_of") or iso_now()), "MANUAL_FALLBACK", None)))

    first_as_of = None
    for name, (values, as_of, status, error) in steps:
        provider_status[name] = {"status": status, "as_of": as_of, "error": error}
        if as_of and first_as_of is None:
            first_as_of = as_of
        _record(out, sources, name, status, as_of, values)

    out["as_of"] = first_as_of or iso_now()
    out["source"] = "adapter_chain"
    out["field_sources"] = sources
    out["provider_status"] = provider_status
    out["cash_3m"] = out["lme_cash"] - out["lme_3m"] if out["lme_cash"] is not None and out["lme_3m"] is not None else None
    stock = _first(out.get("lme_inventory_t"), out.get("lme_closing_stock_t"))
    out["cancelled_ratio_pct"] = out["cancelled_warrants_t"] / stock * 100 if stock not in (None, 0) and out["cancelled_warrants_t"] is not None else None
    return out


def fetch_macro(tickers: dict[str, str]) -> dict[str, dict[str, Any]]:
    results: dict[str, dict[str, Any]] = {}
    if yf is None:
        return {name: {"value": None, "change_pct": None, "ticker": ticker, "status": "MISSING", "error": "yfinance not installed"} for name, ticker in tickers.items()}
    for name, ticker in tickers.items():
        try:
            df = yf.download(ticker, period="7d", interval="1d", auto_adjust=True, progress=False, timeout=12)
            if df is None or df.empty:
                raise ValueError("empty response")
            close = df["Close"]
            if isinstance(close, pd.DataFrame):
                close = close.iloc[:, 0]
            close = pd.to_numeric(close, errors="coerce").dropna()
            latest = float(close.iloc[-1])
            previous = float(close.iloc[-2]) if len(close) >= 2 else None
            change = ((latest / previous) - 1) * 100 if previous not in (None, 0) else None
            results[name] = {"value": latest, "change_pct": change, "ticker": ticker, "status": "LIVE_OR_DELAYED_PUBLIC"}
        except Exception as exc:
            results[name] = {"value": None, "change_pct": None, "ticker": ticker, "status": "MISSING", "error": str(exc)}
    return results


def _read_table(source: str, api_key: str = "") -> pd.DataFrame:
    if source.startswith(("http://", "https://")):
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        r = requests.get(source, headers=headers, timeout=30)
        r.raise_for_status()
        content, ctype, name = r.content, (r.headers.get("Content-Type") or "").lower(), source.lower().split("?", 1)[0]
    else:
        p = Path(source)
        if not p.is_absolute():
            p = Path(__file__).resolve().parents[1] / p
        if not p.exists():
            return pd.DataFrame()
        content, ctype, name = p.read_bytes(), "", p.name.lower()
    if name.endswith((".xlsx", ".xls")) or "excel" in ctype or "spreadsheet" in ctype:
        return pd.read_excel(io.BytesIO(content))
    if name.endswith(".json") or "application/json" in ctype:
        raw = json.loads(content.decode("utf-8"))
        if isinstance(raw, dict):
            raw = raw.get("data") or raw.get("candles") or raw.get("results") or [raw]
        return pd.DataFrame(raw)
    return pd.read_csv(io.BytesIO(content))


def _normalize_candles(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    normalized = {"".join(ch.lower() for ch in str(c) if ch.isalnum()): c for c in df.columns}
    def find(*names: str) -> str | None:
        for name in names:
            if name in normalized:
                return normalized[name]
        return None
    t = find("timestamp", "date", "datetime", "time")
    o, h, l, c, v = find("open", "openingprice"), find("high", "highprice"), find("low", "lowprice"), find("close", "closingprice", "last"), find("volume", "vol", "turnoverlots")
    if not all([t, o, h, l, c]):
        return pd.DataFrame()  # Never manufacture OHLC from close-only data.
    out = df.rename(columns={t: "timestamp", o: "Open", h: "High", l: "Low", c: "Close", **({v: "Volume"} if v else {})}).copy()
    if "Volume" not in out.columns:
        out["Volume"] = 0.0
    out["timestamp"] = pd.to_datetime(out["timestamp"], errors="coerce", utc=True)
    for col in ["Open", "High", "Low", "Close", "Volume"]:
        out[col] = pd.to_numeric(out[col], errors="coerce")
    out = out.dropna(subset=["timestamp", "Open", "High", "Low", "Close"]).sort_values("timestamp")
    # Reject malformed bars rather than letting impossible ranges drive indicators.
    valid = (out["High"] >= out[["Open", "Low", "Close"]].max(axis=1)) & (out["Low"] <= out[["Open", "High", "Close"]].min(axis=1))
    valid &= (out[["Open", "High", "Low", "Close"]] > 0).all(axis=1) & (out["Volume"] >= 0)
    out = out.loc[valid]
    return out.drop_duplicates("timestamp", keep="last").set_index("timestamp")[["Open", "High", "Low", "Close", "Volume"]]


def load_candles(kind: str = "daily") -> tuple[pd.DataFrame, str]:
    env = {
        "daily": ("ZINC_DAILY_CANDLE_URL", "ZINC_DAILY_CSV_URL", "ZINC_DAILY_CANDLE_FILE", "ZINC_DAILY_CSV", "data/lme_zinc_3m_daily.csv"),
        "1h": ("ZINC_1H_CANDLE_URL", "ZINC_1H_CSV_URL", "ZINC_1H_CANDLE_FILE", "ZINC_1H_CSV", "data/lme_zinc_3m_1h.csv"),
        "15m": ("ZINC_15M_CANDLE_URL", "ZINC_15M_CSV_URL", "ZINC_15M_CANDLE_FILE", "ZINC_15M_CSV", "data/lme_zinc_3m_15m.csv"),
    }
    if kind not in env:
        raise ValueError(f"Unsupported candle kind: {kind}")
    candidates = [os.getenv(x, "").strip() for x in env[kind][:-1]] + [env[kind][-1]]
    key = os.getenv("CANDLE_API_KEY", "").strip()
    for source in candidates:
        if not source:
            continue
        try:
            df = _normalize_candles(_read_table(source, key))
            if kind == "daily" and not df.empty:
                # A current UTC trading day can still be in progress. Only settled bars are usable.
                df = df[df.index.date < pd.Timestamp.now(tz="UTC").date()]
            if not df.empty:
                return df, source
        except Exception:
            continue
    return pd.DataFrame(), "missing"
