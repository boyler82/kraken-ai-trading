import sys,unittest
from pathlib import Path
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from leadership_rotation_engine import map_sectors,analyze
class LeadershipTests(unittest.TestCase):
 def test_mapping_unknown_returns_breadth(self):
  f=pd.DataFrame([{'asset':'A','freshness':'FRESH','return_4h':1,'return_24h':2,'return_48h':3,'return_7d':4,'btc_relative_return_24h':1,'volume_ratio':2,'volatility_expansion':1,'momentum_score':70},{'asset':'X','freshness':'FRESH','return_4h':-1,'return_24h':-2,'return_48h':-3,'return_7d':-4,'btc_relative_return_24h':-1,'volume_ratio':1,'volatility_expansion':1,'momentum_score':20}]);m=pd.DataFrame([{'asset':'A','primary_category':'AI','secondary_category':None,'mapping_source':'TEST','mapping_version':'1','confidence':'HIGH'}]);mapped=map_sectors(f,m);self.assertEqual(mapped[mapped.asset=='X'].iloc[0].primary_category,'Other / Unclassified');r=analyze(f,m,{},'2026-01-01T00:00Z');self.assertEqual(len(r['candidates']),2)
