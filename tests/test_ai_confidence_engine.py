import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from ai_confidence_engine import aggregate
class ConfidenceTests(unittest.TestCase):
 def test_missing_conflict_caps_no_probability(self):
  reg={'relative_strength':{'status':'OK','freshness':'FRESH','top_leaders':[{'asset':'A','relative_strength_score':80}]},'momentum':{'status':'OK','freshness':'STALE','candidates':[{'asset':'A','momentum_breakout_score':20,'freshness':'STALE'}]}};r=aggregate(reg,'2026-01-01T00:00Z');a=r['candidates'][0];self.assertLessEqual(a['evidence_confidence_score'],60);self.assertGreater(a['conflict_count'],0);self.assertFalse(r['summary']['probability_claim'])
