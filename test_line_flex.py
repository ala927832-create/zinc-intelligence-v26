import unittest,json,os
from copy import deepcopy
from unittest.mock import patch,Mock
from zincintel.line_flex import build_daily_flex,build_market_rows,valid_change,validate_structure,BASE
from zincintel.line_notify import send_line_daily

class LineFlexTest(unittest.TestCase):
    def test_snapshot_privacy_identity_dates_and_navigation(self):
        from pathlib import Path
        s=json.loads(Path('data/latest_snapshot.json').read_text());old=deepcopy(s)
        s['procurement']={'account_equity':'PRIVATE_CANARY_123'}
        message=build_daily_flex(s);raw=json.dumps(message,ensure_ascii=False)
        self.assertLess(validate_structure(message),30000)
        self.assertNotIn('PRIVATE_CANARY_123',raw)
        for label in ('閱讀完整 Today','每日市場簡報','Markets 圖表','Radar 事件','行情交易日','COMEX連續參考'):
            self.assertIn(label,raw)
        r=next(r for r in build_market_rows(s) if r['key']=='lme_zinc')
        self.assertIsNone(r['change']);self.assertEqual(r['value'],s['market']['lme_cash'])
        self.assertEqual(r['as_of'],s['market']['field_sources']['lme_cash']['as_of'])
        self.assertEqual(s['decision_book'],old['decision_book'])

    def test_single_date_block_no_sources_and_unified_board(self):
        from pathlib import Path
        import re
        from zincintel.line_flex import date_summary
        s=json.loads(Path('data/latest_snapshot.json').read_text())
        m=build_daily_flex(s);raw=json.dumps(m,ensure_ascii=False)
        self.assertEqual(raw.count('行情交易日'),1)
        for forbidden in ('來源：','B_PUBLIC_REFERENCE','CURRENT_FETCH','查看此商品','3M交易日','摘要時間：'):
            self.assertNotIn(forbidden,raw)
        self.assertEqual(raw.count('閱讀完整 Today'),1)
        board=m['contents']['body']['contents'][1]
        self.assertEqual(board['backgroundColor'],'#252C33')
        rows=build_market_rows(s)
        rows[0]['as_of']='2026-10-14'
        dates=date_summary(s,rows)
        self.assertTrue(any('2026-10-14' in x and '黃金' in x for x in dates))

    def test_sparse_and_long_values_fit_and_do_not_infer(self):
        m=build_daily_flex({});validate_structure(m)
        rows=build_market_rows({});self.assertTrue(all(r['value'] is None and r['change'] is None for r in rows))
        self.assertIn('漲跌 N/A',json.dumps(m,ensure_ascii=False))

    def test_no_spot_or_basket_substitution(self):
        s={'market_research':{'cross_assets':{'gold_spot':{'latest_session':{'close':12345}},'usd_basket':{'latest_session':{'close':999}}}}}
        rows=build_market_rows(s)
        self.assertIsNone(rows[0]['value']);self.assertIsNone(rows[3]['value'])

    def test_daily_change_requires_latest_aligned_dates_and_no_long_gap(self):
        series={'status':'AVAILABLE','as_of':'2026-10-15','chart_points':[{'date':'2026-10-14','close':100},{'date':'2026-10-15','close':102}]}
        self.assertEqual(valid_change(series,{'change_1d':2}),2)
        series['as_of']='2026-10-16';self.assertIsNone(valid_change(series,{'change_1d':2}))
        series['as_of']='2026-10-15';series['chart_points'][0]['date']='2026-09-01';self.assertIsNone(valid_change(series,{'change_1d':2}))

    def test_send_validates_before_one_push_and_never_logs_credentials(self):
        response=Mock();response.raise_for_status.return_value=None
        with patch.dict(os.environ,{'LINE_CHANNEL_ACCESS_TOKEN':'secret-canary','LINE_USER_ID':'user-canary'}),patch('zincintel.line_notify.requests.post',return_value=response) as post:
            self.assertTrue(send_line_daily({}))
            self.assertEqual(post.call_count,2)
            self.assertTrue(post.call_args_list[0].args[0].endswith('/validate/push'))
            self.assertNotIn('to',post.call_args_list[0].kwargs['json'])
            self.assertEqual(post.call_args_list[1].kwargs['json']['messages'][0]['type'],'flex')

    def test_failed_validation_never_pushes(self):
        import requests
        response=Mock();response.raise_for_status.side_effect=requests.HTTPError()
        with patch.dict(os.environ,{'LINE_CHANNEL_ACCESS_TOKEN':'token','LINE_USER_ID':'user'}),patch('zincintel.line_notify.requests.post',return_value=response) as post:
            with self.assertRaises(requests.HTTPError):send_line_daily({})
            self.assertEqual(post.call_count,1)

if __name__=='__main__':unittest.main()
