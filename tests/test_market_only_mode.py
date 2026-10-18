from __future__ import annotations
import json,sqlite3,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import ai_chief_strategist_packet as chief
import capital_efficiency_engine as ce
import chatgpt_analysis_export as export
import run_complete_daily_research as pipeline
from lib import research_memory

class MarketOnlyModeTests(unittest.TestCase):
 def test_config_defaults_market_only(self):
  cfg=json.loads((ROOT/'config/research_mode.json').read_text());self.assertEqual(cfg,{'default_mode':'MARKET_ONLY','use_portfolio_context':False})
 def test_chief_ranking_and_fields_ignore_portfolio(self):
  fake1={'holdings':[{'asset':'BTC','quantity':1,'usd_value':1,'portfolio_weight_pct':100}]};fake2={'holdings':[{'asset':'CSPR','quantity':999,'usd_value':999999,'portfolio_weight_pct':100}]}
  with patch.object(chief,'load_current_portfolio',return_value=fake1):one=chief.build('btc','BTC','2026-08-16T21:00:00Z')
  with patch.object(chief,'load_current_portfolio',return_value=fake2):two=chief.build('btc','CSPR','2026-08-16T21:00:00Z')
  self.assertEqual([x['asset'] for x in one['candidates']],[x['asset'] for x in two['candidates']]);self.assertNotIn('portfolio',one);self.assertNotIn('portfolio_state',one)
 def test_export_ranking_has_no_holding_boost(self):
  a=export.build_packet('btc','BTC','2026-08-16T21:00:00Z');b=export.build_packet('btc','CSPR','2026-08-16T21:00:00Z');self.assertEqual([x['asset'] for x in a['top_candidates']],[x['asset'] for x in b['top_candidates']]);self.assertNotIn('portfolio',a)
 def test_capital_efficiency_default_never_reads_portfolio(self):
  with patch.object(ce,'portfolio_rows',side_effect=AssertionError('portfolio read')):payload=ce.build('2026-08-16T21:00:00Z')
  self.assertEqual(payload['research_mode'],'MARKET_ONLY');self.assertNotIn('portfolio_capital_efficiency',payload);self.assertTrue(all('currently_held' not in x for x in payload['assets']))
 def test_research_memory_default_never_reads_portfolio(self):
  with tempfile.TemporaryDirectory() as t:
   db=research_memory.connect(Path(t)/'memory.sqlite');candidate={'asset':'BTC','identity':{},'current_data':{},'consolidation':{},'momentum':{},'relative_strength':{},'rotation':{},'sector_capital_flow':{},'decision_metrics':{},'evidence':{}}
   with patch('portfolio_state.load_current_portfolio',side_effect=AssertionError('portfolio read')):research_memory.capture_current_snapshots(db,'2026-08-19T00:00:00Z','run',[candidate],{},False)
   row=db.execute('select portfolio_weight_pct_at_snapshot,currently_held_at_snapshot from research_market_snapshots').fetchone();db.close();self.assertEqual(tuple(row),(None,None))
 def test_pipeline_default_does_not_launch_portfolio_tools(self):
  called=[]
  def fake_call(args):called.append(args);return True,''
  with patch.object(pipeline,'run_tactical_outcome_tracker',return_value=(None,{})),patch.object(pipeline,'generate_decision_brief',return_value=(None,{})),patch.object(pipeline,'call',side_effect=fake_call),patch.object(pipeline,'run_modular',return_value={'errors':{},'succeeded':1,'total':1}),patch.object(pipeline,'generate',return_value=({'run_status':{'x':'OK'}},'a','b')),patch.object(pipeline,'generate_chief',return_value=({},'chief')),patch.object(pipeline,'generate_observations',return_value=({},'obs')):result=pipeline.run(reuse=True)
  flat=[' '.join(x) for x in called];self.assertTrue(result['success']);self.assertFalse(any('import_portfolio_json' in x or 'held_asset_market_data' in x or '--use-portfolio' in x for x in flat))

if __name__=='__main__':unittest.main()
