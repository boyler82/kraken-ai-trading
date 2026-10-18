import sys,unittest,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import chatgpt_analysis_export as x
class ExportTests(unittest.TestCase):
 def test_dedup_budget_traceability(self):
  reg={'momentum':{'candidates':[{'asset':'A','momentum_breakout_score':80}],'source_file':'m','generated_at_utc':'x','freshness':'FRESH'},'relative_strength':{'top_leaders':[{'asset':'A','relative_strength_score':90}],'source_file':'r','generated_at_utc':'x','freshness':'FRESH'}};rows=x.unified_candidates(reg,'BTC');self.assertEqual(len(rows),1);self.assertEqual(set(rows[0]['evidence']),{'momentum','relative_strength'});self.assertIn('source_file',rows[0]['evidence']['momentum'])
 def test_packet_limits(self):
  p=x.build_packet('btc','BTC','2026-01-01T00:00Z');self.assertLess(len(json.dumps(p).encode()),x.MAX_PACKET_BYTES);self.assertLessEqual(len(p['top_candidates']),12);self.assertIn('packet_compression',p)
