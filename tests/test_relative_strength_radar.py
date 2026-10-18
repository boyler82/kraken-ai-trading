import sys,unittest
from pathlib import Path
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from relative_strength_radar import analyze,classify,score_row
class RelativeTests(unittest.TestCase):
 def test_rank_breadth_classification(self):
  f=pd.DataFrame([{'asset':'A','pair':'AUSD','source_timestamp':'2026-01-01T00:00Z','freshness':'FRESH','liquidity_pass':True,'sufficient_history':True,'btc_relative_return_4h':2,'btc_relative_return_24h':5,'btc_relative_return_48h':6,'ema20_slope':1,'return_24h':4,'realized_volatility':20},{'asset':'B','pair':'BUSD','source_timestamp':'2026-01-01T00:00Z','freshness':'FRESH','liquidity_pass':True,'sufficient_history':True,'btc_relative_return_4h':-1,'btc_relative_return_24h':-2,'btc_relative_return_48h':-3,'ema20_slope':-1,'return_24h':-2,'realized_volatility':20}]);r=analyze(f,'2026-01-01T01:00Z');self.assertEqual(r['candidates'][0]['asset'],'A');self.assertEqual(r['summary']['relative_strength_breadth_pct'],50)
 def test_overextension_penalty(self):
  _,_,p=score_row({'btc_relative_return_48h':12,'freshness':'FRESH','liquidity_pass':True,'sufficient_history':True});self.assertEqual(p['overextension'],15)
