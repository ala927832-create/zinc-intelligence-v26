"""Deterministic three-point briefing from the same frozen snapshot."""
import html
from .dashboard_v27 import _today_market_metrics, _market_series

def build_brief(snapshot):
    plans=snapshot.get('decision_book',{}).get('markets',{})
    values=[]
    for key in ('lme_zinc','shfe_zinc','gold','usdjpy','dxy'):
        m=_today_market_metrics(snapshot,key)
        if m.get('change_1d') is not None:
            values.append((abs(m['change_1d']),key,m))
    first={'title':'主要變化','text':'資料不足，無法比較最新有效交易日變動。','url':'radar.html'}
    if values:
        _,key,m=max(values)
        first.update(text=f"{plans.get(key,{}).get('market',key)} 最近有效交易日變動 {m['change_1d']:+.2f}%；截至 {_market_series(snapshot,key).get('as_of')}，基準 {m['change_basis']}。不同市場日期須另核對。",url=f'market-{key}.html')
    from .radar import _aligned
    real=snapshot.get('market_research',{}).get('rates',{}).get('real10y',{})
    a=_aligned(real,_market_series(snapshot,'gold'))
    text='黃金與實質利率的最新日期未對齊，不能判定當次支持或背離。'
    if a:
        day,bp,ret=a
        label='價格反應與一般反向管道衝突' if bp*ret>0 else '方向符合一般反向管道，但不證明因果' if bp*ret<0 else '至少一項變動為零，不能確認方向'
        text=f'{day}：10Y實質利率 {bp:+.1f} bp、黃金Close {ret:+.2f}%；{label}。'
    second={'title':'證據核對','text':text,'url':'radar.html'}
    events=snapshot.get('market_research',{}).get('events',{}).get('upcoming',[])
    third={'title':'下一關卡','text':'尚無已驗證的近期官方事件；請核對來源狀態，這不代表沒有重大事件。','url':'radar.html#event-clock'}
    if events:
        event=events[0]
        third['text']=f"{event['title']}：{event['taipei_display']}。{event['watch']} 排程不是實際公布結果。"
    return [first,second,third]

def brief_panel(snapshot):
    cards=''.join(f"<article><h3>{i}. {html.escape(x['title'])}</h3><p>{html.escape(x['text'])}</p><a href='{html.escape(x['url'])}'>核對證據 →</a></article>" for i,x in enumerate(build_brief(snapshot),1))
    return "<section class='card daily-three' id='daily-three'><h2>每日三項摘要 · 同批快照</h2><div style='display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:16px'>"+cards+"</div></section>"
