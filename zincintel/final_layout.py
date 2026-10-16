"""A/B presentation only: keep prices, evidence and execution layers distinct."""
from html import escape

LABELS={'lme_zinc':'LME 鋅現貨','shfe_zinc':'SHFE 鋅','gold':'COMEX 黃金','usdjpy':'USD/JPY','dxy':'DXY 美元指數','us_treasury':'美國 10Y 殖利率'}
CSS='''
.final-ab h1,.final-ab h2,.final-ab h3,.final-ab .price,.final-ab .quote-main strong{font-family:Inter,"Noto Sans TC",system-ui,sans-serif}.final-ab .quote-card{min-height:260px;padding:20px}.final-ab .quote-main strong{font-size:36px;letter-spacing:-.025em}.final-ab .quote-main{align-items:center}.final-ab .quote-changes{display:flex;gap:20px;font-size:14px}.final-ab .quote-changes>div{background:none;border:0;padding:0}.final-ab .quote-changes span,.final-ab .quote-changes b{display:inline;font-size:14px}.final-ab .quote-summary{background:none;border:0;padding:8px 0;font-size:14px;line-height:1.7}.final-ab .quote-foot{font-size:12px;align-items:center;flex-wrap:wrap}.final-ab .quote-sub-grid{background:#f5f3ed;padding:8px;font-size:13px}.final-ab .side-nav,.final-ab .nav{background:#102a40}.final-ab .side-nav a,.final-ab .nav a{color:#e8eef1}.final-ab .side-nav a.on,.final-ab .nav a.on{background:#14515d}.final-ab .head h1{font:700 22px/1.4 system-ui}.ab-watch{display:flex;align-items:center;gap:15px;padding:14px 0;border-bottom:1px solid #e0e5e8}.ab-watch p{flex:1;margin:0}.ab-watch a{white-space:nowrap}.ab-private{display:inline-block;padding:10px 14px;color:#fff;background:#102a40;border-radius:6px}.ab-identity{padding:10px 14px;background:#f8f2e8;border-left:3px solid #bc8959;margin:8px 0;font-size:13px}.ab-compass{padding:14px;background:#fff;color:#17354c;border:1px solid #dce1e3;border-radius:8px;margin-top:12px}.ab-band{display:grid;grid-template-columns:repeat(5,1fr));height:10px;display:flex;border-radius:10px;overflow:hidden}.ab-band i{flex:1}.ab-compass-labels{display:flex;justify-content:space-between;font-size:11px;margin-top:4px}.chart-readout{min-height:52px;color:#e7f0f5;line-height:1.7;padding:8px;font-size:13px}.chart-position{width:100%;accent-color:#4cd1d9}.chart-window[hidden]{display:none!important}.chart-window svg{touch-action:pan-y}.ab-cursor{pointer-events:none}.final-ab .chart{height:360px;padding:10px}.final-ab .rsi-chart svg{height:105px}.final-ab .key-levels{background:#fff;color:#17354c;border:1px solid #dce1e3}.final-ab .key-levels h2{color:#17354c}.final-ab .key-levels dt{color:#617181}.final-ab .key-levels div{border-color:#e0e5e8}.final-ab .key-levels .stop{color:#b4404d}.final-ab .key-levels .target{color:#087b70}.final-ab .chart-first{grid-template-columns:minmax(0,2.5fr) minmax(255px,1fr);align-items:start}.final-ab .market-kpis{grid-template-columns:repeat(3,1fr)}.final-ab .market-kpis b{font-size:20px}.final-ab .market-stage{padding:12px 15px}.final-ab .market-stage>p,.final-ab .market-stage .muted{display:none}.final-ab .source-strip{font-size:12px}.final-ab .period-controls button{min-height:36px;font-size:13px}.final-ab .market-detail>header{font-size:14px}.final-ab .market-lower{margin-top:18px}.ab-note{font-size:12px;line-height:1.65;color:#627281}.final-ab .daily-three{box-shadow:none;border:0;padding:0}.final-ab .daily-three p{font-size:14px;line-height:1.75}.final-ab .key-levels .ab-note{color:#627281}
@media(max-width:1050px){.final-ab .chart-first{grid-template-columns:1fr}.final-ab .key-levels{display:block}.final-ab .quote-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:650px){.final-ab .quote-grid{grid-template-columns:1fr}.final-ab .quote-main strong{font-size:34px}.final-ab .market-kpis{grid-template-columns:1fr 1fr}.final-ab .chart{height:275px}.final-ab .market-tabs{display:flex;overflow-x:auto;flex-wrap:nowrap}.final-ab .market-tabs a{flex:0 0 auto}.ab-watch{flex-wrap:wrap}.ab-watch p{flex-basis:65%}.final-ab .head h1{font-size:18px}.final-ab .quote-card{min-height:0}.ab-compass-labels{font-size:12px}}
'''.replace('grid-template-columns:repeat(5,1fr));','grid-template-columns:repeat(5,1fr);')


def today(snapshot):
    from .dashboard_v27 import _market_series,_today_market_metrics,_decision_reference,_spark_path,fmt,_change_text
    from .visual_language import asset_icon,source_badge,source_legend
    from .line_flex import compact_brief
    from .daily_brief import build_brief
    brief_cards=''.join("<article><h3>"+escape(item['title'])+"</h3><p>"+escape(item['text'])+"</p><a href='"+escape(full['url'])+"'>核對證據 →</a></article>" for item,full in zip(compact_brief(snapshot),build_brief(snapshot)))
    brief_html="<section class='daily-three' id='daily-three'><h2>今日三項重點 · 同批資料</h2><div style='display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:16px'>"+brief_cards+"</div></section>"
    plans=snapshot.get('decision_book',{}).get('markets',{})
    cards=[]
    for key,title in LABELS.items():
        plan=plans.get(key,{})
        series=_market_series(snapshot,key)
        rate=snapshot.get('market_research',{}).get('rates',{}).get('us10y',{})
        value,unit=_decision_reference(snapshot,key,plan)
        metrics=_today_market_metrics(snapshot,key,plan)
        asof=plan.get('as_of') or series.get('as_of') or '—'
        source=series.get('source') or '—';grade=series.get('source_grade');status=series.get('retrieval_status') or series.get('status')
        spark=_spark_path(series.get('chart_points',[]));secondary=''
        changes=[]
        for label,field in [('1D','change_1d'),('5D','change_5d')]:
            text,tone=_change_text(metrics.get(field));changes.append(f"<div><span>{label} </span><b class='{tone}'>{escape(text)}</b></div>")
        note={'shfe_zinc':'中國市場獨立序列；先核對合約與價格結構。','gold':'當日變化與中期方向分開判讀。','usdjpy':'USD/JPY上升＝美元走強／日圓走弱。','dxy':'美元籃子方向不能取代商品專屬證據。'}.get(key,'')
        if key=='lme_zinc':
            health=snapshot.get('market',{}).get('data_health',{}).get('lme_cash',{})
            asof=health.get('as_of') or asof;source=health.get('source') or source;grade=health.get('source_grade') or grade
            spark="<span class='spark-missing'>Cash歷史待補</span>"
            changes=["<div>Cash 1D <b>N/A</b></div><div>Cash 5D <b>N/A</b></div>"]
            change,_=_change_text(metrics.get('change_1d'))
            secondary=f"<div class='quote-sub-grid' data-basis='LME_3M_CLOSE'>3M參考 <b>{fmt((plan.get('reference') or {}).get('close'),2)}</b> · 3M 1D {escape(change)} · 資料日 {escape(str(series.get('as_of') or '—'))}</div>"
            note='現貨行情與3M技術趨勢分別判讀。'
        elif key=='us_treasury':
            value=rate.get('value');unit='%' ;asof=rate.get('as_of') or '—';source=rate.get('source') or 'US Treasury';grade=rate.get('source_grade');status=rate.get('retrieval_status')
            changes=[]
            for label,field in [('1D','change_1d_bp'),('5D','change_5d_bp')]:
                v=rate.get(field);txt=f'{v:+.1f} bp' if isinstance(v,(int,float)) else 'N/A';changes.append(f'<div>{label} <b>{txt}</b></div>')
            spark='';note='官方日殖利率；基點變動不是債券價格報酬。'
        contract=series.get('latest_contract') or ''
        cards.append(f"""<article class='quote-card' data-market='{key}'><div class='asset-identity'>{asset_icon(key)}<h2>{title}</h2></div><small>{escape(contract)}</small><div class='quote-main'><strong>{fmt(value,2)}</strong><span>{escape(str(unit))}</span>{spark}</div><div class='quote-changes'>{''.join(changes)}</div>{secondary}<p class='quote-summary'>{note}</p><div class='quote-foot'><span>資料日 {escape(str(asof))}</span><details><summary>來源詳情</summary>{source_badge(grade,status)} {escape(str(source))}</details><a href='market-{key}.html'>查看市場 →</a></div></article>""")
    watches=''.join(f"<div class='ab-watch'>{asset_icon(k,compact=True)}<b>{LABELS[k]}</b><p>{reason}</p><a href='market-{k}.html'>進入 Markets →</a></div>" for k,reason in [('lme_zinc','核對現貨曲線與3M價格趨勢的差異。'),('gold','核對價格結構與實質利率背景。'),('usdjpy','核對匯率方向與利差證據缺口。')])
    return "<section class='panel s12' id='overview'><span id='market-snapshot'></span><h2>今日行情總覽</h2><p class='muted'>先看行情，再選擇深入研究的市場 · 日／5交易日變動</p><div class='quote-grid'>"+''.join(cards)+"</div></section><section class='panel s12'>"+brief_html+"</section><section class='panel s12'><h2>優先觀察 · 研究入口（非排名或交易訊號）</h2>"+watches+"</section><section class='panel s12'><details><summary>資料身分與來源說明</summary>"+"<p>核心市場資料狀態："+escape(str(snapshot.get('core_data_gate',{}).get('status','—')))+"</p>"+source_legend()+"</details></section>"


def compass(direction):
    values=['STRONG_BEAR','BEAR','NEUTRAL','BULL','STRONG_BULL']
    i=values.index(direction) if direction in values else None
    labels=['強空','偏空','中性','偏多','強多'];colors=['#c65060','#e99483','#b9c3c9','#72c4b5','#087f76']
    marker='' if i is None else f"<line x1='100' y1='89' x2='{[36,60,100,140,164][i]}' y2='{[64,39,25,39,64][i]}' stroke='#17354c' stroke-width='4'/>"
    return "<div class='ab-compass'><b>技術趨勢 · Trend Compass</b><svg viewBox='0 0 200 105' width='100%' height='95' role='img' aria-label='"+escape(direction or '資料不足')+"'><path d='M20 90 A80 80 0 0 1 180 90' stroke='#b0c6cd' stroke-width='13' fill='none'/>"+marker+"<circle cx='100' cy='89' r='5' fill='#17354c'/></svg><div class='ab-band'>"+''.join(f"<i style='background:{c}'></i>" for c in colors)+"</div><div class='ab-compass-labels'>"+''.join(f"<span>{'▲ ' if j==i else ''}{x}</span>" for j,x in enumerate(labels))+"</div><p class='ab-note'>僅描述本商品技術序列；不代表交易許可。</p></div>"

CSS+='''.final-ab .chart{height:auto}.final-ab .chart>svg{height:280px;display:block}.final-ab .chart-window{min-width:0}.final-ab .rsi-chart svg{height:105px}.final-ab .chart-readout{font-variant-numeric:tabular-nums}.final-ab .market-body{padding:14px}.final-ab .side-nav a,.final-ab .nav a{border-radius:5px}@media(max-width:650px){.final-ab .chart>svg{height:235px}.final-ab .chart-readout{font-size:12px}.final-ab .market-body{padding:9px}}'''
CHART_JS='''<script>(()=>{document.querySelectorAll('.chart-window').forEach(panel=>{const slider=panel.querySelector('.chart-position');if(!slider)return;const points=JSON.parse(slider.dataset.points),readout=panel.querySelector('.chart-readout');function select(index){const i=Math.max(0,Math.min(points.length-1,index)),d=points[i];slider.value=i;const fields=[['open','Open'],['high','High'],['low','Low'],['close','Close'],['sma14','SMA14'],['sma20','SMA20'],['sma30','SMA30'],['sma50','SMA50'],['sma60','SMA60'],['ema20','EMA20'],['rsi14','RSI14']];readout.textContent=d.date+' · '+fields.filter(([k])=>d[k]!==undefined&&d[k]!==null).map(([k,n])=>n+' '+Number(d[k]).toLocaleString('en-US',{maximumFractionDigits:2})).join(' · ');panel.querySelectorAll('.ab-cursor').forEach(line=>{line.setAttribute('x1',20+i*760/Math.max(1,points.length-1));line.setAttribute('x2',line.getAttribute('x1'));line.setAttribute('visibility','visible')})}panel.querySelectorAll('svg').forEach(svg=>svg.addEventListener('pointermove',e=>{let p=svg.createSVGPoint();p.x=e.clientX;p.y=e.clientY;const m=svg.getScreenCTM();if(!m)return;p=p.matrixTransform(m.inverse());select(Math.round((p.x-20)/760*(points.length-1)))}));slider.addEventListener('input',()=>select(Number(slider.value)));select(points.length-1)});})()</script>'''
CSS+='''.final-ab .quote-main{flex-wrap:wrap}.final-ab .market-spark{width:94px;flex:0 0 94px}.final-ab .rsi-chart{padding:7px 10px 4px;border:0}.final-ab .chart-unit{color:#bed0dc;font-size:12px}'''

CSS+=""".final-ab .quote-sub-grid{display:block;line-height:1.8}.final-ab .quote-card>small{display:block;min-height:18px}.final-ab .quote-board h2,.final-ab #overview>h2{font-size:27px}.final-ab .quote-card h2{font-size:18px}.final-ab .market-stage h2{font-size:25px;margin:0 0 12px}.final-ab .period-controls button.active{background:#42c7d1;border-color:#42c7d1;color:#102a40}.final-ab .market-kpis>div{min-width:0}.final-ab .chart-label-row{margin-bottom:8px}@media(max-width:650px){.final-ab .market-stage h2{font-size:21px}.final-ab #overview>h2{font-size:24px}}"""

CSS+=""".final-ab .market-lower{grid-template-columns:repeat(3,minmax(0,1fr))}.final-ab .evidence-card p{line-height:1.8;font-size:14px}.final-ab .evidence-card h2{font-size:17px}.final-ab .market-lower .card{min-width:0}.final-ab .market-lower .card p{overflow-wrap:anywhere}@media(max-width:850px){.final-ab .market-lower{grid-template-columns:1fr}}"""
