"""Official Treasury par yields. Rates are percent; changes are basis points."""
from datetime import date, datetime, timezone
import math
import xml.etree.ElementTree as ET
import requests

BASE = 'https://home.treasury.gov/resource-center/data-chart-center/interest-rates/pages/xml'
SPECS = {'us2y':('daily_treasury_yield_curve','BC_2YEAR','US 2Y'),
         'us10y':('daily_treasury_yield_curve','BC_10YEAR','US 10Y'),
         'us30y':('daily_treasury_yield_curve','BC_30YEAR','US 30Y'),
         'real10y':('daily_treasury_real_yield_curve','TC_10YEAR','US 10Y real')}

def parse_xml(raw, field, today=None):
    today = today or date.today()
    root = ET.fromstring(raw)
    rows = {}
    for entry in root.iter():
        if entry.tag.split('}')[-1] != 'properties':
            continue
        fields = {c.tag.split('}')[-1]:c.text for c in entry}
        when = date.fromisoformat((fields.get('NEW_DATE') or '')[:10])
        if when >= today or fields.get(field) is None:
            continue
        try:
            value=float(fields[field])
        except (ValueError,TypeError):
            continue
        if math.isfinite(value) and -10 <= value <= 30:
            if when.isoformat() in rows and rows[when.isoformat()] != value:
                raise ValueError('conflicting_duplicate_date')
            rows[when.isoformat()]=value
    return [{'date':d,'value':v} for d,v in sorted(rows.items())]

def describe(points, key, url, today=None, retrieval='CURRENT_FETCH'):
    today=today or date.today()
    for point in points:
        value=point['value']
        when=date.fromisoformat(point['date'])
        if not isinstance(value,(int,float)) or not math.isfinite(value) or not -10 <= value <= 30 or when >= today:
            raise ValueError('invalid_history_observation')
    if [p['date'] for p in points] != sorted(set(p['date'] for p in points)):
        raise ValueError('invalid_history_dates')
    result={'status':'MISSING','name':SPECS[key][2],'unit':'percent','source':'US Treasury official XML',
            'source_grade':'A_OFFICIAL','source_url':url,'expected_update':'US business-day daily',
            'retrieval_status':retrieval,'as_of':None,'observations':len(points),'history':points}
    if not points:return result
    latest=points[-1]; age=(today-date.fromisoformat(latest['date'])).days
    if age < 0: return result
    def change(n):
        if len(points)<=n:return None
        if (date.fromisoformat(latest['date'])-date.fromisoformat(points[-n-1]['date'])).days > (7 if n==1 else 14):return None
        return round((latest['value']-points[-n-1]['value'])*100,2)
    result.update(status='AVAILABLE' if age<=7 else 'STALE',as_of=latest['date'],value=latest['value'],
                  age_days=age,change_1d_bp=change(1),change_5d_bp=change(5),
                  largest_gap_days=max([(date.fromisoformat(b['date'])-date.fromisoformat(a['date'])).days for a,b in zip(points,points[1:])] or [0]))
    return result

def fetch_rates(prior_snapshots=(), today=None):
    today=today or date.today(); payloads={}; errors={}
    for dataset in {v[0] for v in SPECS.values()}:
        try:
            chunks=[]
            for year in (today.year-1,today.year):
                response=requests.get(BASE,params={'data':dataset,'field_tdr_date_value':year},timeout=20)
                response.raise_for_status(); chunks.append(response.content)
            payloads[dataset]=chunks
        except Exception as exc: errors[dataset]=type(exc).__name__
    output={}
    for key,(dataset,field,_) in SPECS.items():
        url=f'{BASE}?data={dataset}&field_tdr_date_value={today.year}'
        try:
            points=[p for raw in payloads.get(dataset,[]) for p in parse_xml(raw,field,today)]
            points=sorted({p['date']:p for p in points}.values(),key=lambda x:x['date'])
            output[key]=describe(points,key,url,today)
        except Exception as exc:
            output[key]=describe([],key,url,today); errors[dataset]=type(exc).__name__
        if output[key]['status']=='MISSING':
            for snapshot in prior_snapshots:
                old=snapshot.get('market_research',{}).get('rates',{}).get(key,{})
                if old.get('source')!='US Treasury official XML' or old.get('source_grade')!='A_OFFICIAL':continue
                try:
                    rebuilt=describe(old.get('history',[]),key,url,today,'CARRY_FORWARD_LAST_VERIFIED')
                    if rebuilt['status']=='AVAILABLE':output[key]=rebuilt;break
                except (ValueError,TypeError,KeyError):continue
        output[key]['current_provider_error']=errors.get(dataset)
    return output
