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

from private_notes import add_note, read_notes
from zincintel.execution import append_trade, performance_summary, read_trades, simulate_execution

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
<title>Private zinc 3M research</title><style>body{font:15px system-ui;background:#101a28;color:#e8eef8;margin:22px}header{display:flex;gap:18px;flex-wrap:wrap;align-items:center}button,select,input,textarea{background:#1d3249;color:#fff;border:1px solid #53708a;padding:7px;border-radius:5px}svg{width:100%;height:560px;background:#152437;touch-action:none}#tooltip{min-height:2em}small{color:#a9bfd2}section{margin-top:24px;border-top:1px solid #35506a;padding-top:16px}form{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:10px}label{display:grid;gap:4px;color:#b9cad9}button{cursor:pointer}.result{white-space:pre-wrap;background:#0b1420;border:1px solid #35506a;border-radius:6px;padding:12px;min-height:3em}.warn{color:#ffbd75}.good{color:#61dbc3}table{width:100%;border-collapse:collapse}td,th{padding:7px;border-bottom:1px solid #35506a;text-align:left}</style>
<header><h2>LME Zinc 3M · 完整日線</h2><label>視窗 <select id="window"><option value="30">30 筆</option><option value="60" selected>60 筆</option><option value="120">120 筆</option><option value="all">全部</option></select></label><label><input id="ma5" type="checkbox" checked> MA5</label><label><input id="ma20" type="checkbox" checked> MA20</label><label><input id="ma50" type="checkbox" checked> MA50</label><button id="older">較早</button><button id="newer">較新</button></header>
<p id="meta"></p><svg id="chart" viewBox="0 0 1000 560" role="img" aria-label="歷史 OHLC K 線與移動平均線"></svg><p id="tooltip"></p><small>移動平均為前 N 個完整交易日的收盤價算術平均，不是工廠實際加權採購均價；不足 N 筆不顯示。此頁僅供歷史資料觀察，不產生交易建議。</small>
<section><h3>Execution Check · 私人模擬核准</h3><p>手動貼入券商即時 Bid／Ask 與帳戶風險參數。此工具只計算，不連接券商、不送單；核准只代表輸入通過規則。</p>
<form id="execution-form"><label>市場<input name="market" required value="LME Zinc"></label><label>可成交合約<input name="contract" required placeholder="券商合約代碼"></label><label>方向<select name="side"><option>LONG</option><option>SHORT</option></select></label><label>報價時間（含時區）<input name="quote_timestamp" required placeholder="2026-10-13T10:30:00+08:00"></label><label>Bid<input name="bid" type="number" step="any" required></label><label>Ask<input name="ask" type="number" step="any" required></label><label>Hard Stop<input name="hard_stop" type="number" step="any" required></label><label>T1<input name="t1" type="number" step="any" required></label><label>T2<input name="t2" type="number" step="any" required></label><label>帳戶權益<input name="account_equity" type="number" step="any" required></label><label>單筆風險 %（上限2）<input name="risk_pct" type="number" step="0.1" min="0.1" max="2" value="1" required></label><label>合約乘數<input name="contract_multiplier" type="number" step="any" required></label><label>Tick size<input name="tick_size" type="number" step="any" required></label><label>每口預估總費用<input name="fees_per_contract" type="number" step="any" min="0" value="0"></label><label>預估滑價 ticks<input name="slippage_ticks" type="number" step="any" min="0" value="1"></label><label>允許最大 spread ticks<input name="max_spread_ticks" type="number" step="any" value="4"></label><label>報價有效秒數<input name="max_quote_age_seconds" type="number" step="1" value="120"></label><label>模擬目前價（選填）<input name="mark_price" type="number" step="any"></label><button type="submit">執行私人模擬核准</button></form><div id="execution-result" class="result">尚未輸入。沒有最新 Bid／Ask，就維持 No Trade。</div></section>
<section><h3>成交後 Journal</h3><p>一個 setup_id 只能寫入一次。績效樣本未滿 30 筆只顯示「樣本不足」，不得解讀為勝率預測。</p>
<form id="trade-form"><label>Setup ID<input name="setup_id" required></label><label>市場<input name="market" required></label><label>合約<input name="contract" required></label><label>方向<select name="side"><option>LONG</option><option>SHORT</option></select></label><label>計畫進場<input name="planned_entry" type="number" step="any" required></label><label>Hard Stop<input name="hard_stop" type="number" step="any" required></label><label>T1<input name="t1" type="number" step="any" required></label><label>T2<input name="t2" type="number" step="any" required></label><label>Actual Fill<input name="actual_fill" type="number" step="any" required></label><label>Exit Price<input name="exit_price" type="number" step="any" required></label><label>口數<input name="quantity" type="number" step="1" required></label><label>合約乘數<input name="contract_multiplier" type="number" step="any" required></label><label>總手續費<input name="fees" type="number" step="any" value="0" required></label><label>開倉時間（含時區）<input name="opened_at" required></label><label>平倉時間（含時區）<input name="closed_at" required></label><label>出場原因<textarea name="exit_reason" maxlength="200"></textarea></label><label><input name="rule_followed" type="checkbox"> 遵守原計畫</label><button type="submit">寫入私人 Journal</button></form><p id="trade-status"></p><div id="performance" class="result"></div><div id="trades"></div></section>
<section><h3>圖表下的私人研究紀錄</h3><p>線上圖表觀察與本機 OHLC 主檔分開保存；「已核對」由你自行判斷，不代表系統已驗證資料來源。</p>
<form id="noteform"><label>網站／圖表連結 <input name="chart_url" type="url" required placeholder="https://..."></label><label>實際市場 <input name="market" required placeholder="依來源顯示"></label><label>合約 <input name="contract" required placeholder="依來源顯示"></label><label>觀察日期 <input name="observed_on" type="date" required></label><label>圖表最後交易日 <input name="last_trading_day" type="date" required></label><label>均線 <select name="moving_averages"><option>無</option><option>MA5</option><option>MA20</option><option>MA50</option><option>MA5/MA20</option><option>MA20/MA50</option><option>MA5/MA20/MA50</option></select></label><label>核對狀態 <select name="verification"><option>待核對</option><option>已核對</option></select></label><label>觀察筆記 <textarea name="observations" maxlength="2000"></textarea></label><label>附件圖片檔名（選填） <input name="attachment" placeholder="chart.png"></label><label><input name="attachment_allowed" type="checkbox"> 已確認來源允許我私人保存該圖片；圖片由我手動存入私人 attachments 資料夾</label><button type="submit">儲存紀錄</button></form><p id="note-status"></p><div id="notes"></div></section>
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
async function refreshNotes(){let rows=await fetch('/api/notes',{cache:'no-store'}).then(r=>r.json());let target=$('notes');target.replaceChildren();for(let d of rows.slice().reverse()){let block=document.createElement('p');block.textContent=`${d.observed_on}｜${d.market} ${d.contract}｜圖表截至 ${d.last_trading_day}｜${d.moving_averages}｜${d.verification}｜${d.observations} ${d.attachment?'｜附件：'+d.attachment:''}｜`;let link=document.createElement('a');link.href=d.chart_url;link.textContent='原圖連結';link.rel='noopener noreferrer';link.target='_blank';block.append(link);target.append(block)}}
$('noteform').onsubmit=async e=>{e.preventDefault();let f=e.target,body=Object.fromEntries(new FormData(f).entries());body.attachment_allowed=f.elements.attachment_allowed.checked;let response=await fetch('/api/notes',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});$('note-status').textContent=response.ok?'已存入私人研究紀錄':'儲存失敗：請檢查網址、日期、欄位及圖片權限';if(response.ok){f.reset();await refreshNotes()}};
$('noteform').elements.observed_on.value=new Date().toLocaleDateString('en-CA');refreshNotes().catch(()=>{$('note-status').textContent='私人紀錄讀取失敗'});
function formObject(form){let body=Object.fromEntries(new FormData(form).entries());for(let box of form.querySelectorAll('input[type=checkbox]'))body[box.name]=box.checked;return body}
$('execution-form').onsubmit=async e=>{e.preventDefault();let response=await fetch('/api/execution/preview',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(formObject(e.target))});let box=$('execution-result');let payload=await response.json().catch(()=>({error:'輸入驗證失敗'}));box.textContent=response.ok?`狀態 ${payload.status}\n模擬進場 ${payload.simulated_entry}｜Spread ${payload.spread_ticks} ticks｜風險預算 ${payload.risk_budget}\n建議口數 ${payload.contract_quantity}｜T1 R:R ${payload.planned_rr_t1}｜T2 R:R ${payload.planned_rr_t2}${payload.unrealized_pnl===undefined?'':`\n模擬未實現損益 ${payload.unrealized_pnl}`}\n阻擋理由 ${payload.blockers.join('、')||'無'}\nORDER TRANSMITTED: NO`:payload.error;box.className='result '+(payload.status==='APPROVED_FOR_SIMULATION'?'good':'warn')};
async function refreshTrades(){let data=await fetch('/api/trades',{cache:'no-store'}).then(r=>r.json());$('performance').textContent=`已平倉 ${data.performance.closed_trades} 筆｜${data.performance.status}｜勝率 ${data.performance.win_rate_pct??'—'}%｜平均 ${data.performance.average_r??'—'}R`;let target=$('trades');target.replaceChildren();for(let d of data.trades.slice().reverse()){let p=document.createElement('p');p.textContent=`${d.setup_id}｜${d.market} ${d.contract}｜${d.side}｜PnL ${d.net_pnl}｜${d.actual_r}R｜滑價 ${d.slippage_price_units}｜規則 ${d.rule_followed?'遵守':'未遵守'}`;target.append(p)}}
$('trade-form').onsubmit=async e=>{e.preventDefault();let response=await fetch('/api/trades',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(formObject(e.target))});$('trade-status').textContent=response.ok?'已寫入私人成交紀錄':'寫入失敗：請檢查完整欄位、時區與 setup_id';if(response.ok){e.target.reset();await refreshTrades()}};refreshTrades().catch(()=>{$('trade-status').textContent='私人 Journal 讀取失敗'});
</script></html>"""


def serve(path: Path, port: int) -> None:
    notes_path = path.parent / "research_notes.jsonl"
    trades_path = path.parent / "execution_journal.jsonl"
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
            elif self.path == "/api/notes":
                try:
                    payload = json.dumps(read_notes(notes_path), ensure_ascii=False).encode("utf-8")
                except (OSError, ValueError):
                    self.send_error(500, "Private notes invalid"); return
                kind = "application/json; charset=utf-8"
            elif self.path == "/api/trades":
                try:
                    trades = read_trades(trades_path)
                    payload = json.dumps({"trades": trades, "performance": performance_summary(trades)}, ensure_ascii=False).encode("utf-8")
                except (OSError, ValueError, json.JSONDecodeError):
                    self.send_error(500, "Private execution journal invalid"); return
                kind = "application/json; charset=utf-8"
            else:
                self.send_error(404); return
            self.send_response(200)
            self.send_header("Content-Type", kind)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Security-Policy", "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; img-src 'self'")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers(); self.wfile.write(payload)

        def do_POST(self):
            host = self.headers.get("Host", "")
            origin = self.headers.get("Origin", "")
            if self.path not in {"/api/notes", "/api/execution/preview", "/api/trades"} or host not in {f"127.0.0.1:{server.server_port}", f"localhost:{server.server_port}"} or origin not in {f"http://127.0.0.1:{server.server_port}", f"http://localhost:{server.server_port}"}:
                self.send_error(403); return
            if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                self.send_error(415); return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 12000:
                    raise ValueError("Invalid size")
                body = json.loads(self.rfile.read(length))
                if self.path == "/api/notes":
                    saved = add_note(notes_path, body)
                elif self.path == "/api/execution/preview":
                    saved = simulate_execution(body)
                else:
                    saved = append_trade(trades_path, body)
            except (ValueError, OSError, TypeError, json.JSONDecodeError) as exc:
                payload = json.dumps({"error": str(exc)}, ensure_ascii=False).encode("utf-8")
                self.send_response(400)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Cache-Control", "no-store")
                self.end_headers(); self.wfile.write(payload); return
            payload = json.dumps(saved, ensure_ascii=False).encode("utf-8")
            self.send_response(201)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
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
