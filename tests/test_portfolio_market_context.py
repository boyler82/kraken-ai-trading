from __future__ import annotations
import sys,tempfile,unittest
import pytest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import asset_pair_resolver as resolver
import portfolio_market_context as context
import ai_chief_strategist_packet as chief
class PortfolioMarketContextTests(unittest.TestCase):
 def test_canonical_pair_normalization(self):
  self.assertEqual(resolver.resolve_kraken_pair('BTC'),'XBTUSD');self.assertEqual(resolver.resolve_kraken_pair('CSPR'),'CSPRUSD');self.assertEqual(resolver.resolve_kraken_pair('ALGO'),'ALGOUSD');self.assertEqual(resolver.resolve_kraken_pair('ENA'),'ENAUSD');self.assertEqual(resolver.resolve_kraken_pair('HBAR'),'HBARUSD')
 def test_fresh_context_overrides_stale_placeholder(self):
  row={'asset':'CSPR','identity':{'kraken_pair':None},'current_data':{'current_price':None,'source_timestamp':'2020-01-01','freshness':'STALE'},'momentum':{},'relative_strength':{},'consolidation':{}}
  market={'contexts':{'CSPR':{'kraken_pair':'CSPRUSD','current_price':.003,'source_timestamp':'2026-08-16T20:00:00Z','freshness':'FRESH','spread':None,'liquidity':1,'momentum':{'change_4h_pct':1,'change_24h_pct':2,'change_48h_pct':3,'acceleration_4h_pct':.5,'volume_z_score':1,'volatility_expansion_ratio':1.2,'momentum_stage':'EARLY_MOMENTUM'},'relative_strength':{'return_vs_btc_24h_pct':2},'consolidation':{}}}}
  chief.enrich_held_candidates([row],market);self.assertEqual(row['current_data']['current_price'],.003);self.assertEqual(row['current_data']['freshness'],'FRESH');self.assertEqual(row['identity']['kraken_pair'],'CSPRUSD')
 def test_missing_context_is_fail_soft_and_counted(self):
  portfolio={'holdings':[{'asset':'CSPR','quantity':1,'portfolio_weight_pct':43.2}]}
  with tempfile.TemporaryDirectory() as t,patch.object(context,'INTRADAY_DIR',Path(t)),patch.object(context,'load_current_portfolio',return_value=portfolio):result=context.build('2026-08-16T21:00:00Z')
  self.assertEqual(result['coverage']['held_asset_count'],1);self.assertEqual(result['coverage']['held_assets_missing_context'],['CSPR']);self.assertIn('HELD_ASSET_MARKET_CONTEXT_MISSING:CSPR',result['warnings'])
 @pytest.mark.archive
 def test_current_packet_has_full_held_coverage(self):
  packet=chief.build('btc','BTC','2026-08-16T21:00:00Z',None,True);state=packet['portfolio_state'];self.assertEqual(state['held_asset_count'],len(packet['portfolio']['open_positions']));self.assertEqual(state['held_assets_with_fresh_market_context'],state['held_asset_count']);self.assertEqual(state['held_assets_missing_context'],[]);self.assertGreater(state['portfolio_weight_with_fresh_market_context_pct'],0)
  cspr=next(x for x in packet['candidates'] if x['asset']=='CSPR');self.assertIsNotNone(cspr['current_data']['current_price']);self.assertIsNotNone(cspr['momentum']['return_24h_pct'])
if __name__=='__main__':unittest.main()
