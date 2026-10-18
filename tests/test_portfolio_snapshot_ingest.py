from __future__ import annotations
import json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import portfolio_snapshot_ingest as ingest
import capital_efficiency_engine as ce

def payload(positions=None,total=1000):
 return {'source':'TEST','captured_at_utc':'2026-08-16T00:00:00Z','displayed_total_value_usd':total,'extraction':{'method':'CODEX_VISION'},'positions':positions or [{'asset':'BTC','quantity':.01,'portfolio_weight_pct':100,'market_value_usd':1000,'unrealized_pnl_usd':100,'unrealized_pnl_pct':11.11}]}

class PortfolioSnapshotIngestTests(unittest.TestCase):
 def test_valid_codex_vision_normalizes_cost_and_entry(self):
  result=ingest.validate(payload());self.assertTrue(result['valid']);row=result['positions'][0];self.assertEqual(row['cost_basis_usd'],900);self.assertEqual(row['derived_entry_price_usd'],90000)
 def test_duplicate_rows_rejected(self):
  row=payload()['positions'][0];result=ingest.validate(payload([row,dict(row)],2000));self.assertFalse(result['valid']);self.assertIn('DUPLICATE_ASSET_BTC',result['errors'])
 def test_total_weight_and_pnl_validation(self):
  bad=payload();bad['displayed_total_value_usd']=2000;self.assertIn('VISIBLE_TOTAL_MISMATCH',ingest.validate(bad)['errors']);bad=payload();bad['positions'][0]['unrealized_pnl_pct']=99;self.assertIn('ROW_1_BTC_PNL_PERCENT_MISMATCH',ingest.validate(bad)['errors'])
 def test_large_change_requires_explicit_acceptance(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);source=root/'input.json';current=root/'current.json';source.write_text(json.dumps(payload()));current.write_text(json.dumps({'positions':[{'asset':'BTC','quantity':.005,'market_value_usd':500}]}))
   with patch.object(ingest,'SNAPSHOTS',root/'snapshots'),patch.object(ingest,'REJECTED',root/'rejected'):
    result=ingest.ingest(source,current_path=current)
   self.assertEqual(result['status'],'REVIEW_REQUIRED');self.assertFalse(result['promoted_to_current'])
 def test_invalid_snapshot_never_promoted(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);source=root/'input.json';current=root/'current.json';bad=payload();bad['positions'][0]['quantity']=-1;source.write_text(json.dumps(bad))
   with patch.object(ingest,'SNAPSHOTS',root/'snapshots'),patch.object(ingest,'REJECTED',root/'rejected'):
    result=ingest.ingest(source,current_path=current)
   self.assertEqual(result['status'],'REJECTED');self.assertFalse(current.exists())
 def test_capital_efficiency_reads_current_without_csv_mutation(self):
  with tempfile.TemporaryDirectory() as temp:
   path=Path(temp)/'current.json';path.write_text(json.dumps({'status':'ACCEPTED','positions':[{'asset':'BTC','market_value_usd':1000},{'asset':'USD','market_value_usd':50}]}))
   canonical={'holdings':[{'asset':'BTC','quantity':1,'usd_value':1000,'portfolio_weight_pct':100,'displayed_pnl_usd':None,'displayed_pnl_pct':None}]}
   with patch.object(ce,'load_current_portfolio',return_value=canonical):rows,warnings=ce.portfolio_rows({'BTC':1})
  self.assertEqual([x['asset'] for x in rows],['BTC']);self.assertNotEqual(rows[0]['capital_allocated_usd'],1000);self.assertTrue(not warnings or warnings==['MARK_TO_MARKET_PRICE_STALE:BTC'])
 def test_no_ocr_dependency_or_private_api(self):
  text=Path(ingest.__file__).read_text().lower();self.assertNotIn('tesseract',text);self.assertNotIn('/private/',text);self.assertNotIn('place_order',text)
if __name__=='__main__':unittest.main()
