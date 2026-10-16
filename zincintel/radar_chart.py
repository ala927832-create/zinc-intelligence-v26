"""Native SVG history comparison: aligned dates, original values in tooltip."""
import json

def comparison_chart(snapshot):
    research=snapshot.get('market_research',{})
    sources=[]
    for key,label in [('us2y','2Y'),('us10y','10Y'),('us30y','30Y'),('real10y','10Y Real')]:
        r=research.get('rates',{}).get(key,{})
        sources.append({'key':key,'label':label,'unit':'%','points':[{'date':p['date'],'value':p['value']} for p in r.get('history',[])]})
    for key,label in [('dxy','DXY'),('gold','Gold'),('usdjpy','USD/JPY')]:
        s=research.get('cross_assets',{}).get(key,{})
        sources.append({'key':key,'label':label,'unit':s.get('unit',''),'points':[{'date':p['date'],'value':p['close']} for p in s.get('chart_points',[])]})
    s=research.get('close_series',{})
    sources.append({'key':'lme_zinc','label':'LME 3M Close','unit':'USD/t','points':[{'date':p['date'],'value':p['close']} for p in s.get('chart_points',[])]})
    payload=json.dumps(sources,ensure_ascii=False).replace('<','\\u003c')
    return """<section class='card' id='macro-history'><h2>歷史比較 · 同步日期查值</h2><p>上圖為原始殖利率%；下圖為DXY與商品起點＝100。兩圖共用日期與游標；缺值不插補，超過7日的缺口斷線。標準化比較不是相關性或因果估計。</p>
<div><label>期間 <select id='radar-window'><option value='60'>60筆日期</option><option value='120' selected>120筆日期</option><option value='all'>全部</option></select></label> <label>商品 <select id='radar-asset'><option value='gold'>黃金</option><option value='lme_zinc'>LME 3M Close</option><option value='usdjpy'>USD/JPY</option></select></label></div>
<div id='radar-history-legend'></div><svg id='radar-history-svg' viewBox='0 0 960 480' style='width:100%;background:#0b2f4f;border-radius:8px;touch-action:pan-y' role='img' aria-label='Rates and indexed price history'></svg><p id='radar-history-tip' aria-live='polite'>移動滑鼠或觸碰圖表，查看相同日期的原始數值。</p>
<script type='application/json' id='radar-history-data'>"""+payload+"""</script><script>(()=>{
const all=JSON.parse(document.getElementById('radar-history-data').textContent),svg=document.getElementById('radar-history-svg'),tip=document.getElementById('radar-history-tip'),period=document.getElementById('radar-window'),asset=document.getElementById('radar-asset');
const colors=['#59d7ff','#ffb454','#c69cff','#4ed6a5','#f4d35e','#ff8b98'];let active=[],dates=[],maps=[],hover='';
const esc=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function render(){active=all.filter(s=>['us2y','us10y','us30y','real10y','dxy',asset.value].includes(s.key));maps=active.map(s=>new Map(s.points.map(p=>[p.date,p.value])));dates=[...new Set(active.flatMap(s=>s.points.map(p=>p.date)))].sort();if(period.value!=='all')dates=dates.slice(-Number(period.value));if(dates.length<2){svg.innerHTML='<text x="20" y="40" fill="white">資料不足</text>';return;}
const t0=Date.parse(dates[0]),t1=Date.parse(dates.at(-1)),x=d=>65+(Date.parse(d)-t0)/(t1-t0)*865;let out='';
const baseDate=dates.find(d=>maps[4]?.has(d)&&maps[5]?.has(d));
for(let pane=0;pane<2;pane++){const top=pane?265:20,bottom=pane?435:190;let sets=active.map((s,i)=>{const pts=dates.filter(d=>maps[i].has(d)&&(!pane||(baseDate&&d>=baseDate))).map(d=>({date:d,value:maps[i].get(d)}));const base=baseDate?maps[i].get(baseDate):null;return pts.map(p=>({...p,plot:pane?(base>0?p.value/base*100:null):p.value}));});
const vals=sets.flatMap((s,i)=>(pane?i>=4:i<4)?s.map(p=>p.plot).filter(v=>Number.isFinite(v)):[]);if(!vals.length)continue;let lo=Math.min(...vals),hi=Math.max(...vals);if(lo===hi){lo-=1;hi+=1;}let pad=(hi-lo)*.1;lo-=pad;hi+=pad;const y=v=>bottom-(v-lo)/(hi-lo)*(bottom-top);
for(let k=0;k<=4;k++){let v=lo+(hi-lo)*k/4,yy=y(v);out+=`<line x1="65" x2="930" y1="${yy}" y2="${yy}" stroke="#31556e"/><text x="59" y="${yy+4}" text-anchor="end" fill="#bed0dc" font-size="12">${v.toFixed(2)}${pane?'':'%'}</text>`;}
sets.forEach((pts,i)=>{if((pane?i<4:i>=4))return;let path='',last=null;pts.forEach(p=>{if(!Number.isFinite(p.plot))return;let connected=last&&(Date.parse(p.date)-Date.parse(last))/86400000<=7;path+=(connected?'L':'M')+x(p.date)+','+y(p.plot);last=p.date;});out+=`<path d="${path}" fill="none" stroke="${colors[i]}" stroke-width="2" ${i===3?'stroke-dasharray="5 4"':''}/>`;});
if(hover&&dates.includes(hover))out+=`<line x1="${x(hover)}" x2="${x(hover)}" y1="${top}" y2="${bottom}" stroke="white" stroke-dasharray="3 3"/>`;
out+=`<text x="65" y="${bottom+20}" fill="#bed0dc" font-size="12">${dates[0]}</text><text x="495" y="${bottom+20}" fill="#bed0dc" text-anchor="middle" font-size="12">${dates[Math.floor(dates.length/2)]}</text><text x="930" y="${bottom+20}" fill="#bed0dc" text-anchor="end" font-size="12">${dates.at(-1)}</text>`;
}svg.innerHTML=out;document.getElementById('radar-history-legend').innerHTML=active.map((s,i)=>`<span style="display:inline-block;margin:8px;color:${colors[i]};background:#0b2f4f;padding:3px 7px">${esc(s.label)} ${i<4?'%':'起點100'}</span>`).join('');}
svg.addEventListener('pointermove',ev=>{if(!dates.length)return;const box=svg.getBoundingClientRect(),ratio=Math.max(0,Math.min(1,((ev.clientX-box.left)/box.width*960-65)/865)),t=Date.parse(dates[0])+ratio*(Date.parse(dates.at(-1))-Date.parse(dates[0]));hover=dates.reduce((a,b)=>Math.abs(Date.parse(a)-t)<Math.abs(Date.parse(b)-t)?a:b);tip.textContent=hover+' ｜ '+active.map((s,i)=>s.label+': '+(maps[i].has(hover)?maps[i].get(hover).toFixed(4)+' '+s.unit:'N/A（當日缺值）')).join(' ｜ ');render();});period.addEventListener('change',()=>{hover='';render();});asset.addEventListener('change',()=>{hover='';render();});render();})()</script></section>"""
