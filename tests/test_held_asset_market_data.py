from __future__ import annotations
import sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import pandas as pd
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import held_asset_market_data as held
import capital_efficiency_engine as ce
class HeldAssetMarketDataTests(unittest.TestCase):
 def test_detects_every_held_crypto_asset(self):
  portfolio={'holdings':[{'asset':'CSPR','quantity':1},{'asset':'BTC','quantity':.1},{'asset':'USD','quantity':2},{'asset':'ZERO','quantity':0}]}
  self.assertEqual(held.held_crypto_assets(portfolio),['BTC','CSPR'])
 def test_missing_cached_data_is_explicit(self):
  with tempfile.TemporaryDirectory() as t,patch.object(held,'INTRADAY_DIR',Path(t)),patch.object(held,'BTC_OPERATIONAL_PATH',Path(t)/'missing'):
   result=held.ensure_asset('CSPR','2026-08-16T00:00:00Z',no_network=True)
  self.assertEqual(result['status'],'HELD_ASSET_DATA_INSUFFICIENT')
 def test_canonical_dataset_names_support_btc_and_cspr(self):
  self.assertEqual(held.canonical_path('BTC').name,'BTCUSD_1H.csv');self.assertEqual(held.canonical_path('CSPR').name,'CSPRUSD_1H.csv')
 def test_full_coverage_requires_all_metrics_and_events(self):
  record={k:1 for k in ('median_abs_move_12h','median_range_12h','median_range_24h','ATR_pct','realized_volatility','pct_periods_range_ge_3','pct_periods_range_ge_5','capital_efficiency_score')};record['liquidity_status']='GOOD';record['plus_3_before_minus_2']={'status':'AVAILABLE'};record['plus_5_before_minus_2']={'status':'AVAILABLE'}
  self.assertTrue(ce.has_full_capital_efficiency_coverage(record));record['ATR_pct']=None;self.assertFalse(ce.has_full_capital_efficiency_coverage(record))
 def test_no_private_endpoint_or_orders(self):
  text=Path(held.__file__).read_text().lower();self.assertIn('/public/ohlc',held.KRAKEN_OHLC_URL.lower());self.assertNotIn('/private/',text);self.assertNotIn('addorder',text)
if __name__=='__main__':unittest.main()
