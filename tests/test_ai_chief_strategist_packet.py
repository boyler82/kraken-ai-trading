from __future__ import annotations
import hashlib,json,sys,unittest
import pytest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import ai_chief_strategist_packet as chief

@pytest.mark.archive
class ChiefStrategistPacketTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.packet=chief.build('btc','BTC','2026-08-03T23:00:00Z',None)
 def test_canonical_schema_and_limits(self):
  required={'packet_version','research_mode','generated_at_utc','report_date','objective','run_status','market_state','decision_board','candidates','tactical_opportunities','btc_rotation','sector_leadership','capital_flow','relative_strength','opportunity_changes','cross_module_confirmations','cross_module_conflicts','consistency_warnings','risks','unknowns','analyst_tasks','data_quality','source_trace','packet_compression'};self.assertTrue(required.issubset(self.packet));self.assertLessEqual(len(self.packet['candidates']),12);self.assertEqual(len({r['asset'] for r in self.packet['candidates']}),len(self.packet['candidates']));self.assertLess(len(json.dumps(self.packet).encode()),1_000_000)
 def test_canonical_portfolio_without_invented_tao(self):
  self.assertEqual(self.packet['research_mode'],'MARKET_ONLY');self.assertNotIn('portfolio',self.packet);self.assertNotIn('portfolio_state',self.packet);self.assertNotIn('current_holding',self.packet);self.assertTrue(all('currently_held' not in x and 'portfolio_weight_pct' not in x for x in self.packet['candidates']))
  optional=chief.build('btc','BTC','2026-08-03T23:00:00Z',None,True);self.assertEqual(optional['research_mode'],'PORTFOLIO');self.assertIn('portfolio',optional);self.assertIn('portfolio_state',optional)
 def test_candidate_evidence_sections_and_calculations(self):
  r=self.packet['candidates'][0]
  for key in ('identity','current_data','decision_metrics','consolidation','momentum','relative_strength','rotation','sector_capital_flow','validation','evidence','source_refs'):self.assertIn(key,r)
  c=r['consolidation'];
  if c['downside_to_invalidation_pct'] and c['net_upside_to_high_pct'] is not None:self.assertAlmostEqual(c['rr_to_high'],c['net_upside_to_high_pct']/c['downside_to_invalidation_pct'])
  self.assertIn('return_24h_pct',r['momentum']);self.assertIn('return_vs_btc_24h_pct',r['relative_strength']);self.assertIn('score_advantage',r['rotation']);self.assertIn('sector_rank',r['sector_capital_flow']);self.assertIn('historical_sample_size',r['validation'])
  d=r['current_data'];self.assertEqual(d['analysis_price'],d['current_price']);self.assertEqual(d['analysis_price_timestamp'],d['source_timestamp']);self.assertEqual(d['current_price_semantics'],'DEPRECATED_ALIAS_OF_ANALYSIS_PRICE');self.assertIsNone(d['live_reference_price']);self.assertEqual(d['live_price_status'],'LIVE_PRICE_UNAVAILABLE')
 def test_board_changes_conflicts_risks_unknowns_tasks(self):
  allowed={'HOLD_BTC_BENCHMARK','MONITOR_ALT','ROTATION_CANDIDATE'};self.assertIn(self.packet['decision_board']['preferred_market_state'],allowed)
  for key in ('new_candidates','removed_candidates','strengthening_candidates','weakening_candidates','newly_invalidated'):self.assertIn(key,self.packet['opportunity_changes'])
  order={'CRITICAL':0,'HIGH':1,'MEDIUM':2,'LOW':3};levels=[order[r['severity']] for r in self.packet['risks']];self.assertEqual(levels,sorted(levels));self.assertLessEqual(len(self.packet['risks']),12);self.assertLessEqual(len(self.packet['cross_module_confirmations']),10);self.assertLessEqual(len(self.packet['cross_module_conflicts']),10);self.assertLessEqual(len(self.packet['analyst_tasks']),8);self.assertTrue(self.packet['unknowns'])
 def test_previous_packet_changes(self):
  old=json.loads(json.dumps(self.packet));old['candidates']=old['candidates'][1:]+[{'asset':'REMOVED','decision_metrics':{'decision_impact_score':50,'current_primary_hypothesis':'OLD'}}];new=chief.build('btc','BTC','2026-08-04T00:00:00Z',old);self.assertTrue(any(x['asset']=='REMOVED' for x in new['opportunity_changes']['removed_candidates']))
 def test_trace_nan_determinism_and_markdown(self):
  refs={x['source_ref'] for x in self.packet['source_trace']};self.assertTrue(refs);self.assertTrue(all(set(r['source_refs']).issubset(refs) for r in self.packet['candidates']));encoded=json.dumps(self.packet,allow_nan=False);self.assertNotIn('NaN',encoded);self.assertNotIn('Infinity',encoded);self.assertEqual(chief.build('btc','BTC','2026-08-03T23:00:00Z',None),self.packet);md=chief.render_markdown(self.packet,Path('/x.json'));self.assertTrue(100<=len(md.splitlines())<=180);self.assertIn('Canonical JSON: /x.json',md)
 def test_decision_score_portfolio_priority(self):
  normal,_=chief.decision_score('A',{},set());held,parts=chief.decision_score('A',{}, {'A'});self.assertEqual(held-normal,25);self.assertEqual(parts['active_portfolio_relevance'],25)
 def test_consistency_validator_flags_all_contradictions(self):
  candidate={'asset':'AAVE','current_data':{'current_price':90},'consolidation':{'range_low':100,'range_validity':True,'range_state':'VALID_RANGE','recovery_condition':None,'downside_to_invalidation_pct':-10,'rr_to_high':-2,'rr_to_midpoint':None},'momentum':{'stage':'BREAKOUT_DEVELOPING','breakout_level':110,'activation_condition':'CLOSE_ABOVE_BREAKOUT_LEVEL','invalidation_condition':'CLOSE_BELOW_BREAKOUT_LEVEL'},'rotation':{'validated_expected_edge':3,'rotation_state':'REVIEW_BTC_TO_ALT','candidate_disposition':'MONITOR_ONLY','rejection_reasons':['UNVALIDATED_EDGE']},'validation':{'historical_sample_size':0}}
  warnings=chief.consistency_warnings([candidate],{});codes={x['code'] for x in warnings};self.assertTrue({'VALID_RANGE_BELOW_LOW_WITHOUT_RECOVERY','NEGATIVE_RISK_DISTANCE','RR_INVALID_DENOMINATOR','PRE_ACTIVATION_BREAKOUT_INVALIDATION','VALIDATED_EDGE_WITHOUT_SAMPLE','PREFERRED_ROTATION_GUARDRAIL_FAILURE'}.issubset(codes));self.assertTrue(all({'asset','module','code','evidence','severity','suggested_interpretation'}.issubset(x) for x in warnings))
 def test_packet_build_is_read_only_and_has_no_orders(self):
  protected=list((ROOT/'journal').glob('*.sqlite'))+[p for p in (ROOT/'STRATEGIES').rglob('*') if p.is_file()];before={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in protected};chief.build('btc','BTC','2026-08-03T23:00:00Z',None);self.assertEqual(before,{p:hashlib.sha256(p.read_bytes()).hexdigest() for p in protected});text=json.dumps(self.packet).lower();self.assertNotIn('order_endpoint',text)

if __name__=='__main__':unittest.main()
