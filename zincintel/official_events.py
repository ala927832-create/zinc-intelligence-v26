"""Official scheduled events only. A schedule is never an actual release."""
from datetime import datetime, date, timedelta, timezone
from zoneinfo import ZoneInfo
import re
import json
from pathlib import Path
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlsplit

URLS={'BLS':'https://www.bls.gov/schedule/news_release/bls.ics',
      'Fed':'https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm',
      'BoJ':'https://www.boj.or.jp/en/mopo/mpmsche_minu/index.htm',
      'NBS':'https://www.stats.gov.cn/english/PressRelease/ReleaseCalendar/'}
BLS_CACHE_PATH=Path('data/reference/bls_calendar_verified.json')
BLS_CACHE_MAX_DAYS=7
MONTHS={name:i for i,name in enumerate(['January','February','March','April','May','June','July','August','September','October','November','December'],1)}

def event(title,when,provider,exact=False):
    return {'title':title,'date':when.date().isoformat(),'sort_time':when.isoformat(),
            'taipei_display':when.astimezone(ZoneInfo('Asia/Taipei')).strftime('%Y-%m-%d %H:%M 台灣時間') if exact else when.date().isoformat()+f' {when.tzinfo}會議日／台灣公告時間未定',
            'time_precision':'EXACT' if exact else 'DATE_ONLY','source':provider,'source_url':URLS[provider],
            'status':'SCHEDULED_NOT_RELEASED','watch':'觀察公布後美元、利率與商品價格是否確認；避免把第一波反應直接當作突破。',
            'markets':'USD／Gold／Zinc' if provider!='BoJ' else 'USD/JPY／DXY／Gold'}

def parse_bls(raw):
    raw=re.sub(r'\r?\n[ \t]','',raw)
    out=[]
    for block in raw.split('BEGIN:VEVENT')[1:]:
        fields={}
        for line in block.splitlines():
            if ':' in line:
                k,v=line.split(':',1);fields[k]=v
        title=fields.get('SUMMARY','')
        if title.lower() not in ('consumer price index','employment situation'):continue
        item=next(((k,v) for k,v in fields.items() if k.startswith('DTSTART')),None)
        if not item:continue
        key,value=item
        if re.fullmatch(r'\d{8}T\d{6}Z',value):
            dt=datetime.strptime(value,'%Y%m%dT%H%M%SZ').replace(tzinfo=timezone.utc)
        elif 'TZID=' in key and re.fullmatch(r'\d{8}T\d{6}',value):
            zone=key.split('TZID=')[1]
            zone={'US-Eastern':'America/New_York','US/Eastern':'America/New_York'}.get(zone,zone)
            dt=datetime.strptime(value,'%Y%m%dT%H%M%S').replace(tzinfo=ZoneInfo(zone))
        else:continue
        out.append(event(title,dt,'BLS',True))
    return out

def parse_bls_list(raw):
    """Official monthly list; never infer a day or clock from release conventions."""
    soup=BeautifulSoup(raw,'html.parser');out=[]
    if 'Eastern Time' not in soup.get_text(' ',strip=True):return out
    for row in soup.select('table.release-list tr'):
        d,t,desc=(row.select_one('.'+k) for k in ('date-cell','time-cell','desc-cell'))
        if d is None or t is None or desc is None:continue
        title=desc.find('strong')
        title=title.get_text(' ',strip=True) if title else ''
        if title not in ('Consumer Price Index','Employment Situation'):continue
        try:
            dt=datetime.strptime(d.get_text(' ',strip=True)+' '+t.get_text(' ',strip=True),'%A, %B %d, %Y %I:%M %p').replace(tzinfo=ZoneInfo('America/New_York'))
        except ValueError:continue
        out.append(event(title,dt,'BLS',True))
    return out

def fetch_bls_months(now):
    """Independent official HTML fallback covering every month in the 45-day window."""
    months=sorted({(now.astimezone(ZoneInfo('Asia/Taipei')).date()+timedelta(days=i)).strftime('%Y/%m') for i in range(46)})
    out=[];attempts=[]
    for month in months:
        url=f'https://www.bls.gov/schedule/{month}_sched_list.htm'
        try:
            r=requests.get(url,timeout=12);r.raise_for_status();items=parse_bls_list(r.text)
            attempts.append({'url':url,'status':'VERIFIED_FETCH' if items else 'UNPARSED'})
            for x in items:x['source_url']=url
            out.extend(items)
        except Exception as exc:attempts.append({'url':url,'status':'UNAVAILABLE','error':type(exc).__name__})
    status='VERIFIED_FETCH' if all(x['status']=='VERIFIED_FETCH' for x in attempts) else 'PARTIAL' if out else 'UNAVAILABLE'
    return out,{'status':status,'checked_at':now.isoformat(),'url':attempts[0]['url'],'method':'OFFICIAL_MONTHLY_HTML_FALLBACK','attempts':attempts}

def parse_fed(raw):
    soup=BeautifulSoup(raw,'html.parser');out=[]
    for panel in soup.select('.panel'):
        heading=panel.select_one('.panel-heading')
        match=re.search(r'(20\d{2}) FOMC',heading.get_text(' ',strip=True) if heading else '')
        if not match:continue
        year=int(match[1])
        for row in panel.select('.fomc-meeting'):
            month=row.select_one('.fomc-meeting__month');days=row.select_one('.fomc-meeting__date')
            if not month or not days:continue
            month=month.get_text(' ',strip=True);days=days.get_text(' ',strip=True)
            if month not in MONTHS or not re.fullmatch(r'\d{1,2}-\d{1,2}\*?',days):continue
            day=int(re.findall(r'\d+',days)[-1])
            out.append(event('FOMC會議最後一日',datetime(year,MONTHS[month],day,tzinfo=ZoneInfo('America/New_York')),'Fed'))
    return out

def parse_boj(raw):
    soup=BeautifulSoup(raw,'html.parser');out=[]
    for table in soup.select('table'):
        if 'Date of MPM' not in table.get_text(' ',strip=True):continue
        heading=table.find('caption') or table.find_previous(['h2','h3','h4'])
        year_match=re.search(r'20\d{2}',heading.get_text() if heading else '')
        if not year_match:continue
        year=int(year_match[0])
        for row in table.select('tr'):
            cell=row.find('td')
            if not cell:continue
            text=re.sub(r'\([^)]*\)', '', cell.get_text(' ',strip=True))
            match=re.match(r'([A-Za-z]+)\.?\s+(\d{1,2})(?:\s*(?:and|-|,)\s*(\d{1,2}))?',text)
            if not match:continue
            month=next((v for k,v in MONTHS.items() if k.lower().startswith(match[1].lower())),None)
            if month:out.append(event('BoJ金融政策會議最後一日',datetime(year,month,int(match[3] or match[2]),tzinfo=ZoneInfo('Asia/Tokyo')),'BoJ'))
    return out

def parse_nbs(raw):
    soup=BeautifulSoup(raw,'html.parser');out=[]
    match=re.search(r'Regular Press Release Calendar of NBS in (20\d{2})',soup.get_text(' ',strip=True))
    if not match:return out
    year=int(match[1])
    for row in soup.select('table tr'):
        cells=row.find_all(['td','th'],recursive=False)
        if len(cells)!=14:continue
        title=cells[1].get_text(' ',strip=True)
        if title not in ('National Economic Performance','Monthly Report on Purchasing Managers’ Index (PMI)',"Monthly Report on Purchasing Managers' Index (PMI)"):continue
        next_row=row.find_next_sibling('tr')
        if next_row is None:continue
        times=next_row.find_all(['td','th'],recursive=False);counter=0
        for month,cell in enumerate(cells[2:],1):
            days=re.findall(r'(\d{1,2})/[A-Za-z]+',cell.get_text(' ',strip=True))
            if not days:continue
            if counter>=len(times):break
            clocks=re.findall(r'(\d{1,2}):(\d{2})',times[counter].get_text(' ',strip=True));counter+=1
            if len(clocks)!=len(days):continue
            for day,(hour,minute) in zip(days,clocks):
                item=event('中國國民經濟運行情況' if title=='National Economic Performance' else '中國官方PMI',datetime(year,month,int(day),int(hour),int(minute),tzinfo=ZoneInfo('Asia/Shanghai')),'NBS',True)
                item['markets']='LME Zinc／SHFE Zinc／USD'
                item['watch']='核對工業生產、投資或PMI與鋅需求／價格反應；缺市場共識時不判定超出預期。'
                out.append(item)
    return out

def save_bls_cache(events,now,path):
    if path is None:return
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps({'verified_at':now.isoformat(),'events':events},ensure_ascii=False,indent=2),encoding='utf-8')

def cached_bls(now,path):
    if path is None:return [],None
    try:
        data=json.loads(Path(path).read_text(encoding='utf-8'))
        verified=datetime.fromisoformat(data['verified_at'])
        age=(now-verified).total_seconds()/86400
        if not 0<=age<=BLS_CACHE_MAX_DAYS:return [],None
        items=[]
        for x in data['events']:
            url=urlsplit(x['source_url']);dt=datetime.fromisoformat(x['sort_time'])
            if x['source']!='BLS' or x['title'] not in ('Consumer Price Index','Employment Situation') or url.scheme!='https' or url.hostname!='www.bls.gov' or not url.path.startswith('/schedule/') or x['time_precision']!='EXACT' or dt.tzinfo is None or x['date']!=dt.date().isoformat():return [],None
            item=event(x['title'],dt,'BLS',True);item['source_url']=x['source_url']
            item['verification_status']='CARRY_FORWARD_LAST_VERIFIED';item['last_verified_at']=data['verified_at'];items.append(item)
        return items,{'last_verified_at':data['verified_at'],'cache_age_days':round(age,3),'cache_max_days':BLS_CACHE_MAX_DAYS}
    except (OSError,ValueError,KeyError,TypeError):return [],None

def fetch_events(now=None,*,bls_cache_path=BLS_CACHE_PATH):
    now=now or datetime.now(timezone.utc);out=[];sources={}
    for name,parser in [('BLS',parse_bls),('Fed',parse_fed),('BoJ',parse_boj),('NBS',parse_nbs)]:
        try:
            response=requests.get(URLS[name],timeout=15);response.raise_for_status()
            source_url=URLS[name]
            if name=='NBS':
                response.encoding='utf-8'
                index=BeautifulSoup(response.text,'html.parser')
                link=next((a for a in index.select('a[href]') if f'Calendar of NBS in {now.year}' in a.get_text(' ',strip=True)),None)
                if link is None:raise ValueError('current_year_calendar_not_found')
                source_url=urljoin(URLS[name],link['href'])
                if urlsplit(source_url).hostname!='www.stats.gov.cn':raise ValueError('unexpected_calendar_host')
                response=requests.get(source_url,timeout=15);response.raise_for_status();response.encoding='utf-8'
            events=parser(response.text)
            if name=='BLS' and not events:raise ValueError('empty_bls_ics')
            for item in events:item['source_url']=source_url
            if name=='BLS':save_bls_cache(events,now,bls_cache_path)
            sources[name]={'status':'VERIFIED_FETCH' if events else 'UNPARSED','checked_at':now.isoformat(),'url':source_url}
            out.extend(events)
        except Exception as exc:
            if name=='BLS':
                events,state=fetch_bls_months(now);state['primary_error']=type(exc).__name__
                if state['status']=='VERIFIED_FETCH':save_bls_cache(events,now,bls_cache_path)
                elif not events:
                    cached,meta=cached_bls(now,bls_cache_path)
                    if cached:
                        events=cached;state.update(meta);state['status']='CARRY_FORWARD_LAST_VERIFIED';state['method']='LAST_VERIFIED_OFFICIAL_CALENDAR'
                sources[name]=state;out.extend(events)
            else:sources[name]={'status':'UNAVAILABLE','error':type(exc).__name__,'checked_at':now.isoformat(),'url':URLS[name]}
    day=now.astimezone(ZoneInfo('Asia/Taipei')).date()
    upcoming=[]
    for item in out:
        event_day=date.fromisoformat(item['date'])
        if day<=event_day<=day+timedelta(days=45):
            if item['time_precision']=='EXACT' and datetime.fromisoformat(item['sort_time'])<now:continue
            upcoming.append(item)
    return {'checked_at':now.isoformat(),'sources':sources,'upcoming':sorted(upcoming,key=lambda x:datetime.fromisoformat(x['sort_time']).timestamp()),
            'coverage':'BLS CPI/Employment, Fed, BoJ, NBS economic performance/PMI; unscheduled news not integrated',
            'news_status':'NOT_CHECKED'}

def event_panel(snapshot):
    from html import escape as e
    data=snapshot.get('market_research',{}).get('events',{})
    checked=data.get('checked_at')
    try:today=datetime.fromisoformat(checked).astimezone(ZoneInfo('Asia/Taipei')).date()
    except (TypeError,ValueError):today=None
    near=[];later=[]
    for x in data.get('upcoming',[]):
        try:day=datetime.fromisoformat(x['sort_time']).astimezone(ZoneInfo('Asia/Taipei')).date() if x.get('time_precision')=='EXACT' else date.fromisoformat(x['date'])
        except (KeyError,ValueError):later.append(x);continue
        (near if today and today<=day<today+timedelta(days=7) else later).append(x)
    def table(items):
        rows=''.join(f"<tr><td>{e(x['title'])}</td><td>{e(x['taipei_display'])}</td><td>{e(x['markets'])}</td><td>公布前：核對日期、價格位置與既有計畫。<br>公布後：{e(x['watch'])}<br>檢討：尚未匯入實際值與市場共識，不判定驚喜幅度。</td><td><a href='{e(x['source_url'])}'>{e(x['source'])}</a> · {e(x['status'])}<br>{e(x.get('verification_status','CURRENT_FETCH'))} {e(x.get('last_verified_at',''))}</td></tr>" for x in items)
        return "<div class='table-wrap'><table><tr><th>事件</th><th>時間／日期</th><th>商品</th><th>觀察流程</th><th>來源／狀態</th></tr>"+(rows or '<tr><td colspan=5>此區間無已驗證排程；不代表沒有重大事件。</td></tr>')+'</table></div>'
    states=''.join(f"<li><a href='{e(v.get('url',''))}'>{e(k)}</a>: {e(v.get('status'))} · {e(v.get('checked_at'))} · {e(v.get('method','PRIMARY'))} · 最後核對 {e(v.get('last_verified_at') or v.get('checked_at'))} · 沿用 {e(str(v.get('cache_age_days','N/A')))} 日</li>" for k,v in data.get('sources',{}).items())
    return ("<section class='card' id='event-clock'><h2>近期事件 · Official event clock</h2><p>預設展開快照日起未來7日；較遠排程收合。已排定事件不是實際公布結果，日期型會議不推算公告時刻。</p><h3>未來7日</h3>"+table(near)+f"<details><summary>其餘已驗證事件（{len(later)}項；45日範圍）</summary>"+table(later)+"</details><details><summary>事件來源與覆蓋狀態</summary><ul>"+states+"</ul></details><p>排程可修訂，以官方連結為準。突發新聞未查核；中國僅涵蓋NBS國民經濟與PMI。來源缺失時不推算事件。</p></section>")
