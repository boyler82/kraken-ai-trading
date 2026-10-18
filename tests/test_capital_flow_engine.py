import sys,unittest
from pathlib import Path
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from capital_flow_engine import infer
class FlowTests(unittest.TestCase):
 def test_inference_and_no_clear(self):
  f=pd.DataFrame([{'asset':'BTC','freshness':'FRESH','market_cap_rank':1,'return_24h':1,'btc_relative_return_24h':0,'momentum_stage':'NO_MOMENTUM'},{'asset':'A','freshness':'FRESH','market_cap_rank':10,'return_24h':.5,'btc_relative_return_24h':-.5,'momentum_stage':'NO_MOMENTUM'}]);r=infer(f,{},'2026-01-01T00:00Z');self.assertIn(r['summary']['primary_state'],{'DEFENSIVE_TO_BTC','NO_CLEAR_FLOW'});self.assertIn('inferred',r['summary']['inference_disclaimer'].lower())
