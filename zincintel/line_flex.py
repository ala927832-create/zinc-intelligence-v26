"""Version B daily Flex layout. Public research only; no execution/account data."""
from __future__ import annotations
import json, math
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
from .dashboard_v27 import _today_market_metrics, _market_series
from .daily_brief import build_brief

BASE='https://ala927832-create.github.io/zinc-intelligence-v26/'
NAVY='#102D4B'; BLUE='#1264D9'; INK='#17334D'; UP='#23D0B4'; DOWN='#FF727D'; MUTED='#617487'

def text(value,size='sm',color=INK,**kw):
    return dict(type='text',text=str(value if value not in (None,'') else 'N/A'),size=size,color=color,wrap=True,**kw)

def box(contents,**kw):return dict(type='box',layout='vertical',contents=contents,**kw)
def link(label,path=''):return dict(type='button',action=dict(type='uri',label=label,uri=BASE+path),style='link',height='sm',color=BLUE)
def finite(x):return isinstance(x,(int,float)) and not isinstance(x,bool) and math.isfinite(x)
def price(x):return f'{x:,.2f}' if finite(x) else 'N/A'
def delta(x,unit='%'):
    if not finite(x):return '漲跌 N/A','#BBC6D0'
    return f'{"▲" if x>0 else "▼" if x<0 else "＝"} {x:+.2f}{unit}',UP if x>0 else DOWN if x<0 else '#BBC6D0'

def valid_change(series,metrics):
    """Require aligned dated observations, and reject long gaps as a daily move."""
    if series.get('status')!='AVAILABLE':return None
    points=[p for p in series.get('chart_points',[]) if finite(p.get('close'))]
    if len(points)<2:return None
    try:
        a,b=(datetime.fromisoformat(p['date']).date() for p in points[-2:])
        if b.isoformat()!=series.get('as_of') or not 0<(b-a).days<=7:return None
    except (KeyError,TypeError,ValueError):return None
    return metrics.get('change_1d')

def build_market_rows(snapshot):
    rows=[];market=snapshot.get('market',{});cross=snapshot.get('market_research',{}).get('cross_assets',{})
    for key,label,unit,identity in [
        ('gold','黃金','USD/oz','COMEX連續參考｜非指定到期合約'),
        ('lme_zinc','鋅現貨','USD/t','LME Cash｜公開參考報價'),
        ('usdjpy','美元／日圓','JPY／1 USD','USD/JPY｜外匯參考'),
        ('dxy','美元指數','點','DXY｜指數參考'),
        ('shfe_zinc','上海鋅','CNY/t','SHFE｜獨立市場')]:
        # Never substitute spot gold or a research USD basket under futures/DXY identity.
        series=_market_series(snapshot,key);m=_today_market_metrics(snapshot,key)
        session=series.get('latest_session') or {}
        value=m.get('technical_close')
        if value is None:value=session.get('close',series.get('latest_close'))
        as_of=series.get('as_of');source=series.get('source') or '來源缺失'
        grade=series.get('source_grade') or '等級缺失'
        status=series.get('retrieval_status') or series.get('status') or 'MISSING'
        change=valid_change(series,m);extra=[]
        direction=snapshot.get('decision_book',{}).get('markets',{}).get(key,{}).get('direction') or '未確認'
        sentence=f'技術方向：{direction}；單日變動不等於趨勢反轉。'
        if key=='usdjpy':sentence='匯價下降＝日圓升值；技術方向 '+direction+'。'
        if key=='gold':identity+='｜'+str(series.get('symbol') or '代碼缺失')
        if key=='lme_zinc':
            meta=market.get('field_sources',{}).get('lme_cash',{})
            value=market.get('lme_cash');as_of=meta.get('as_of');source=meta.get('provider') or '來源缺失';status=meta.get('status') or 'MISSING'
            grade=market.get('data_health',{}).get('lme_cash',{}).get('source_grade') or '等級缺失'
            change=None # A 3M change is never a Cash change.
            d,c=delta(valid_change(series,m))
            extra=[text('3M參考收盤 '+price(m.get('technical_close'))+' USD/t','sm'),text(d,'sm',c),text('3M交易日：'+str(series.get('as_of') or 'N/A'),'xs',MUTED),text('3M來源：'+str(series.get('source') or '來源缺失'),'xs',MUTED),text(str(series.get('source_grade') or '等級缺失')+'｜'+str(series.get('retrieval_status') or series.get('status') or 'MISSING'),'xs',MUTED)]
            sentence='Cash與3M分開核對日期與變動；3M方向 '+direction+'。'
        if key=='shfe_zinc':identity+='｜'+str(series.get('latest_contract') or '合約缺失')
        if not as_of or source=='來源缺失' or status in ('MISSING','UNAVAILABLE','NOT_AVAILABLE'):
            value=None;change=None
        rows.append(dict(key=key,label=label,unit=unit,identity=identity,value=value,change=change,as_of=as_of,source=source,grade=grade,status=status,sentence=sentence,extra=extra))
    return rows

def market_card(r):
    d,color=delta(r['change'])
    header=dict(type='box',layout='horizontal',spacing='md',contents=[
        dict(type='image',url=BASE+'assets/line-icons/'+r['key']+'.png',size='40px',aspectRatio='1:1',flex=0),
        box([text(r['label'],'lg',weight='bold'),text(r['identity'],'xs',MUTED)],flex=1)])
    quote=box([dict(type='box',layout='horizontal',alignItems='center',spacing='sm',contents=[text(price(r['value']),'xxl','#FFFFFF',weight='bold',flex=1),text(d,'sm',color,weight='bold',flex=0)]),text(r['unit'],'xs','#CDDFEE')],backgroundColor=NAVY,paddingAll='12px',cornerRadius='8px',margin='md')
    contents=[header,quote]
    if r['extra']:contents.append(box(r['extra'],backgroundColor='#EDF4FC',paddingAll='8px',margin='sm',cornerRadius='6px'))
    contents.extend([box([text(r['sentence'])],backgroundColor='#F1F6FB',paddingAll='8px',margin='sm',cornerRadius='6px'),text('交易日：'+str(r['as_of'] or 'N/A'),'xs',MUTED,margin='sm'),text('來源：'+r['source'],'xs',MUTED),text(r['grade']+'｜'+r['status'],'xs','#946000' if 'CARRY' in r['status'] else MUTED),link('查看此商品 →','market-'+r['key']+'.html')])
    return box(contents,backgroundColor='#FFFFFF',paddingAll='12px',cornerRadius='10px',margin='md',borderWidth='1px',borderColor='#D9E8F8')

def compact_brief(snapshot):
    """Short mobile wording of the same frozen facts; no extra signal model."""
    full=build_brief(snapshot);first=full[0]['text']
    key=full[0]['url'].removeprefix('market-').removesuffix('.html')
    if key in ('gold','lme_zinc','usdjpy','dxy','shfe_zinc'):
        m=_today_market_metrics(snapshot,key);change=m.get('change_1d')
        labels={'gold':'黃金參考Close','lme_zinc':'LME 3M參考Close','usdjpy':'USD/JPY','dxy':'DXY','shfe_zinc':'SHFE鋅'}
        if finite(change):first=f"{labels[key]} {change:+.2f}%｜{_market_series(snapshot,key).get('as_of') or '日期缺失'}。"
    from .radar_evidence import evidence_rows
    candidates=[r for r in evidence_rows(snapshot) if '當日反向' in r['technical'] or '美元下降但鋅下跌' in r['macro'] or '管道衝突' in r['macro']]
    chosen=next((r for r in candidates if '美元下降但鋅下跌' in r['macro']),candidates[0] if candidates else None)
    second='尚無已驗證方向衝突；不代表證據完整。'
    if chosen:
        if '美元下降但鋅下跌' in chosen['macro']:second=chosen['label']+'：美元下降但價格仍跌；相對表現偏弱，原因未確認。'
        elif '當日反向' in chosen['technical']:second=chosen['label']+'：'+chosen['technical'].split('。')[0]+'。當日反向變動尚未推翻中期結構。'
        else:second=chosen['label']+'：價格未按一般利率管道反應；其他因素待查。'
    events=snapshot.get('market_research',{}).get('events',{}).get('upcoming',[])
    third=(events[0]['title']+'｜'+events[0]['taipei_display']+'。排程非實際結果。') if events else '官方事件覆蓋不足，請核對Radar；不代表沒有重大事件。'
    return [dict(title='主要變化',text=first),dict(title='重要矛盾',text=second),dict(title='下一關卡',text=third)]

def build_daily_flex(snapshot):
    try:stamp=datetime.fromisoformat(snapshot.get('run_time','')).astimezone(ZoneInfo('Asia/Taipei')).strftime('%Y-%m-%d %H:%M 台灣時間')
    except (ValueError,TypeError):stamp=snapshot.get('run_date') or '時間缺失'
    header=box([text('每日市場研究','xl','#FFFFFF',weight='bold'),text('摘要時間：'+stamp,'xs','#D5E5F5'),text('延遲研究資料｜各市場交易日分別標示','xs','#D5E5F5'),dict(type='button',style='link',height='sm',color='#79C7FF',action=dict(type='uri',label='閱讀完整 Today →',uri=BASE))],backgroundColor=NAVY,paddingAll='16px')
    contents=[]
    for i,(item,tint) in enumerate(zip(compact_brief(snapshot),['#E8F6F3','#FFF3DB','#EAF3FF']),1):
        contents.append(box([text(f'{i:02}  '+item['title'],'sm',weight='bold'),text(item['text'],'sm')],backgroundColor=tint,paddingAll='12px',cornerRadius='8px',margin='sm'))
    contents.extend(market_card(r) for r in build_market_rows(snapshot))
    rate=snapshot.get('market_research',{}).get('rates',{}).get('us10y',{})
    rd,_=delta(rate.get('change_1d_bp'),' bp')
    contents.append(box([text('利率背景｜美債10Y '+price(rate.get('value'))+'%','sm',weight='bold'),text(rd+'｜'+str(rate.get('as_of') or 'N/A'),'xs'),text('來源：美國財政部｜'+str(rate.get('retrieval_status') or rate.get('status') or 'MISSING'),'xs',MUTED)],backgroundColor='#EDF4FC',paddingAll='10px',margin='md',cornerRadius='8px'))
    footer=box([dict(type='button',style='primary',color=BLUE,height='md',action=dict(type='uri',label='閱讀今日完整報告 → Today',uri=BASE)),link('Markets 商品圖表','markets.html'),link('Radar 事件證據','radar.html'),text('研究用途｜非即時可成交報價','xs',MUTED),text('沒有Trigger不下單；仍須核對Bid/Ask與Actual R:R。','xs',MUTED)],spacing='sm',paddingAll='16px')
    return dict(type='flex',altText='每日市場研究｜'+str(snapshot.get('run_date') or '')+'｜黃金・鋅・日圓・美元｜點開閱讀Today',contents=dict(type='bubble',size='mega',header=header,body=box(contents,backgroundColor='#F4F8FC',paddingAll='12px'),footer=footer))

def validate_structure(message):
    raw=json.dumps(message,ensure_ascii=False)
    if message.get('type')!='flex' or len(message.get('altText',''))>400 or len(json.dumps(message['contents'],ensure_ascii=False).encode())>30000:raise ValueError('Flex format/size limit')
    def walk(x):
        if isinstance(x,dict):
            if x.get('type')=='text' and (not isinstance(x.get('text'),str) or not x['text']):raise ValueError('empty text')
            if x.get('type')=='uri' and not x.get('uri','').startswith(BASE):raise ValueError('unexpected navigation URL')
            for v in x.values():walk(v)
        elif isinstance(x,list):
            for v in x:walk(v)
    walk(message)
    for forbidden in ('account_equity','execution_journal','LINE_USER_ID','LINE_CHANNEL_ACCESS_TOKEN'):
        if forbidden in raw:raise ValueError('private field in Flex')
    return len(raw.encode())

def write_preview(snapshot):
    """Approximate browser preview of the actual payload, not LINE-renderer certification."""
    import html
    msg=build_daily_flex(snapshot);validate_structure(msg)
    def render(x):
        typ=x.get('type');style=''
        if typ=='text':
            sizes={'xs':12,'sm':14,'lg':19,'xl':22,'xxl':28}
            return '<div style="font-size:'+str(sizes.get(x.get('size'),14))+'px;color:'+x.get('color',INK)+';font-weight:'+('700' if x.get('weight')=='bold' else '400')+';overflow-wrap:anywhere;flex:'+str(x.get('flex',1))+'">'+html.escape(x['text'])+'</div>'
        if typ=='image':return '<img width="40" height="40" src="'+html.escape(x['url'])+'" alt="商品圖示">'
        if typ=='button':return '<a class="button '+('primary' if x.get('style')=='primary' else '')+'" href="'+html.escape(x['action']['uri'])+'">'+html.escape(x['action']['label'])+'</a>'
        if typ=='box':
            style='display:flex;flex-direction:'+('row' if x['layout']=='horizontal' else 'column')+';gap:8px;align-items:'+('center' if x.get('alignItems') else 'stretch')+';background:'+x.get('backgroundColor','transparent')+';padding:'+x.get('paddingAll','0')+';border-radius:'+x.get('cornerRadius','0')+';margin-top:'+('12px' if x.get('margin') else '0')+';flex:'+str(x.get('flex',1))+';min-width:0;'
            return '<div style="'+style+'">'+''.join(render(c) for c in x['contents'])+'</div>'
        return ''
    page='<!doctype html><html lang="zh-Hant"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>LINE B｜閱讀預覽</title><style>body{margin:0;background:#E9F1F8;font:14px/1.55 Arial,sans-serif}.preview{max-width:430px;margin:auto;background:white}.button{display:block;text-align:center;text-decoration:none;color:#1264D9;padding:12px;min-height:24px}.primary{background:#1264D9;color:white;border-radius:8px}aside{padding:12px;color:#617487;max-width:406px;margin:auto}</style><aside>版本B網頁近似預覽；實際LINE顯示以手機為準。<br>可縮窄視窗檢查360／390／430px閱讀。<a href="./">返回Today</a></aside><main class="preview">'+''.join(render(msg['contents'][k]) for k in ('header','body','footer'))+'</main></html>'
    path=Path('public/line-preview.html');path.write_text(page,encoding='utf-8');return path
