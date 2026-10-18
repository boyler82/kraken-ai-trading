from __future__ import annotations
import hashlib,sys,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/"scripts"))
import morning_brief
import run_daily_rotation_analysis as rotation
from run_daily_rotation_analysis import render_handoff
class RotationRenderingTests(unittest.TestCase):
 def test_market_only_production_reporter(self):
  dashboard={"report_timestamp":"2026-09-05T00:00:00+00:00","objective":"BTC_ACCUMULATION","btc_hold_score":70,"preferred_state":"HOLD_BTC","candidate_count":0,"portfolio_context_status":"INTENTIONALLY_ABSENT_MARKET_ONLY"}
  with patch.object(rotation,'analyze',return_value={'dashboard':dashboard,'candidates':[]}),patch.object(rotation,'write_reports'),patch.object(sys,'argv',['run_daily_rotation_analysis.py','--objective','btc','--reuse-existing-data']),patch('builtins.print') as output:rotation.main()
  self.assertIn('holding N/A (INTENTIONALLY_ABSENT_MARKET_ONLY)',output.call_args.args[0])
 def test_fallback(self):self.assertEqual(morning_brief._rotation_rows({}),[])
 def test_brief_render(self):
  d={"objective":"BTC_ACCUMULATION","current_holding":"BTC","btc_hold_score":70,"market_regime":"MIXED","preferred_state":"HOLD_BTC","top_candidates":[],"rotation_cost_guard":"EDGE_BELOW_COST_GUARD","rotation_cooldown_status":"PASS","data_freshness":"FRESH","confidence":"LOW","main_invalidation_condition":"n/a"};text="\n".join(morning_brief._rotation_rows(d));self.assertIn("HOLD_BTC",text);self.assertIn("USER_DECISION_REQUIRED",text);self.assertNotIn("BUY NOW",text)
 def test_handoff(self):
  h={"report_timestamp":"x","objective":"BTC_ACCUMULATION","current_holding":"BTC","available_capital_reference":None,"btc_hold_score":70,"market_regime":"MIXED","preferred_state":"HOLD_BTC","rotation_cost_guard":"PASS","rotation_cooldown_status":"PASS","confidence":"LOW","main_invalidation_condition":"n/a","top_candidates":[],"unknowns":["sample"],"source_files":["a.csv"]};text=render_handoff(h);self.assertIn("Exact source files",text);self.assertIn("sample",text)
 def test_no_protected_mutation(self):
  protected=list((ROOT/"journal").glob("*.sqlite"))+list((ROOT/"STRATEGIES/btc_4h_donchian_v1").rglob("*.py"));before={x:hashlib.sha256(x.read_bytes()).hexdigest() for x in protected};morning_brief._rotation_rows({});self.assertEqual(before,{x:hashlib.sha256(x.read_bytes()).hexdigest() for x in protected})
if __name__=="__main__":unittest.main()
