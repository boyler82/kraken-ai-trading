from __future__ import annotations
import sys,unittest
from pathlib import Path
import numpy as np,pandas as pd
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/"scripts"))
import btc_rotation_engine as e

def frame(count=800,growth=.001,start="2026-01-01"):
 ts=pd.date_range(start,periods=count,freq="1h",tz="UTC");c=100*np.power(1+growth,np.arange(count));return pd.DataFrame({"timestamp":ts,"open":c,"high":c*1.01,"low":c*.99,"close":c,"volume":100})

class RotationEngineTests(unittest.TestCase):
 def test_synthetic_sync_no_fill(self):
  a=frame(5);b=frame(5,growth=.0001);a=a.drop(index=2);r=e.synchronized_relative_series(a,b)
  self.assertEqual(len(r),4);self.assertNotIn(pd.Timestamp("2026-01-01T02:00Z"),set(r.timestamp));self.assertTrue(np.allclose(r.alt_btc,r.alt_usd/r.btc_usd))
 def test_malformed(self):
  with self.assertRaises(ValueError):e.synchronized_relative_series(pd.DataFrame(),pd.DataFrame())
 def test_returns_and_relative_momentum(self):
  f=e.rotation_features(frame(growth=.001),frame(growth=.0002));self.assertGreater(f["relative_return_24h_pct"],0);self.assertGreater(f["alt_btc_ema20_slope_pct"],0);self.assertEqual(f["relative_trend_state"],"POSITIVE")
 def test_btc_score_contributions(self):
  f=e.rotation_features(frame(),frame());s,p,state=e.btc_hold_score(f,[],"BULL",True);self.assertEqual(s,round(sum(p.values()),4));self.assertIn(state,{"BTC_STRONG_HOLD_ENVIRONMENT","BTC_FAVORED","NEUTRAL"})
 def test_alt_score_contributions_and_exclusions(self):
  f=e.rotation_features(frame(.0 if False else 800),frame(growth=.0002));ctx={"momentum_breakout_score":80,"simple_zone":"LOWER_RANGE","range_still_valid":True,"volume_z_score":2,"liquidity_pass":True,"spread_pass":True,"freshness_status":"FRESH","overextension_risk":"LOW"};s,p,q=e.alt_rotation_score(f,ctx);self.assertEqual(s,round(max(0,min(100,sum(p.values())-sum(q.values()))),4))
  for key,value,penalty in (("freshness_status","STALE","stale_data"),("liquidity_pass",False,"low_liquidity"),("overextension_risk","HIGH","overextension")):
   _,_,bad=e.alt_rotation_score(f,{**ctx,key:value});self.assertGreater(bad[penalty],0)
 def test_cost_hysteresis_cooldown_holding_overtrade(self):
  c=e.rotation_controls(9,1.4,12,12,2);self.assertEqual(c["rotation_hysteresis_status"],"NOISE_BAND");self.assertEqual(c["rotation_cost_guard"],"EDGE_BELOW_COST_GUARD");self.assertEqual(c["rotation_cooldown_status"],"COOLDOWN_ACTIVE");self.assertEqual(c["minimum_holding_period_status"],"MINIMUM_HOLD_ACTIVE");self.assertEqual(c["overtrading_risk"],"HIGH")
 def test_states(self):
  passed=e.rotation_controls(20,4);best={"asset":"ADA","critical_risk":False}
  self.assertEqual(e.choose_state("btc","BTC",60,best,passed,"BULL"),"REVIEW_BTC_TO_ALT")
  self.assertEqual(e.choose_state("btc","BTC",70,best,e.rotation_controls(5,1),"BULL"),"HOLD_BTC")
  self.assertEqual(e.choose_state("usd","BTC",30,None,e.rotation_controls(0,0),"BEAR"),"REVIEW_BTC_TO_USD")
  self.assertEqual(e.choose_state("btc","USD",70,None,e.rotation_controls(0,0),"BULL"),"REVIEW_USD_TO_BTC")
  alt={**best,"asset":"BTC","current_holding_context":{"relative_trend_state":"DETERIORATING"}};self.assertEqual(e.choose_state("btc","ADA",50,alt,passed,"MIXED"),"REVIEW_ALT_TO_BTC")
  self.assertEqual(e.choose_state("btc","USD",40,best,e.rotation_controls(0,0),"MIXED"),"NO_ROTATION")
 def test_theoretical_metrics_unknown_probability(self):
  f=e.rotation_features(frame(growth=.001),frame(growth=.0002));x=e.theoretical_edge(f);self.assertIn("relative_risk_reward",x);self.assertEqual(x["probability_band"],"UNKNOWN");self.assertEqual(x["confidence"],"LOW");self.assertEqual(x["historical_sample_size"],0);self.assertIsNone(x["validated_expected_edge"]);self.assertEqual(x["edge_validation_status"],"UNVALIDATED")
 def test_unvalidated_low_advantage_candidates_are_monitor_only(self):
  candidate={**e.theoretical_edge(e.rotation_features(frame(growth=.001),frame(growth=.0002))),"asset":"DOT","score_advantage":5,"momentum_stage":"BREAKOUT_DEVELOPING","overextension_risk":"LOW","controls":e.rotation_controls(5,2)}
  status,reasons=e.rotation_disposition(candidate);self.assertEqual(status,"MONITOR_ONLY");self.assertTrue({"SCORE_ADVANTAGE_TOO_LOW","UNVALIDATED_EDGE","INSUFFICIENT_SAMPLE","LOW_CONFIDENCE","BREAKOUT_NOT_CONFIRMED"}.issubset(reasons))
 def test_deterministic_risk_flags(self):
  f={"relative_return_48h_pct":12,"absolute_return_4h_pct":9};c={"freshness_status":"STALE","liquidity_pass":False,"spread_pass":False,"overextension_risk":"HIGH"};self.assertEqual(e.risk_flags(f,c),sorted(e.risk_flags(f,c)))

if __name__=="__main__":unittest.main()
