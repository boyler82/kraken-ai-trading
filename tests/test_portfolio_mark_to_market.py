from __future__ import annotations
import json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import portfolio_state as state
import capital_efficiency_engine as ce

class PortfolioMarkToMarketTests(unittest.TestCase):
 def portfolio(self):
  return {'captured_at':'2026-08-16T00:00:00Z','holdings':[{'asset':'CSPR','quantity':7_819_228.5,'usd_value':24_838.17,'portfolio_weight_pct':80,'displayed_pnl_usd':123,'displayed_pnl_pct':4.2},{'asset':'USD','quantity':5000,'usd_value':5000,'portfolio_weight_pct':20,'displayed_pnl_usd':None,'displayed_pnl_pct':None}],'warnings':[]}
 def test_fresh_public_price_marks_crypto_and_reweights_with_cash(self):
  source=self.portfolio();marked=state.mark_to_market(source,'2026-08-19T10:00:00Z',prices={'CSPR':{'price':.0026441,'timestamp':'2026-08-19T09:00:00Z','age_hours':1}});cspr,usd=marked['holdings']
  self.assertAlmostEqual(cspr['current_market_value_usd'],7_819_228.5*.0026441);self.assertAlmostEqual(cspr['mark_to_market_change_since_snapshot_pct'],(cspr['current_market_value_usd']/24_838.17-1)*100)
  self.assertAlmostEqual(cspr['current_portfolio_weight_pct']+usd['current_portfolio_weight_pct'],100);self.assertEqual(usd['current_market_value_usd'],5000);self.assertEqual(marked['concentration']['cash_weight_pct'],usd['current_portfolio_weight_pct'])
  self.assertEqual(source['holdings'][0]['usd_value'],24_838.17);self.assertNotIn('current_market_value_usd',source['holdings'][0]);self.assertEqual(cspr['snapshot_displayed_pnl_usd'],123);self.assertEqual(cspr['displayed_pnl_usd'],123)
 def test_stale_price_is_guarded_and_snapshot_is_not_used_as_live_value(self):
  marked=state.mark_to_market(self.portfolio(),'2026-08-19T10:00:00Z',prices={'CSPR':{'price':.003,'timestamp':'2026-08-18T00:00:00Z','age_hours':34}});cspr=marked['holdings'][0]
  self.assertIsNone(cspr['mark_price']);self.assertIsNone(cspr['current_market_value_usd']);self.assertEqual(marked['concentration']['top3_weight_pct'],100);self.assertIn('MARK_TO_MARKET_PRICE_STALE:CSPR',marked['warnings'])
 def test_latest_completed_cached_public_close(self):
  with tempfile.TemporaryDirectory() as temp:
   path=Path(temp)/'CSPRUSD_1H.csv';path.write_text('timestamp,close\n2026-08-19T08:00:00Z,0.0025\n2026-08-19T11:00:00Z,9\n')
   marked=state.mark_to_market(self.portfolio(),'2026-08-19T10:00:00Z',Path(temp));self.assertEqual(marked['holdings'][0]['mark_price'],.0025)
 def test_capital_efficiency_uses_marked_position_not_snapshot_value(self):
  marked=state.mark_to_market(self.portfolio(),'2026-08-19T10:00:00Z',prices={'CSPR':{'price':.002,'timestamp':'2026-08-19T09:00:00Z','age_hours':1}})
  with patch.object(ce,'load_current_portfolio',return_value=self.portfolio()),patch.object(ce,'mark_to_market',return_value=marked):rows,warnings=ce.portfolio_rows({},'2026-08-19T10:00:00Z')
  self.assertAlmostEqual(rows[0]['capital_allocated_usd'],7_819_228.5*.002);self.assertEqual(warnings,[])

if __name__=='__main__':unittest.main()
