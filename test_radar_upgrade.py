import unittest
from datetime import datetime,timezone
from copy import deepcopy
from unittest.mock import patch
from zincintel.official_events import parse_bls,parse_fed,parse_boj,fetch_events
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

if __name__=='__main__':unittest.main()
