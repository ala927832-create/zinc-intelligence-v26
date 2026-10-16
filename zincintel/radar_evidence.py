"""Display-only evidence interpretation; does not grant trade permission."""
from .dashboard_v27 import _today_market_metrics, _market_series

ASSETS=[('gold','黃金'),('usdjpy','美元／日圓'),('dxy','美元指數'),('lme_zinc','LME鋅'),('shfe_zinc','SHFE鋅')]
CONDITIONS={
'gold':('反轉觀察：Close重回EMA20且後續收盤守穩，核對實質利率與美元；續跌觀察：反彈受阻EMA20後再轉弱。','反彈未能站回EMA20，或實質利率／美元轉升而金價轉弱。','ETF資金、CFTC部位與期貨OI尚未完成整合。'),
'usdjpy':('USD/JPY與美日同期限利差同步確認後再評估；USD/JPY下跌代表日圓升值。','價格與利差方向不一致，或BoJ／官方干預消息改變原有條件。','缺日本2Y與可核對干預證據；美國2Y不能取代美日利差。'),
'dxy':('Close、EMA20與5日變動同向，再核對相對利率及主要成分貨幣。','當日走勢與中期分類相反且後續延續，須重審原有美元方向。','缺其他國家同期限利率與成分貢獻；不能只用美債判斷美元。'),
'lme_zinc':('3M Close先核對EMA20，再核對同日期Cash−3M與連續庫存變化；TC獨立按週觀察。','美元下降但鋅價持續走弱，或價格與實體證據背離；追查供需，不能直接歸因。','Cash不是3M Close；庫存與TC頻率不同；LME仍Close-only，無K線觸發。'),
'shfe_zinc':('核對明確合約的價格結構、成交量與OI，再比較人民幣調整後LME走勢。','價格突破未獲量／OI確認，或換月造成價格斷層，撤回突破解讀。','跨市比價尚缺稅費、匯率與套利成本完整處理；不直接套用LME結論。')}

def evidence_rows(snapshot):
    from .radar import _aligned
    rates=snapshot.get('market_research',{}).get('rates',{})
    dxy=_market_series(snapshot,'dxy');result=[]
    for key,label in ASSETS:
        series=_market_series(snapshot,key);m=_today_market_metrics(snapshot,key)
        direction=snapshot.get('decision_book',{}).get('markets',{}).get(key,{}).get('direction') or 'UNDETERMINED'
        ret=m.get('change_1d');five=m.get('change_5d')
        conflict='日期／資料不足，尚不能判定當日與中期證據。'
        if ret is not None:
            action='上漲' if ret>0 else '下跌' if ret<0 else '持平'
            opposite=(ret>0 and 'BEAR' in direction) or (ret<0 and 'BULL' in direction)
            conflict=f'當日{action} {ret:+.2f}%；中期 {direction}。'+('當日反向變動尚未推翻中期結構，須等待後續收盤驗證。' if opposite else '當日與中期分類分開判讀；一次同向不等於持續確認。')
            if five is not None:conflict+=f' 5日 {five:+.2f}%。'
        factor='real10y' if key=='gold' else 'us2y'
        aligned=_aligned(rates.get(factor,{}),series)
        macro='日期／資料不足，宏觀順逆風未確認。'
        if aligned:
            day,bp,change=aligned
            if key in ('lme_zinc','shfe_zinc'):
                # Currency comparison must use the exact same latest pair of dates.
                currency=_aligned({'status':dxy.get('status'),'as_of':dxy.get('as_of'),'history':[{'date':p['date'],'value':p['close']} for p in dxy.get('chart_points',[]) if isinstance(p.get('close'),(float,int))]},series)
                macro=f'{day}：美國2Y {bp:+.1f} bp；只作外部背景，不代表鋅供需。'
                if currency:
                    dates=sorted(set(p['date'] for p in dxy.get('chart_points',[])) & set(p['date'] for p in series.get('chart_points',[])))
                    dp={p['date']:p['close'] for p in dxy.get('chart_points',[])}
                    if len(dates)>=2:
                        fx=(dp[dates[-1]]/dp[dates[-2]]-1)*100
                        macro+=f' 同步DXY {fx:+.2f}%；'+('美元下降但鋅下跌：相對表現偏弱，原因未確認。' if fx<-.01 and change<-.01 else '美元與鋅只做同日方向比較，非因果結論。')
            else:
                expected=-1 if key=='gold' else 1
                verdict='變動接近零，辨識力不足' if abs(bp)<.5 or abs(change)<.01 else '當日管道一致，未證明因果' if bp*change*expected>0 else '當日管道衝突，其他因素待查'
                factor_label='10Y實質殖利率' if key=='gold' else '美國2Y'
                channel=('實質利率下降，黃金機會成本管道為順風' if bp<0 else '實質利率上升，黃金機會成本管道為逆風' if bp>0 else '實質利率持平') if key=='gold' else '美國利率只提供背景，相對利差仍待核對'
                macro=f'{day}：{factor_label} {bp:+.1f} bp，Close {change:+.2f}%；{channel}；{verdict}。'
        evidence='專屬證據尚未完成；不把宏觀背景充當商品確認。'
        if key=='lme_zinc':
            market=snapshot.get('market',{});src=market.get('field_sources',{});parts=[]
            for field,name,unit in [('lme_cash','Cash','USD/t'),('lme_3m','3M報價','USD/t'),('lme_inventory_t','庫存','t'),('tc_usd_t','TC','USD/dmt')]:
                v=market.get(field);meta=src.get(field,{})
                parts.append(f'{name} {v if v is not None else "N/A"} {unit}｜{meta.get("as_of") or "日期缺失"}｜{meta.get("provider") or "來源缺失"}')
            a,b=src.get('lme_cash',{}).get('as_of'),src.get('lme_3m',{}).get('as_of')
            if a and a==b and all(isinstance(market.get(k),(float,int)) for k in ('lme_cash','lme_3m')):parts.append(f'同日Cash−3M {market["lme_cash"]-market["lme_3m"]:+.2f} USD/t｜{a}')
            evidence='；'.join(parts)+'。水準不是變化；不同日期不合併確認。'
        elif key=='shfe_zinc':evidence=f'獨立SHFE序列｜{series.get("as_of") or "N/A"}；合約及量／OI詳見商品頁，未在此宣稱資金確認。'
        if key=='shfe_zinc':
            latest=series.get('latest_session') or {}
            evidence+=f' 合約 {series.get("latest_contract") or "N/A"}；成交量 {latest.get("volume", "N/A")}；OI {series.get("latest_open_interest", "N/A")}。水準不等於增減。'
        if key in ('gold','usdjpy','dxy'):
            evidence=f'價格結構基準 {m.get("change_basis") or "N/A"}｜{series.get("as_of") or "N/A"}；EMA20 {m.get("ema20") if m.get("ema20") is not None else "N/A"}；{m.get("long_label") or "長均線"} {m.get("long_average") if m.get("long_average") is not None else "N/A"}。專屬資金／政策證據尚未完成，不作確認。'
        confirm,refute,missing=CONDITIONS[key]
        result.append(dict(key=key,label=label,direction=direction,as_of=series.get('as_of') or 'N/A',technical=conflict,macro=macro,evidence=evidence,confirm=confirm,refute=refute,missing=missing))
    return result
