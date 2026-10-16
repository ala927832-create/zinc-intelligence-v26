import unittest
from datetime import datetime,timezone
from copy import deepcopy
from unittest.mock import patch
from zincintel.official_events import parse_bls,parse_fed,parse_boj,parse_nbs,fetch_events
from zincintel.daily_brief import build_brief
from zincintel.radar_chart import comparison_chart

class RadarUpgradeTest(unittest.TestCase):
    def test_bls_summer_winter_and_folded_lines(self):
        raw='BEGIN:VEVENT\nSUMMARY:Consumer Price Index\nDTSTART;TZID=US-Eastern:20261014T083000\nEND:VEVENT\nBEGIN:VEVENT\nSUMMARY:Employment Situation\nDTSTART;TZID=America/New_York:20261106T083000\nEND:VEVENT'
        events=parse_bls(raw)
        self.assertIn('20:30',events[0]['taipei_display'])
        self.assertIn('21:30',events[1]['taipei_display'])
        self.assertEqual(parse_bls(raw.replace('TZID=US-Eastern:','VALUE=DATE:').split('END:VEVENT')[0]),[])

    def test_fed_date_is_not_fake_exact_release_time(self):
        raw='<div class="panel"><div class="panel-heading">2026 FOMC Meetings</div><div class="fomc-meeting"><div class="fomc-meeting__month">October</div><div class="fomc-meeting__date">27-28</div></div></div>'
        event=parse_fed(raw)[0]
        self.assertEqual(event['date'],'2026-10-28')
        self.assertEqual(event['time_precision'],'DATE_ONLY')
        self.assertIn('時間未定',event['taipei_display'])

    def test_boj_uses_second_meeting_day_and_caption_year(self):
        raw='<table><caption>Table : 2026</caption><tr><th>Date of MPM</th></tr><tr><td>Oct. 29 (Thurs.), 30 (Fri.)</td></tr></table>'
        self.assertEqual(parse_boj(raw)[0]['date'],'2026-10-30')

    def test_fetch_failure_is_not_no_event_claim(self):
        with patch('zincintel.official_events.requests.get',side_effect=TimeoutError):
            data=fetch_events(datetime(2026,10,16,tzinfo=timezone.utc))
        self.assertEqual(data['upcoming'],[])
        self.assertTrue(all(x['status']=='UNAVAILABLE' for x in data['sources'].values()))
        self.assertEqual(data['news_status'],'NOT_CHECKED')

    def test_nbs_month_columns_and_times_stay_aligned(self):
        cells=['19/Mon','……','16/Mon','16/Thu','18/Mon','16/Tue','15/Wed','17/Mon','15/Tue','19/Mon','16/Mon','15/Tue']
        raw='<h1>Regular Press Release Calendar of NBS in 2026</h1><table><tr><td>1</td><td>National Economic Performance</td>'+''.join('<td>'+x+'</td>' for x in cells)+'</tr><tr>'+('<td>10:00</td>'*11)+'</tr></table>'
        events=parse_nbs(raw)
        october=next(x for x in events if x['date']=='2026-10-19')
        self.assertIn('10:00 台灣時間',october['taipei_display'])
        self.assertEqual(len(events),11)

    def test_summary_deterministic_non_mutating_missing_data(self):
        snapshot={};original=deepcopy(snapshot)
        a=build_brief(snapshot)
        self.assertEqual(a,build_brief(snapshot))
        self.assertEqual(len(a),3)
        self.assertEqual(snapshot,original)
        self.assertIn('不代表沒有重大事件',a[2]['text'])

    def test_chart_exposes_units_common_baseline_and_missing_tooltip(self):
        markup=comparison_chart({})
        self.assertIn('maps[4]?.has(d)&&maps[5]?.has(d)',markup)
        self.assertIn('N/A（當日缺值）',markup)
        self.assertIn('60筆日期',markup)
        self.assertNotIn('atr14',markup)

class RadarEvidenceTest(unittest.TestCase):
    def test_bls_html_fallback_dst_and_requires_explicit_timezone(self):
        from zincintel.official_events import parse_bls_list
        raw='<p>All times Eastern Time</p><table class="release-list"><tr><td class="date-cell">Friday, November 6, 2026</td><td class="time-cell">08:30 AM</td><td class="desc-cell"><strong>Employment Situation</strong></td></tr></table>'
        self.assertIn('2026-11-06 21:30',parse_bls_list(raw)[0]['taipei_display'])
        self.assertEqual(parse_bls_list(raw.replace('Eastern Time','Unknown')),[])

    def test_bls_failure_uses_official_html_and_reports_partial_coverage(self):
        from zincintel.official_events import fetch_events
        from types import SimpleNamespace
        raw='<p>Eastern Time</p><table class="release-list"><tr><td class="date-cell">Friday, November 6, 2026</td><td class="time-cell">08:30 AM</td><td class="desc-cell"><strong>Employment Situation</strong></td></tr></table>'
        def get(url,**kw):
            if '11_sched_list' in url:return SimpleNamespace(text=raw,raise_for_status=lambda:None)
            raise TimeoutError()
        with patch('zincintel.official_events.requests.get',side_effect=get):
            data=fetch_events(datetime(2026,10,16,tzinfo=timezone.utc))
        self.assertEqual(data['sources']['BLS']['status'],'PARTIAL')
        self.assertEqual(data['upcoming'][0]['source_url'],'https://www.bls.gov/schedule/2026/11_sched_list.htm')

    def test_event_seven_days_boundary_and_far_events_collapsed(self):
        from zincintel.official_events import event_panel
        def ev(day):return dict(title='event'+day,date=day,sort_time=day+'T08:00:00+08:00',taipei_display=day,markets='Gold',watch='watch',source_url='https://www.bls.gov',source='BLS',status='SCHEDULED_NOT_RELEASED',time_precision='EXACT')
        markup=event_panel({'market_research':{'events':{'checked_at':'2026-10-16T00:00:00+00:00','upcoming':[ev('2026-10-22'),ev('2026-10-23')]}}})
        split=markup.index('<details>')
        self.assertIn('event2026-10-22',markup[:split]);self.assertNotIn('event2026-10-23',markup[:split])
        self.assertNotIn('<details open',markup)

    def test_evidence_preserves_dates_and_explains_opposite_horizons(self):
        from zincintel.radar_evidence import evidence_rows
        from zincintel.radar import radar_body
        snap={'decision_book':{'markets':{'gold':{'direction':'BEAR'}}},'market_research':{'cross_assets':{'gold':{'status':'AVAILABLE','as_of':'2026-10-15','chart_points':[{'date':'2026-10-14','close':100},{'date':'2026-10-15','close':102}]}}},'market':{'lme_cash':100,'lme_3m':99,'field_sources':{'lme_cash':{'as_of':'2026-10-15'},'lme_3m':{'as_of':'2026-10-14'}}}}
        old=deepcopy(snap);rows=evidence_rows(snap)
        self.assertIn('當日反向',rows[0]['technical'])
        self.assertNotIn('同日Cash−3M',rows[3]['evidence'])
        self.assertEqual(old,snap)
        html=radar_body(snap)
        markers=['daily-three','evidence-matrix','macro-history','event-clock','radar-sources']
        positions=[html.index('id="'+m+'"') if 'id="'+m+'"' in html else html.index("id='"+m+"'") for m in markers]
        self.assertEqual(positions,sorted(positions))
        self.assertIn('BLS',html)

if __name__=='__main__':unittest.main()
