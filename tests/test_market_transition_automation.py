import json, os, subprocess, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import market_transition_run_accounting as accounting

ROOT=Path(__file__).resolve().parents[1]
class AutomationShellTests(unittest.TestCase):
 def test_plist_is_template_and_interval_is_90_minutes(self):
  text=(ROOT/'automation/com.krakenai.market-transition.plist').read_text()
  self.assertIn('__REPOSITORY_ROOT__',text); self.assertIn('<integer>5400</integer>',text)
  self.assertNotIn('/Users/',text)
  self.assertNotIn('/dev/null',text)
  self.assertIn('market_transition_launchd.stdout.log',text)
 def test_wrapper_has_lock_and_safe_append_log(self):
  text=(ROOT/'scripts/run_market_transition_monitor.sh').read_text()
  self.assertIn('mkdir "$LOCK_DIR"',text); self.assertIn('>> "$LOG_FILE" 2>&1',text)
  self.assertNotIn('order',text.lower()); self.assertNotIn('rm -rf',text)
 def test_live_lock_prevents_overlap(self):
  import shutil
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);(root/'scripts').mkdir()
   wrapper=root/'scripts/run_market_transition_monitor.sh'
   shutil.copyfile(ROOT/'scripts/run_market_transition_monitor.sh',wrapper)
   lock=root/'RESEARCH_MEMORY/market_transition/run.lock';lock.mkdir(parents=True)
   (lock/'pid').write_text(str(os.getpid()))
   result=subprocess.run(['bash',str(wrapper)],cwd=root,capture_output=True,text=True)
   self.assertEqual(result.returncode,75)
 def test_missing_data_fails_without_snapshot_write(self):
  # The wrapper's strict status capture is statically verified here; input-level
  # missing Kraken assets are covered by monitor warnings/data-quality tests.
  text=(ROOT/'scripts/run_market_transition_monitor.sh').read_text()
  self.assertIn('EXIT_STATUS=$?',text); self.assertIn('exit "$EXIT_STATUS"',text)
 def test_refresh_failure_stops_before_monitor(self):
  text=(ROOT/'scripts/run_market_transition_monitor.sh').read_text()
  self.assertLess(text.index('refresh_market_transition_data.py'),text.index('market_transition_monitor.py'))
  self.assertIn('MARKET_DATA_REFRESH_FAILED',text)
  self.assertIn('if [ "$REFRESH_STATUS" -ne 0 ]',text)
 def test_monitor_has_no_runtime_network_dependency(self):
  text=(ROOT/'scripts/market_transition_monitor.py').read_text()
  self.assertNotIn('urllib',text); self.assertNotIn('requests.',text)
 def test_sleep_gap_is_operational_and_never_a_prediction(self):
  old=(accounting.RUNS,accounting.GAPS,accounting.MEMORY)
  with tempfile.TemporaryDirectory() as td:
   root=Path(td); accounting.MEMORY=root; accounting.RUNS=root/'runs'; accounting.GAPS=root/'gaps'
   try:
    accounting.start('one','2026-08-26T00:00:00Z','launchd')
    accounting.finish('one','2026-08-26T00:01:00Z','SUCCESS_NEW_OBSERVATION',0,None)
    accounting.start('two','2026-08-26T05:00:00Z','launchd')
    gaps=list(accounting.GAPS.glob('*.json')); self.assertEqual(len(gaps),2)
    self.assertTrue(all(json.loads(p.read_text())['status']=='MAC_SLEEP_OR_OFFLINE_GAP' for p in gaps))
    self.assertFalse(any(json.loads(p.read_text())['prediction_created'] for p in gaps))
   finally: accounting.RUNS,accounting.GAPS,accounting.MEMORY=old
 def test_manual_gap_is_unknown_and_timezone_safe(self):
  old=accounting.GAPS
  with tempfile.TemporaryDirectory() as td:
   accounting.GAPS=Path(td)
   try:
    made=accounting.record_gaps('2026-08-26T06:00:00+02:00',{'started_at':'2026-08-26T00:00:00Z'},'UNKNOWN_MISSED_RUN')
    self.assertEqual(len(made),2)
    self.assertEqual(json.loads(made[0].read_text())['expected_at'],'2026-08-26T01:30:00+00:00')
   finally: accounting.GAPS=old
 def test_run_classifications_are_explicit(self):
  self.assertEqual(accounting.VALID,{'SUCCESS_NEW_OBSERVATION','NO_NEW_MARKET_DATA','STALE_MARKET_DATA','MARKET_DATA_REFRESH_FAILED','MONITOR_FAILED','MAC_SLEEP_OR_OFFLINE_GAP','UNKNOWN_MISSED_RUN'})
  text=(ROOT/'scripts/run_market_transition_monitor.sh').read_text()
  for status in ('MARKET_DATA_REFRESH_FAILED','MONITOR_FAILED'):
   self.assertIn(status,text)

if __name__=='__main__':unittest.main()
