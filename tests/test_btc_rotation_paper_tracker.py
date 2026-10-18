from __future__ import annotations
import json,sys,unittest
from pathlib import Path
from tempfile import TemporaryDirectory
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/"scripts"))
import btc_rotation_paper_tracker as p
class PaperTrackerTests(unittest.TestCase):
 def test_isolated_review_record_not_execution(self):
  with TemporaryDirectory() as d:
   root=Path(d);p.PAPER_DIR=root;p.STATE=root/"state.json";p.HISTORY=root/"history.csv";p.DECISIONS=root/"decisions.md"
   record=p.record_paper_review({"candidate":"ADA","preferred_state":"REVIEW_BTC_TO_ALT","estimated_round_trip_cost_pct":.6},"2026-01-01T00:00Z")
   state=json.loads(p.STATE.read_text());self.assertEqual(record["status"],"PAPER_REVIEW_RECORDED_NOT_EXECUTED");self.assertEqual(state["current_paper_holding"],"BTC");self.assertEqual(state["authorization"],"PAPER_NOT_AUTHORIZED")
 def test_controls(self):
  state={"entry_timestamp":"2026-01-01T00:00Z","last_rotation_timestamp":"2026-01-01T12:00Z","rotations":[{"timestamp":"2026-01-01T12:00Z"}]};c=p.controls_from_state(state,"2026-01-02T00:00Z");self.assertEqual(c["hours_held"],24);self.assertEqual(c["hours_since_rotation"],12);self.assertEqual(c["rotations_7d"],1)
if __name__=="__main__":unittest.main()
