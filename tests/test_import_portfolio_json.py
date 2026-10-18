from __future__ import annotations
import json,sqlite3,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import import_portfolio_json as importer
import portfolio_state as state
from lib import research_memory as rm

def snapshot(captured='2026-08-16T21:14:00+02:00',weight=100,value=1000):
 return {'schema_version':'1.0','captured_at':captured,'source':'TEST','base_currency':'USD','snapshot_completeness':'NEAR_COMPLETE','holdings':[{'asset':' btc ','quantity':1,'portfolio_weight_pct':weight,'usd_value':value,'displayed_pnl_usd':None,'displayed_pnl_pct':None}],'visible_total_usd':value,'open_orders_visible':0,'warnings':[]}
class PortfolioJSONImportTests(unittest.TestCase):
 def test_valid_null_import_database_history_current(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);result=importer.import_snapshot(snapshot(),root/'m.sqlite',root/'current.json',root/'history')
   self.assertEqual(result['status'],'IMPORTED');self.assertEqual(json.loads((root/'current.json').read_text())['holdings'][0]['asset'],'BTC');self.assertEqual(len(list((root/'history').glob('*.json'))),1)
   db=sqlite3.connect(root/'m.sqlite');self.assertEqual(db.execute('select count(*) from portfolio_holdings').fetchone()[0],1);db.close()
 def test_duplicate_snapshot_skipped_without_history_duplicate(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);args=(snapshot(),root/'m.sqlite',root/'current.json',root/'history');importer.import_snapshot(*args);second=importer.import_snapshot(*args)
   self.assertEqual(second['status'],'DUPLICATE_PORTFOLIO_SNAPSHOT_SKIPPED');self.assertEqual(len(list((root/'history').glob('*'))),1)
 def test_newest_selected_by_captured_at_not_mtime(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);inp=root/'input';inp.mkdir();(inp/'new_portfolio_snapshot.json').write_text(json.dumps(snapshot('2026-08-17T00:00:00Z',100,2000)));(inp/'old_portfolio_snapshot.json').write_text(json.dumps(snapshot('2026-08-16T00:00:00Z')))
   result=importer.run(inp,db_path=root/'m.sqlite',current_path=root/'current.json',history=root/'history');self.assertIn('new_portfolio_snapshot',result['input_path'])
 def test_weight_rules_and_negative_quantity(self):
  low=snapshot(weight=79);normalized,errors,valid=importer.normalize(low);self.assertTrue(valid);self.assertIn('PORTFOLIO_SNAPSHOT_INCOMPLETE',normalized['warnings'])
  _,errors,valid=importer.normalize(snapshot(weight=101.1));self.assertFalse(valid);self.assertIn('PORTFOLIO_WEIGHT_SUM_INVALID',errors)
  bad=snapshot();bad['holdings'][0]['quantity']=-1;self.assertFalse(importer.normalize(bad)[2])
 def test_older_import_preserves_current_and_history(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);db=root/'m.sqlite';current=root/'current.json';history=root/'history';importer.import_snapshot(snapshot('2026-08-17T00:00:00Z'),db,current,history);result=importer.import_snapshot(snapshot('2026-08-16T00:00:00Z'),db,current,history)
   self.assertFalse(result['promoted_to_current']);self.assertEqual(json.loads(current.read_text())['captured_at'],'2026-08-17T00:00:00Z');self.assertEqual(len(list(history.glob('*'))),2)
 def test_portfolio_state_api_and_concentration(self):
  p=snapshot();p['holdings']=[{'asset':'CSPR','quantity':1,'portfolio_weight_pct':43.2,'usd_value':430},{'asset':'BTC','quantity':1,'portfolio_weight_pct':16.7,'usd_value':167},{'asset':'CC','quantity':1,'portfolio_weight_pct':40.1,'usd_value':401}]
  self.assertTrue(state.is_asset_held('cspr',p));self.assertEqual(state.get_portfolio_weight('BTC',p),16.7);self.assertEqual(state.get_total_visible_usd(p),1000);self.assertAlmostEqual(state.get_portfolio_concentration(p)['top3_weight_pct'],100)
 def test_research_memory_future_only_context(self):
  with tempfile.TemporaryDirectory() as t:
   db=rm.connect(Path(t)/'r.sqlite');candidate={'asset':'ZEC','identity':{},'current_data':{},'decision_metrics':{},'consolidation':{},'momentum':{},'relative_strength':{},'rotation':{},'sector_capital_flow':{},'evidence':{}}
   portfolio={'holdings':[{'asset':'ZEC','quantity':1,'portfolio_weight_pct':9.7}]}
   with patch('portfolio_state.load_current_portfolio',return_value=portfolio):rm.capture_current_snapshots(db,'2026-08-17T00:00:00Z','run',[candidate],{},True)
   row=db.execute('select portfolio_weight_pct_at_snapshot,currently_held_at_snapshot from research_market_snapshots').fetchone();db.close();self.assertEqual(tuple(row),(9.7,1))
if __name__=='__main__':unittest.main()
