"""Offline-first private OHLC archive and loopback-only interactive research chart."""

from __future__ import annotations

import argparse
import csv
from datetime import date
from decimal import Decimal, InvalidOperation
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import tempfile

ROOT = Path(__file__).resolve().parent
FIELDS = ("date", "open", "high", "low", "close", "market", "contract", "currency", "source")
IDENTITY = {"market": "LME", "contract": "ZINC_3M", "currency": "USD"}


def private_dir() -> Path:
    raw = os.environ.get("ZINC_PRIVATE_DIR", "")
    if not raw or not Path(raw).is_absolute():
        raise ValueError("Set ZINC_PRIVATE_DIR to an absolute path outside the repository")
    path = Path(raw).resolve()
    if path == ROOT or ROOT in path.parents or path in ROOT.parents:
        raise ValueError("Private data must be outside the repository and its parent directories")
    return path


def normalize(rows: list[dict]) -> list[dict]:
    if not rows:
        raise ValueError("No daily bars provided")
    result = []
    seen = set()
    for raw in rows:
        row = {str(key).strip().lower(): str(value).strip() for key, value in raw.items() if key is not None}
        if any(not row.get(field) for field in FIELDS):
            raise ValueError("Every bar needs date, OHLC, market, contract, currency and source")
        if any(row[key].upper() != expected for key, expected in IDENTITY.items()):
            raise ValueError("Only LME ZINC_3M USD bars are accepted")
        try:
            trading_day = date.fromisoformat(row["date"])
        except ValueError as exc:
            raise ValueError("Invalid trading date") from exc
        if trading_day.isoformat() != row["date"] or trading_day >= date.today():
            raise ValueError("Trading date must be a completed previous day")
        if row["date"] in seen:
            raise ValueError("Duplicate trading date in import batch")
        seen.add(row["date"])
        try:
            prices = {key: Decimal(row[key]) for key in ("open", "high", "low", "close")}
        except InvalidOperation as exc:
            raise ValueError("OHLC must be numeric") from exc
        if any(not price.is_finite() or price <= 0 for price in prices.values()):
            raise ValueError("OHLC must be positive finite prices")
        if prices["high"] < max(prices["open"], prices["low"], prices["close"]) or prices["low"] > min(prices["open"], prices["high"], prices["close"]):
            raise ValueError("Invalid OHLC price range")
        result.append({**{key: row[key] for key in FIELDS},
                       **{key: str(prices[key]) for key in prices}})
    return sorted(result, key=lambda item: item["date"])


def load(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8-sig") as stream:
        return normalize(list(csv.DictReader(stream)))


def import_file(source: Path, destination: Path) -> int:
    if source.resolve() == ROOT or ROOT in source.resolve().parents:
        raise ValueError("Input CSV must be outside the public repository")
    with source.open(newline="", encoding="utf-8-sig") as stream:
        incoming = normalize(list(csv.DictReader(stream)))
    existing = {row["date"]: row for row in load(destination)}
    for row in incoming:
        if row["date"] in existing and existing[row["date"]] != row:
            raise ValueError("Conflicting historical row requires manual review: " + row["date"])
    merged = sorted({**existing, **{row["date"]: row for row in incoming}}.values(), key=lambda x: x["date"])
    destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".ohlc-", dir=destination.parent, text=True)
    try:
        with os.fdopen(fd, "w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(merged)
        os.chmod(name, 0o600)
        os.replace(name, destination)
    finally:
        if os.path.exists(name):
            os.unlink(name)
    return len(merged)


def page() -> str:
    return """<!doctype html><html lang="zh-Hant"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Private zinc 3M research</title><style>body{font:15px system-ui;background:#101a28;color:#e8eef8;margin:22px}header{display:flex;gap:18px;flex-wrap:wrap;align-items:center}button,select{background:#1d3249;color:#fff;border:1px solid #53708a;padding:7px;border-radius:5px}svg{width:100%;height:560px;background:#152437;touch-action:none}#tooltip{min-height:2em}small{color:#a9bfd2}</style>
<header><h2>LME Zinc 3M · 完整日線</h2><label>視窗 <select id="window"><option value="30">30 筆</option><option value="60" selected>60 筆</option><option value="120">120 筆</option><option value="all">全部</option></select></label><label><input id="ma5" type="checkbox" checked> MA5</label><label><input id="ma20" type="checkbox" checked> MA20</label><label><input id="ma50" type="checkbox" checked> MA50</label><button id="older">較早</button><button id="newer">較新</button></header>
<p id="meta"></p><svg id="chart" viewBox="0 0 1000 560" role="img" aria-label="歷史 OHLC K 線與移動平均線"></svg><p id="tooltip"></p><small>移動平均為前 N 個完整交易日的收盤價算術平均，不是工廠實際加權採購均價；不足 N 筆不顯示。此頁僅供歷史資料觀察，不產生交易建議。</small>
<script>
let data=[], end=0; const $=id=>document.getElementById(id), ns='http://www.w3.org/2000/svg';
function el(name,attrs){let n=document.createElementNS(ns,name);for(const [k,v] of Object.entries(attrs))n.setAttribute(k,v);$('chart').append(n);return n}
function mean(i,n){if(i+1<n)return null;let s=0;for(let j=i-n+1;j<=i;j++)s+=+data[j].close;return s/n}
function draw(){const svg=$('chart');svg.replaceChildren();if(!data.length){$('meta').textContent='OHLC MISSING · 0 筆；請先匯入已驗證日線';return}
 const count=$('window').value==='all'?data.length:+$('window').value, from=Math.max(0,end-count), visible=data.slice(from,end);if(!visible.length)return;
 const low=Math.min(...visible.map(d=>+d.low)),high=Math.max(...visible.map(d=>+d.high)),range=(high-low)||1;
 const y=v=>510-(v-low)/range*450,x=i=>58+(i+.5)*900/visible.length,step=900/visible.length;
 $('meta').textContent=`來源：${[...new Set(visible.map(d=>d.source))].join('、')} · ${data.length} 筆有效日線 · 最後交易日 ${data.at(-1).date} · 顯示 ${visible[0].date} 至 ${visible.at(-1).date} · USD/t`;
 for(let g=0;g<=4;g++){let price=low+range*g/4;el('line',{x1:52,x2:963,y1:y(price),y2:y(price),stroke:'#33485c'});let t=el('text',{x:2,y:y(price)+4,fill:'#b9cad9','font-size':12});t.textContent=price.toFixed(1)}
 visible.forEach((d,i)=>{let xx=x(i), up=+d.close>=+d.open,color=up?'#43c6aa':'#f08c80';el('line',{x1:xx,x2:xx,y1:y(+d.high),y2:y(+d.low),stroke:color,'stroke-width':2});let yy=Math.min(y(+d.open),y(+d.close)),h=Math.max(2,Math.abs(y(+d.open)-y(+d.close)));el('rect',{x:xx-Math.max(1,step*.28),y:yy,width:Math.max(2,step*.56),height:h,fill:color});let hit=el('rect',{x:xx-step/2,y:54,width:step,height:467,fill:'transparent'});hit.addEventListener('pointermove',()=>{$('tooltip').textContent=`${d.date} · O ${d.open} / H ${d.high} / L ${d.low} / C ${d.close} · MA5 ${mean(from+i,5)?.toFixed(2)??'資料不足'} · MA20 ${mean(from+i,20)?.toFixed(2)??'資料不足'} · MA50 ${mean(from+i,50)?.toFixed(2)??'資料不足'} · ${d.source}`})});
 for(let [n,color] of [[5,'#bba6eb'],[20,'#f3c76b'],[50,'#7cafff']]){if(!$('ma'+n).checked)continue;let pts=visible.map((_,i)=>{let v=mean(from+i,n);return v===null?null:[x(i),y(v)]}).filter(Boolean);if(pts.length>1)el('polyline',{points:pts.map(p=>p.join(',')).join(' '),fill:'none',stroke:color,'stroke-width':2})}
 $('older').disabled=from===0;$('newer').disabled=end===data.length;
}
for(let id of ['window','ma5','ma20','ma50'])$(id).addEventListener('change',draw);
$('older').onclick=()=>{end=Math.max(1,end-+($('window').value==='all'?60:$('window').value));draw()};$('newer').onclick=()=>{end=Math.min(data.length,end+($('window').value==='all'?60:$('window').value));draw()};
fetch('/api/ohlc',{cache:'no-store'}).then(r=>r.json()).then(rows=>{data=rows;end=data.length;draw()}).catch(()=>{$('meta').textContent='無法讀取本機私人日線'});
</script></html>"""


def serve(path: Path, port: int) -> None:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            host = self.headers.get("Host", "")
            if host not in {f"127.0.0.1:{server.server_port}", f"localhost:{server.server_port}"}:
                self.send_error(403, "Local host only"); return
            if self.path == "/":
                payload = page().encode("utf-8"); kind = "text/html; charset=utf-8"
            elif self.path == "/api/ohlc":
                try:
                    rows = load(path)
                except (OSError, ValueError):
                    self.send_error(500, "Private OHLC archive invalid"); return
                payload = json.dumps(rows, ensure_ascii=False).encode("utf-8"); kind = "application/json; charset=utf-8"
            else:
                self.send_error(404); return
            self.send_response(200)
            self.send_header("Content-Type", kind)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Security-Policy", "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; img-src 'self'")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers(); self.wfile.write(payload)

    with ThreadingHTTPServer(("127.0.0.1", port), Handler) as server:
        print(f"Local-only research chart: http://127.0.0.1:{server.server_port}/")
        server.serve_forever()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Private historical OHLC research; never publish this archive")
    parser.add_argument("action", choices=("import", "serve"))
    parser.add_argument("source", nargs="?", type=Path)
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    target = private_dir() / "lme_zinc_3m_ohlc.csv"
    if args.action == "import":
        if not args.source:
            parser.error("import requires a source CSV")
        print(f"Verified sessions: {import_file(args.source, target)}")
    else:
        if args.source:
            parser.error("serve does not accept a source CSV")
        serve(target, args.port)
