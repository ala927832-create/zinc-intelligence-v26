"""Read-only macro evidence panels; never change trade permission."""
import html
from .visual_language import asset_icon, source_badge
from .dashboard_v27 import _market_series, _today_market_metrics

def e(x):return html.escape(str(x if x is not None else 'N/A'))
def n(x,suffix=''):
    return f'{x:,.2f}{suffix}' if isinstance(x,(int,float)) else 'N/A'

def rates_panel(snapshot):
    rates=snapshot.get('market_research',{}).get('rates',{})
    rows=[]
    for key,label,channel in [('us2y','美國2Y','短端利率／美元政策環境'),('us10y','美國10Y','長端融資環境；不等同Fed預期'),('us30y','美國30Y','長端期限與財政風險背景'),('real10y','美國10Y實質','黃金持有機會成本；非固定反向關係')]:
        r=rates.get(key,{})
        rows.append(f"<tr><td>{label}</td><td>{n(r.get('value'),'%')}</td><td>{n(r.get('change_1d_bp'),' bp')}</td><td>{n(r.get('change_5d_bp'),' bp')}</td><td>{e(r.get('as_of'))}<br>{e(r.get('status','MISSING'))} · {e(r.get('retrieval_status'))}</td><td>{channel}<br>{source_badge(r.get('source_grade'),r.get('retrieval_status') if r.get('status')=='AVAILABLE' else 'MISSING')} <a href='{e(r.get('source_url') or 'https://home.treasury.gov/treasury-daily-interest-rate-xml-feed')}'>官方資料</a></td></tr>")
    a,b=rates.get('us10y',{}),rates.get('us2y',{})
    slope=n((a['value']-b['value'])*100,' bp') if a.get('status')==b.get('status')=='AVAILABLE' and a.get('as_of')==b.get('as_of') else 'N/A（日期或狀態不一致）'
    return ("<section class='card' id='treasury-evidence'><h2>美債與實質殖利率 · Treasury evidence</h2><p>官方Par Yield／Par Real Yield日資料；1D／5D指有效發布筆數，非盤中報價。1個百分點＝100 bp。</p><div class='table-wrap'><table><tr><th>因素</th><th>最新水準</th><th>1D</th><th>5D</th><th>資料日期／狀態</th><th>影響管道／來源</th></tr>"+''.join(rows)+f"</table></div><p>10Y−2Y曲線：{slope}。曲線形狀是描述，不能單獨推論景氣或Fed下一步。</p></section>")

def _aligned(rate,series):
    if rate.get('status')!='AVAILABLE' or series.get('status')!='AVAILABLE':return None
    r={p['date']:p['value'] for p in rate.get('history',[])}
    p={p['date']:p['close'] for p in series.get('chart_points',[]) if isinstance(p.get('close'),(float,int))}
    common=sorted(set(r)&set(p))
    if len(common)<2:return None
    a,b=common[-2:]
    if b != rate.get('as_of') or b != series.get('as_of'):return None
    from datetime import date
    if (date.fromisoformat(b)-date.fromisoformat(a)).days>7:return None
    return b,(r[b]-r[a])*100,(p[b]/p[a]-1)*100

def radar_body(snapshot):
    from .daily_brief import brief_panel
    from .radar_chart import comparison_chart
    from .official_events import event_panel
    research=snapshot.get('market_research',{});rates=research.get('rates',{})
    dxy=research.get('cross_assets',{}).get('dxy',{})
    dm=_today_market_metrics(snapshot,'dxy')
    dollar=(f"DXY {n(dm.get('technical_close'))}，1D {n(dm.get('change_1d'),'%')}、5D {n(dm.get('change_5d'),'%')}；截至 {e(dxy.get('as_of'))}，{e(dxy.get('retrieval_status'))}。")
    short,long=rates.get('us2y',{}),rates.get('us10y',{})
    rate_summary='利率方向：資料不足，請逐列核對狀態與日期。'
    if short.get('status')==long.get('status')=='AVAILABLE' and short.get('as_of')==long.get('as_of'):
        a,b=short.get('change_1d_bp'),long.get('change_1d_bp')
        if a is not None and b is not None:
            alignment='短端與長端方向相反，不能描述為利率全面上升或下降。' if a*b<0 else '短端與長端須連同實質利率分別判讀；沒有單一利率結論。'
            rate_summary=f"截至 {short.get('as_of')}，2Y一日 {a:+.1f} bp，10Y一日 {b:+.1f} bp；{alignment}"
    from .radar_evidence import evidence_rows
    rows=[]
    for x in evidence_rows(snapshot):
        rows.append(f"<tr><td>{asset_icon(x['key'],compact=True)} <a href='market-{x['key']}.html'>{e(x['label'])}</a><br>{e(x['as_of'])}</td><td>{e(x['technical'])}</td><td>{e(x['macro'])}</td><td>{e(x['evidence'])}</td><td>{e(x['missing'])}<details><summary>確認／反證條件</summary><p><b>確認｜</b>{e(x['confirm'])}</p><p><b>反證｜</b>{e(x['refute'])}</p></details></td></tr>")
    matrix="<section class='card' id='evidence-matrix'><h2>商品證據矩陣 · 今日宏觀研究導覽</h2><p>技術方向是中期分類；宏觀欄只核對當日影響管道，並非宏觀評分或交易核准。當次驗證｜比較日期與方向；下一觀察｜展開各商品確認與反證條件。</p><p>窄螢幕可橫向滑動矩陣；各商品確認與反證條件可展開。</p><div class='table-wrap'><table style='min-width:1000px;table-layout:fixed'><thead><tr><th>商品／技術日期</th><th>技術方向與時間尺度</th><th>宏觀順逆風／證據衝突</th><th>商品專屬證據</th><th>尚未確認／觀察條件</th></tr></thead><tbody>"+''.join(rows)+"</tbody></table></div></section>"
    sources=snapshot.get('market_research',{}).get('events',{}).get('sources',{})
    missing=[k for k in ('BLS','Fed','BoJ','NBS') if sources.get(k,{}).get('status')!='VERIFIED_FETCH']
    warning="<aside class='card' id='evidence-gaps' role='status'><b>影響判斷的缺口</b><p>"+e(('、'.join(missing)+' 事件覆蓋非即時完整查核；' if missing else ''))+"BLS沿用排程時會標示最後核對時間，最長7日，逾期不使用。突發新聞未查核；LME無真實完整OHLC；跨市場同日同步不證明因果。沒有事件列不代表沒有重大事件。</p></aside>"
    details="<section class='card' id='radar-sources'><h2>來源與限制</h2><details><summary>展開利率數值、來源與日期</summary>"+rates_panel(snapshot)+"<p>"+dollar+"</p></details><p>資料用途為研究背景；缺口、日期不一致與反證不會被隱藏，也不改變Trigger或交易權限。</p></section>"
    return "<div class='grid'>"+brief_panel(snapshot)+warning+matrix+comparison_chart(snapshot)+event_panel(snapshot)+details+"</div>"
