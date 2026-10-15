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
    return ("<section class='card'><h2>美債與實質殖利率 · Treasury evidence</h2><p>官方Par Yield／Par Real Yield日資料；1D／5D指有效發布筆數，非盤中報價。1個百分點＝100 bp。</p><div class='table-wrap'><table><tr><th>因素</th><th>最新水準</th><th>1D</th><th>5D</th><th>資料日期／狀態</th><th>影響管道／來源</th></tr>"+''.join(rows)+f"</table></div><p>10Y−2Y曲線：{slope}。曲線形狀是描述，不能單獨推論景氣或Fed下一步。</p></section>")

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
    intro=("<section class='card'><h2>今日宏觀研究導覽</h2><p>先看利率與美元實際變動，再核對商品有無同步確認；以下屬描述性背景，不改變既有Trigger或交易權限。</p>"
           f"<p>{e(rate_summary)}</p><p>{dollar}</p><p>重大新聞與事件時鐘尚未接入：此頁沒有完成當日事件查核，不能把空白解讀為沒有重大事件。</p></section>")
    cards=[]
    for key,label in [('gold','黃金'),('usdjpy','美元／日圓'),('dxy','美元指數'),('lme_zinc','LME鋅'),('shfe_zinc','SHFE鋅')]:
        plan=snapshot.get('decision_book',{}).get('markets',{}).get(key,{})
        factor='real10y' if key=='gold' else 'us2y'
        aligned=_aligned(rates.get(factor,{}),_market_series(snapshot,key))
        observation='日期／資料不足，未確認跨市場同步關係。'
        if aligned:
            day,bp,ret=aligned
            expected=-1 if key=='gold' else 1 if key in ('dxy','usdjpy') else 0
            if abs(bp)<0.5 or abs(ret)<0.01: verdict='變動接近零，方向關係不具辨識力'
            elif expected==0:verdict='僅並列觀察；美債不是鋅的直接供需證據'
            elif bp*ret*expected>0:verdict='方向與一般影響管道一致；不代表已證明因果'
            else:verdict='證據衝突：價格未按一般管道反應，須找其他證據'
            observation=f'共同日期 {day}：利率變動 {bp:+.1f} bp，商品Close變動 {ret:+.2f}%；{verdict}。'
        channel={'gold':'實質利率上升一般增加黃金持有機會成本；美元也須獨立核對。','usdjpy':'美國短端利率是美元條件之一；缺日本2Y、政策與干預證據，不能計算美日利差。','dxy':'美國短端利率與美元方向並列；缺其他國家利率及成分貢獻，無法完成相對利率判斷。','lme_zinc':'美元與利率屬外部環境；Cash−3M、庫存與TC才是另外的實體證據，須逐項核對日期。','shfe_zinc':'美元與美債只提供外部背景；缺人民幣調整比價、需求及套利成本，不直接套用LME結論。'}[key]
        cards.append(f"<article class='card half'><h2>{asset_icon(key,compact=True)} {label} · {e(plan.get('direction'))}</h2><p><b>影響管道｜</b>{channel}</p><p><b>當次驗證｜</b>{e(observation)}</p><p><b>下一觀察｜</b>觀察下一個共同資料日是否延續；進場仍依商品頁的Trigger、失效與執行條件。</p><a href='market-{key}.html'>查看商品證據與計畫 →</a></article>")
    return "<div class='grid'>"+intro+rates_panel(snapshot)+f"<section class='card'><h2>美元因素</h2><p>{dollar}</p><p>美元走強對美元計價商品通常形成外部壓力；此為分析管道，需商品價格與專屬供需確認。</p></section>"+''.join(cards)+"</div>"
