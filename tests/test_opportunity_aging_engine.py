import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from opportunity_aging_engine import update_state
class AgingTests(unittest.TestCase):
 def test_first_seen_strengthening_expiry(self):
  state,rows=update_state([{'opportunity_id':'momentum:A','asset':'A','opportunity_type':'momentum','current_score':50,'current_price':1,'btc_relative_value':1}],'2026-01-01T00:00Z',{});self.assertEqual(rows[0]['classification'],'NEW');state2,rows2=update_state([{'opportunity_id':'momentum:A','asset':'A','opportunity_type':'momentum','current_score':60,'current_price':1,'btc_relative_value':1}],'2026-01-02T01:00Z',state);self.assertEqual(rows2[0]['strengthening_count'],1);_,expired=update_state([],'2026-01-03T00:00Z',state2);self.assertEqual(expired[0]['classification'],'EXPIRED');self.assertIsNone(rows2[0]['useful_life_estimate'])
