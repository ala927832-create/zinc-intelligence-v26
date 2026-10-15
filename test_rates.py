import unittest
from datetime import date
from zincintel.rates import parse_xml, describe
from zincintel.radar import _aligned, radar_body

class RatesTest(unittest.TestCase):
    def test_official_xml_null_negative_future_and_duplicates(self):
        raw='''<feed xmlns:d="d"><properties><d:NEW_DATE>2026-10-12</d:NEW_DATE><d:TC_10YEAR>-0.5</d:TC_10YEAR></properties><properties><d:NEW_DATE>2026-10-13</d:NEW_DATE><d:TC_10YEAR/></properties><properties><d:NEW_DATE>2026-10-15</d:NEW_DATE><d:TC_10YEAR>2</d:TC_10YEAR></properties></feed>'''
        self.assertEqual(parse_xml(raw,'TC_10YEAR',date(2026,10,15)),[{'date':'2026-10-12','value':-0.5}])

    def test_basis_points_and_age(self):
        pts=[{'date':f'2026-10-{d:02}','value':4+i*.01} for i,d in enumerate([5,6,7,8,9,12])]
        x=describe(pts,'us10y','url',date(2026,10,13))
        self.assertEqual(x['change_1d_bp'],1)
        self.assertEqual(x['change_5d_bp'],5)
        self.assertEqual(describe(pts,'us10y','url',date(2026,10,23))['status'],'STALE')

    def test_long_gap_not_daily_change(self):
        pts=[{'date':'2026-09-01','value':4},{'date':'2026-10-12','value':5}]
        self.assertIsNone(describe(pts,'us10y','url',date(2026,10,13))['change_1d_bp'])

    def test_alignment_requires_same_latest_date(self):
        r={'status':'AVAILABLE','as_of':'2026-10-13','history':[{'date':'2026-10-12','value':4},{'date':'2026-10-13','value':4.1}]}
        p={'status':'AVAILABLE','as_of':'2026-10-13','chart_points':[{'date':'2026-10-12','close':100},{'date':'2026-10-13','close':99}]}
        self.assertAlmostEqual(_aligned(r,p)[1],10)
        p['as_of']='2026-10-14'
        self.assertIsNone(_aligned(r,p))

    def test_missing_data_never_claims_no_events(self):
        s=radar_body({})
        self.assertIn('未完成',s.replace('沒有完成','未完成'))
        self.assertIn('日期／資料不足',s)
        self.assertIn('缺日本2Y',s)

    def test_market_context_does_not_mutate_trade_evidence(self):
        from zincintel.research_pages import _market_card
        plan={'evidence':[{'factor':'real yield','status':'NOT_INTEGRATED','value':None}], 'decision_audit':{}}
        snapshot={'market_research':{'rates':{'real10y':{'status':'AVAILABLE','value':2.5,'as_of':'2026-10-14'}}}}
        card=_market_card('gold',plan,{},snapshot)
        self.assertIn('CONTEXT_AVAILABLE_NOT_IN_SIGNAL',card)
        self.assertEqual(plan['evidence'][0]['status'],'NOT_INTEGRATED')

if __name__=='__main__':unittest.main()
