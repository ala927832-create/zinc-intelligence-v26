"""Version B daily Flex layout. Public research only; no execution/account data."""
from __future__ import annotations
import json, math
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
from .dashboard_v27 import _today_market_metrics, _market_series
from .daily_brief import build_brief

BASE='https://ala927832-create.github.io/zinc-intelligence-v26/'
NAVY='#252C33'; BLUE='#176C66'; INK='#202A30'; UP='#23D0B4'; DOWN='#FF727D'; MUTED='#617487'

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

def board_row(r,snapshot):
    """A continuous graphite board row, not a standalone nested card."""
    identity={'gold':'COMEX連續參考','lme_zinc':'LME Cash','usdjpy':'USD/JPY','dxy':'DXY','shfe_zinc':'SHFE '+str(_market_series(snapshot,'shfe_zinc').get('latest_contract') or '合約缺失')}[r['key']]
    heading=dict(type='box',layout='horizontal',spacing='sm',alignItems='center',contents=[
        dict(type='image',url=BASE+'assets/line-icons-b1/'+r['key']+'.png',size='28px',aspectRatio='1:1',flex=0),
        text(r['label'],'md','#FFFFFF',weight='bold',flex=1),text(identity,'xs','#C6CCD0',flex=1)])
    d,color=delta(r['change'])
    quotes=dict(type='box',layout='horizontal',spacing='sm',alignItems='center',contents=[
        box([text(price(r['value']),'xl','#FFFFFF',weight='bold'),text(r['unit'],'xs','#CED2D4')],flex=1),text(d,'sm',color,weight='bold',flex=0)])
    contents=[heading,quotes]
    if r['key']=='lme_zinc':
        series=_market_series(snapshot,'lme_zinc');m=_today_market_metrics(snapshot,'lme_zinc')
        d,c=delta(valid_change(series,m))
        contents.append(dict(type='box',layout='horizontal',spacing='sm',alignItems='center',contents=[text('3M參考收盤 '+price(m.get('technical_close'))+' USD/t','xs','#CED2D4',flex=1),text(d,'sm',c,flex=0)]))
    return box(contents,spacing='sm',paddingTop='12px',paddingBottom='12px')

def date_summary(snapshot,rows):
    groups={}
    dates=[(r['label'],r['as_of']) for r in rows]+[('LME 3M',_market_series(snapshot,'lme_zinc').get('as_of')),('美債10Y',snapshot.get('market_research',{}).get('rates',{}).get('us10y',{}).get('as_of'))]
    for label,day in dates:groups.setdefault(day or '日期缺失',[]).append(label)
    if len(groups)==1:
        return ['行情交易日：'+next(iter(groups))]
    return ['行情交易日（異日集中列示）']+[day+'｜'+'、'.join(labels) for day,labels in sorted(groups.items(),reverse=True)]

def observation(snapshot):
    phrases=[]
    for key,label in [('gold','黃金'),('lme_zinc','鋅3M')]:
        m=_today_market_metrics(snapshot,key);p,ema=m.get('technical_close'),m.get('ema20')
        if finite(p) and finite(ema):
            phrases.append(label+('在EMA20下方，反彈結構仍待確認。' if p<ema else '在EMA20上方，觀察後續收盤是否守穩。'))
    return ''.join(phrases) or '結構證據不足，保留No Trade；完整條件見Today。'

def compact_brief(snapshot):
    """Short mobile wording of the same frozen facts; no extra signal model."""
    full=build_brief(snapshot);first=full[0]['text']
    key=full[0]['url'].removeprefix('market-').removesuffix('.html')
    if key in ('gold','lme_zinc','usdjpy','dxy','shfe_zinc'):
        m=_today_market_metrics(snapshot,key);change=m.get('change_1d')
        labels={'gold':'黃金參考Close','lme_zinc':'LME 3M參考Close','usdjpy':'USD/JPY','dxy':'DXY','shfe_zinc':'SHFE鋅'}
        if finite(change):first=f"{labels[key]} {change:+.2f}%。"
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
    rows=build_market_rows(snapshot)
    header=box([text('每日市場簡報','xl',weight='bold')]+[text(x,'xs',MUTED) for x in date_summary(snapshot,rows)],backgroundColor='#F2EFE8',paddingAll='16px')
    summary=[text('30秒重點','lg',weight='bold')]
    for item,color in zip(compact_brief(snapshot),['#176C66','#A66B27','#56616C']):
        summary.append(dict(type='box',layout='horizontal',spacing='sm',margin='sm',contents=[text(item['title'],'sm',color,weight='bold',flex=0),text(item['text'],'sm',flex=1)]))
    board=[text('主要行情','lg','#FFFFFF',weight='bold')]
    for r in rows:
        board.extend([board_row(r,snapshot),dict(type='separator',color='#596168')])
    rate=snapshot.get('market_research',{}).get('rates',{}).get('us10y',{})
    rd,rc=delta(rate.get('change_1d_bp'),' bp')
    board.append(box([text('利率背景｜美債10Y '+price(rate.get('value'))+('%' if finite(rate.get('value')) else ''),'sm','#FFFFFF'),text(rd,'sm',rc)],spacing='sm',paddingTop='12px'))
    contents=[box(summary,backgroundColor='#FFFCF6',paddingAll='14px',cornerRadius='8px'),box(board,backgroundColor=NAVY,paddingAll='14px',cornerRadius='8px',margin='md'),box([text('怎麼看今天？','lg',weight='bold'),text(observation(snapshot)),text('USD/JPY下跌代表日圓升值。','xs',MUTED)],backgroundColor='#FFFCF6',paddingAll='14px',spacing='sm',margin='md',cornerRadius='8px')]
    footer=box([dict(type='button',style='primary',color=BLUE,height='md',action=dict(type='uri',label='閱讀完整 Today →',uri=BASE)),dict(type='box',layout='horizontal',contents=[link('Markets 圖表','markets.html'),link('Radar 事件','radar.html')]),text('研究用途｜延遲報價｜非即時可成交價格','xs',MUTED)],paddingAll='14px',spacing='sm',backgroundColor='#F2EFE8')
    return dict(type='flex',altText='每日市場簡報 B1｜黃金・鋅・日圓・美元｜閱讀Today',contents=dict(type='bubble',size='mega',header=header,body=box(contents,backgroundColor='#F2EFE8',paddingAll='10px'),footer=footer))

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
            sizes={'xs':12,'sm':14,'md':16,'lg':19,'xl':22,'xxl':28}
            return '<div style="font-size:'+str(sizes.get(x.get('size'),14))+'px;color:'+x.get('color',INK)+';font-weight:'+('700' if x.get('weight')=='bold' else '400')+';overflow-wrap:anywhere;flex:'+str(x.get('flex',1))+'">'+html.escape(x['text'])+'</div>'
        if typ=='separator':return '<hr style="border:0;border-top:1px solid '+x.get('color','#DDD')+';margin:0">'
        if typ=='image':return '<img width="28" height="28" src="'+html.escape(x['url'])+'" alt="商品圖示">'
        if typ=='button':return '<a class="button '+('primary' if x.get('style')=='primary' else '')+'" href="'+html.escape(x['action']['uri'])+'">'+html.escape(x['action']['label'])+'</a>'
        if typ=='box':
            style='display:flex;flex-direction:'+('row' if x['layout']=='horizontal' else 'column')+';gap:8px;align-items:'+('center' if x.get('alignItems') else 'stretch')+';background:'+x.get('backgroundColor','transparent')+';padding:'+x.get('paddingAll','0')+';padding-top:'+x.get('paddingTop',x.get('paddingAll','0'))+';padding-bottom:'+x.get('paddingBottom',x.get('paddingAll','0'))+';border-radius:'+x.get('cornerRadius','0')+';margin-top:'+('12px' if x.get('margin') else '0')+';flex:'+str(x.get('flex',1))+';min-width:0;'
            return '<div style="'+style+'">'+''.join(render(c) for c in x['contents'])+'</div>'
        return ''
    page='<!doctype html><html lang="zh-Hant"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>LINE B1｜閱讀預覽</title><style>body{margin:0;background:#F2EFE8;font:14px/1.55 Arial,sans-serif}.preview{max-width:430px;margin:auto;background:white}.button{display:block;text-align:center;text-decoration:none;color:#176C66;padding:12px;min-height:24px}.primary{background:#176C66;color:white;border-radius:8px}aside{padding:12px;color:#617487;max-width:406px;margin:auto}</style><aside>B1網頁近似預覽；實際LINE顯示以手機為準。<br>可縮窄視窗檢查360／390／430px閱讀。<a href="./">返回Today</a></aside><main class="preview">'+''.join(render(msg['contents'][k]) for k in ('header','body','footer'))+'</main></html>'
    path=Path('public/line-preview.html');path.write_text(page,encoding='utf-8');return path
