from __future__ import annotations
import json,sqlite3,sys,tempfile,unittest
import pytest
from pathlib import Path
from unittest.mock import patch
import pandas as pd
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from lib import research_memory as rm
import find_historical_analogs as analogs
import analyze_coin_personality as personality
from build_ai_research_memory_packet import compact_for_chief

def candidate(asset='ALGO',price=100):
 return {'asset':asset,'identity':{'kraken_pair':asset+'USD','sector':'L1'},'current_data':{'current_price':price,'spread':.1,'liquidity':100000},'decision_metrics':{'evidence_confidence_score':50,'decision_impact_score':60,'opportunity_age_hours':2,'opportunity_age_status':'NEW','current_primary_hypothesis':'RANGE'},'consolidation':{'range_validity':True,'range_state':'VALID_RANGE','position_percent':20,'range_quality':70,'range_low':90,'midpoint':105,'range_high':120,'downside_to_invalidation_pct':10,'net_upside_to_midpoint_pct':5,'net_upside_to_high_pct':20},'momentum':{'stage':'EARLY','acceleration':1,'volume_z_score':.5,'volatility_expansion':1.2,'distance_to_breakout_pct':-2,'extension_risk':'LOW'},'relative_strength':{'percentile_rank':75,'relative_trend':'LEADER','return_vs_btc_24h_pct':1,'return_vs_btc_48h_pct':2,'return_vs_btc_7d_pct':3},'rotation':{'rotation_state':'HOLD','score_advantage':1},'sector_capital_flow':{'capital_flow_alignment':'ALT','sector_rank':2},'evidence':{'supporting_modules':['a'],'opposing_modules':[]}}

class ResearchMemoryTests(unittest.TestCase):
 def setUp(self):
  self.t=tempfile.TemporaryDirectory();self.path=Path(self.t.name)/'m.sqlite';self.db=rm.connect(self.path)
 def tearDown(self):self.db.close();self.t.cleanup()
 def capture(self,ts='2026-08-13T00:00:00+00:00',asset='ALGO',price=100):
  return rm.capture_current_snapshots(self.db,ts,'run', [candidate(asset,price)],{'crypto_regime':'BEAR','btc_hold_score':60,'universe_above_ema20_pct':40,'universe_outperforming_btc_24h_pct':30})
 def test_snapshot_idempotency(self):
  self.assertEqual(self.capture(),1);self.assertEqual(self.capture(),0);self.assertEqual(self.db.execute('select count(*) from research_market_snapshots').fetchone()[0],1)
 def test_bucket_boundaries(self):
  self.assertEqual(rm.rs_bucket(20),'20-40');self.assertEqual(rm.rs_bucket(90),'90-100');self.assertEqual(rm.range_bucket(100),'80-100%');self.assertEqual(rm.range_bucket(101),'outside_range');self.assertEqual(rm.volume_bucket(-1),'-1 to 0');self.assertEqual(rm.breadth_bucket(80),'80-100')
 def test_ev_profit_factor_and_drawdown(self):
  rows=[{'setup_episode_id':str(i),'strategy_variant':'v','net_return_pct':x,'mfe_pct':x+1,'mae_pct':min(x,0),'holding_hours':10} for i,x in enumerate([10,-5,5,-5])];m=rm.metrics(rows);self.assertEqual(m['expected_value_pct'],1.25);self.assertEqual(m['profit_factor'],1.5);self.assertAlmostEqual(m['maximum_drawdown_pct'],-5.2375)
 def test_profit_factor_strict_json_semantics(self):
  def result(values):
   return rm.metrics([{'setup_episode_id':str(i),'strategy_variant':'v','net_return_pct':x,'mfe_pct':None,'mae_pct':None,'holding_hours':None} for i,x in enumerate(values)])
  no_losses=result([1,2,0]);self.assertIsNone(no_losses['profit_factor']);self.assertEqual(no_losses['profit_factor_status'],'INFINITE_NO_LOSSES')
  non_finite=result([1,float('inf'),float('-inf'),float('nan'),-2]);self.assertEqual(non_finite['non_finite_observation_count'],3);self.assertEqual(non_finite['unique_episode_count'],2);self.assertEqual(non_finite['profit_factor'],.5)
  finite=result([4,-2]);self.assertEqual(finite['profit_factor_status'],'FINITE');self.assertEqual(finite['profit_factor'],2)
  json.dumps(no_losses,allow_nan=False);json.dumps(non_finite,allow_nan=False);json.dumps(finite,allow_nan=False)
 def test_variant_correlation_handling(self):
  rows=[{'setup_episode_id':'same','strategy_variant':v,'net_return_pct':x,'mfe_pct':1,'mae_pct':-1,'holding_hours':1} for v,x in [('a',1),('b',99)]];m=rm.metrics(rows);self.assertEqual(m['unique_episode_count'],1);self.assertEqual(m['variant_trade_count'],2);self.assertEqual(m['expected_value_pct'],1)
 def test_sample_quality_labels(self):
  self.assertEqual([rm.sample_quality(x) for x in (9,10,29,30,49,50,99,100)],['INSUFFICIENT','VERY_LOW','VERY_LOW','LOW','LOW','MEDIUM','MEDIUM','HIGHER_CONFIDENCE'])
 def test_no_lookahead_and_forward_availability(self):
  self.capture();frame=pd.DataFrame([{'timestamp':pd.Timestamp('2026-08-13T04:00Z'),'close':104,'high':105,'low':99},{'timestamp':pd.Timestamp('2026-08-13T12:00Z'),'close':112,'high':113,'low':98}])
  with patch.object(rm,'_market_frame',return_value=frame):rm.update_forward_outcomes(self.db,'2026-08-13T05:00:00Z')
  r=self.db.execute('select * from research_forward_outcomes').fetchone();self.assertAlmostEqual(r['return_4h_pct'],4);self.assertIsNone(r['return_12h_pct']);self.assertIsNone(r['mfe_12h_pct'])
 def test_baseline_development_oos_split(self):
  self.db.execute("update research_metadata set value='2026-01-01T00:00:00+00:00' where key='baseline_created_at'");self.db.commit();self.capture();self.assertEqual(self.db.execute('select sample_role from research_market_snapshots').fetchone()[0],'FORWARD_OOS')
 @pytest.mark.archive
 def test_paper_outcome_linking_is_read_only(self):
  import hashlib
  source=ROOT/'PAPER_RESEARCH/paper_strategy_research.sqlite';before=hashlib.sha256(source.read_bytes()).hexdigest();row=sqlite3.connect(source).execute("SELECT t.entry_timestamp,t.asset FROM paper_trades t WHERE t.status='CLOSED' LIMIT 1").fetchone();self.capture(row[0],row[1]);rm.import_paper_outcomes(self.db,source);linked=self.db.execute('select count(*) from research_setup_outcomes where snapshot_id is not null').fetchone()[0];self.assertGreater(linked,0);self.assertEqual(before,hashlib.sha256(source.read_bytes()).hexdigest())
 def test_analog_normalization_and_small_n(self):
  for i in range(4):self.capture(f'2026-08-{10+i:02d}T00:00:00+00:00',f'A{i}',100+i)
  r=analogs.find(self.db,asset='A3',k=20,min_sample=5);self.assertEqual(r['status'],'INSUFFICIENT_ANALOG_SAMPLE');self.assertTrue(all(x>=0 for x in r['distance_score']))
 def test_compact_chief_integration_limit(self):
  packet={'status':'AVAILABLE','market_memory_summary':{'completed_unique_episodes':185,'total_snapshots':12},'current_candidate_memory':[{'asset':str(i),'blob':'x'*5000} for i in range(20)]};c=compact_for_chief(packet);self.assertLessEqual(len(json.dumps(c).encode()),15000)
 def test_fast_range_qualification_requires_five(self):
  root=Path(self.t.name);p=root/'DATASETS/RANGE_PERSONALITY';p.mkdir(parents=True);episode={'asset':'FAST','range_low':1,'range_high':1.04,'calendar_duration_hours':12,'traversals':[{'gross_move_percent':3,'hours':12,'maximum_favorable_movement':3.2,'maximum_adverse_movement':-.5,'false_break_during_traversal':False} for _ in range(5)]};(p/'range_episode_history.json').write_text(json.dumps({'episodes':[episode]}))
  with patch.object(personality,'ROOT',root):rows=personality.fast_range_candidates(self.db)
  self.assertEqual(rows[0]['asset'],'FAST');self.assertEqual(rows[0]['historical_fast_range_episode_count'],5)
 def test_fail_soft_shape(self):
  c=compact_for_chief({});self.assertIn('status',c);self.assertEqual(c['sample']['snapshots'],0)

if __name__=='__main__':unittest.main()
