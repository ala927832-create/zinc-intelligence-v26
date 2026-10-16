"""Information boundaries and synchronized lookup windows, without live data."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from bs4 import BeautifulSoup
from zincintel.final_layout import today
from zincintel.research_pages import build_research_pages

class FinalAB(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snapshot=json.loads(Path('data/latest_snapshot.json').read_text())

    def test_today_has_prices_and_no_markets_plan(self):
        original=copy.deepcopy(self.snapshot)
        doc=BeautifulSoup(today(self.snapshot),'html.parser')
        self.assertEqual(len(doc.select('.quote-card')),6)
        self.assertIsNotNone(doc.select_one('#overview'))
        cash=doc.select_one('[data-market="lme_zinc"]')
        self.assertIsNone(cash.select_one('.market-spark'))
        self.assertIn('Cash 1D N/A',cash.get_text(' ',strip=True))
        self.assertIn('LME_3M_CLOSE',str(cash))
        for marker in ('Next trigger','Hard stop','PRIMARY WATCH','RSI14','chart-first'):
            self.assertNotIn(marker,str(doc))
        self.assertEqual(self.snapshot,original)

    def test_all_periods_keep_price_and_rsi_in_one_window(self):
        original=copy.deepcopy(self.snapshot)
        with tempfile.TemporaryDirectory() as t,patch('zincintel.research_pages.PUBLIC_DIR',Path(t)):
            build_research_pages(self.snapshot)
            doc=BeautifulSoup((Path(t)/'market-lme_zinc.html').read_text(),'html.parser')
            panels=doc.select('.chart-window')
            self.assertEqual([p['data-chart-window'] for p in panels],['20','60','120','252','all'])
            for p in panels:
                self.assertIsNotNone(p.select_one('[data-indicator="RSI14"]'))
                slider=p.select_one('.chart-position');points=json.loads(slider['data-points'])
                self.assertEqual(int(slider['max'])+1,len(points))
                self.assertEqual(p.select_one('.chart')['data-chart-mode'],'CLOSE_ONLY')
                self.assertEqual(len(p.select('.ab-cursor')),2)
            self.assertEqual([p['data-chart-window'] for p in panels if not p.has_attr('hidden')],['60'])
            self.assertNotIn('lme_linked_shfe',str(doc))
            self.assertEqual(len(doc.select('.ab-private')),1)
            gold=(Path(t)/'market-gold.html').read_text()
            self.assertNotIn("class='ab-private'",gold)
            self.assertEqual(self.snapshot,original)

if __name__=='__main__':unittest.main()
