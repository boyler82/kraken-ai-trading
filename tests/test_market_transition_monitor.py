import json, sys, tempfile, unittest
from datetime import timedelta
from pathlib import Path
import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"scripts"))
import market_transition_monitor as m
from print_market_transition_summary import render

def bars(n=220, slope=1.0):
    close=pd.Series([100+i*slope for i in range(n)],dtype=float)
    return pd.DataFrame({"timestamp":pd.date_range("2026-01-01",periods=n,freq="h",tz="UTC"),"open":close-.2,"high":close+.5,"low":close-.5,"close":close,"volume":[10+(i%3) for i in range(n)]})

class MarketTransitionTests(unittest.TestCase):
 def test_breadth_and_sell_pressure_are_deterministic(self):
  f=pd.DataFrame({"current_price":[2,1,3],"ema20":[1,2,2],"ema50":[1,1,4]})
  b,d=m.breadth_metrics(f,{"breadth":{"above_ema20_pct":50,"above_ema50_pct":50}})
  self.assertAlmostEqual(b["above_ema20_pct"],66.6667,places=3); self.assertEqual(d["classification"],"STABLE")
  self.assertIn(m.sell_pressure(bars(),12)["classification"],{"DECLINING","NORMAL","INCREASING"})
 def test_fixed_classification_and_no_commands(self):
  s={"btc_structure_1h":{"trend":"HH_HL"},"btc_structure_4h":{"trend":"HH_HL"},"breadth_delta":{"classification":"IMPROVING"},
     "sell_pressure":{"4h":{"classification":"DECLINING"},"12h":{"classification":"NORMAL"}},"breakout_retention_pct":80,
     "median_pullback_depth_pct":10,"rs_leaders_retained_pct":80,"data_quality":{"status":"GOOD"}}
  state,c,k,n,_=m.classify(s); self.assertEqual(state,"CONTINUATION_READY"); self.assertEqual((c,k,n),(5,0,1))
  self.assertNotIn("BUY", state); self.assertNotIn("SELL", state)
 def test_snapshot_contract_and_summary(self):
  f=pd.DataFrame([{"asset":"BTC","current_price":200,"ema20":190,"ema50":180,"btc_relative_return_4h":0,"btc_relative_return_24h":0},
                  {"asset":"ALT","current_price":120,"ema20":110,"ema50":100,"btc_relative_return_4h":2,"btc_relative_return_12h":3,"btc_relative_return_24h":4}])
  s=m.build_snapshot(f,{"BTC":bars(),"ALT":bars()},"2026-01-10T04:00Z")
  required={"timestamp","market_state","btc_structure_1h","btc_structure_4h","breadth","breadth_delta","sell_pressure","breakout_retention_pct","median_pullback_depth_pct","rs_leaders","rs_leaders_retained_pct","continuation_evidence","correction_evidence","neutral_evidence","data_quality","warnings"}
  self.assertTrue(required <= s.keys()); self.assertIn(s["market_state"],m.STATES); self.assertIn("MARKET TRANSITION MONITOR",render(s))
 def test_prediction_files_are_never_overwritten(self):
  old=m.PREDICTIONS; oldmem=m.MEMORY
  with tempfile.TemporaryDirectory() as td:
   m.MEMORY=Path(td); m.PREDICTIONS=Path(td)/"predictions"
   try:
    s={"timestamp":"2026-01-01T00:00:00Z","market_state":"INDETERMINATE"}
    a=m.persist_prediction(s); b=m.persist_prediction(s)
    self.assertNotEqual(a,b); self.assertEqual(len(list(m.PREDICTIONS.glob("*.json"))),2)
   finally: m.PREDICTIONS=old; m.MEMORY=oldmem
 def test_identical_market_data_cannot_create_two_predictions(self):
  oldp,oldmem=m.PREDICTIONS,m.MEMORY
  with tempfile.TemporaryDirectory() as td:
   m.MEMORY=Path(td);m.PREDICTIONS=Path(td)/"predictions"
   try:
    s={"timestamp":"2026-01-01T00:00:00Z","market_state":"INDETERMINATE","market_data_hash":"same"}
    m.persist_prediction(s)
    with self.assertRaises(m.DuplicateMarketDataError):m.persist_prediction({**s,"timestamp":"2026-01-01T01:00:00Z"})
    self.assertEqual(len(list(m.PREDICTIONS.glob("*.json"))),1)
   finally:m.PREDICTIONS,m.MEMORY=oldp,oldmem
 def test_duplicate_hash_is_found_across_all_prediction_history(self):
  old=m.PREDICTIONS
  with tempfile.TemporaryDirectory() as td:
   m.PREDICTIONS=Path(td); (m.PREDICTIONS/'older.json').write_text(json.dumps({'market_data_hash':'same'}))
   (m.PREDICTIONS/'newer.json').write_text(json.dumps({'market_data_hash':'different'}))
   try:self.assertTrue(m.prediction_hash_exists('same'));self.assertFalse(m.prediction_hash_exists('missing'))
   finally:m.PREDICTIONS=old
 def test_run_skips_same_data_and_accepts_advanced_data(self):
  old=(m.PREDICTIONS,m.MEMORY,m.OPERATIONS,m.load_market_inputs,m.evaluate_due_predictions)
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);m.MEMORY=root;m.PREDICTIONS=root/'predictions';m.OPERATIONS=root/'events'
   frame=bars();frame['timestamp']=pd.date_range('2026-01-09T00:00Z',periods=len(frame),freq='h')
   features=pd.DataFrame([{"asset":"BTC","pair":"XBTUSD","current_price":1,"ema20":1,"ema50":1}])
   m.load_market_inputs=lambda as_of:(features,{"BTC":frame},[]);m.evaluate_due_predictions=lambda *args:0
   try:
    _,first,_=m.run('2026-01-18T04:30Z');self.assertIsNotNone(first)
    second,path,_=m.run('2026-01-18T05:00Z');self.assertEqual(second['status'],'NO_NEW_MARKET_DATA');self.assertIsNone(path)
    advanced=pd.concat([frame,pd.DataFrame([{**frame.iloc[-1].to_dict(),"timestamp":pd.Timestamp('2026-01-18T04:00Z'),"close":999}])],ignore_index=True)
    m.load_market_inputs=lambda as_of:(features,{"BTC":advanced},[])
    third,path,_=m.run('2026-01-18T05:30Z');self.assertIsNotNone(path);self.assertNotIn('status',third)
   finally:m.PREDICTIONS,m.MEMORY,m.OPERATIONS,m.load_market_inputs,m.evaluate_due_predictions=old
 def test_run_does_not_infer_misses_from_prediction_history(self):
  old=(m.PREDICTIONS,m.MEMORY,m.MISSED,m.load_market_inputs,m.evaluate_due_predictions)
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);m.MEMORY=root;m.PREDICTIONS=root/'predictions';m.MISSED=root/'legacy_misses';m.PREDICTIONS.mkdir()
   (m.PREDICTIONS/'old.json').write_text(json.dumps({'timestamp':'2026-01-01T00:00:00Z','market_data_timestamp':'2026-01-01T00:00:00Z','market_data_hash':'old'}))
   frame=bars();frame['timestamp']=pd.date_range('2026-01-01T00:00Z',periods=len(frame),freq='h')
   features=pd.DataFrame([{'asset':'BTC','pair':'XBTUSD','current_price':1,'ema20':1,'ema50':1}])
   m.load_market_inputs=lambda as_of:(features,{'BTC':frame},[]);m.evaluate_due_predictions=lambda *args:0
   try:
    m.run('2026-01-10T04:00Z')
    self.assertFalse(m.MISSED.exists())
   finally:m.PREDICTIONS,m.MEMORY,m.MISSED,m.load_market_inputs,m.evaluate_due_predictions=old
 def test_stale_run_does_not_create_prediction(self):
  old=(m.PREDICTIONS,m.MEMORY,m.OPERATIONS,m.load_market_inputs)
  with tempfile.TemporaryDirectory() as td:
   m.MEMORY=Path(td);m.PREDICTIONS=Path(td)/'predictions';m.OPERATIONS=Path(td)/'events'
   m.load_market_inputs=lambda as_of:(pd.DataFrame(),{"BTC":bars()},[])
   try:
    result,path,_=m.run('2026-02-01T00:00Z');self.assertEqual(result['status'],'STALE_MARKET_DATA');self.assertIsNone(path);self.assertFalse(m.PREDICTIONS.exists())
   finally:m.PREDICTIONS,m.MEMORY,m.OPERATIONS,m.load_market_inputs=old
 def test_validation_statistics_cover_every_state_and_horizon(self):
  with tempfile.TemporaryDirectory() as td:
   record={"market_state":"HEALTHY_PULLBACK","horizon_hours":12,"btc_forward_return_pct":2,
           "median_alt_forward_return_pct":1,"maximum_adverse_excursion_pct":-1}
   (Path(td)/"one.json").write_text(json.dumps(record))
   stats=m.validation_statistics(Path(td))
   self.assertEqual(stats["HEALTHY_PULLBACK"]["12h"]["p_positive_btc_return"],1)
   self.assertIsNone(stats["INDETERMINATE"]["24h"]["p_positive_btc_return"])
 def test_stale_and_missing_kraken_data_fail_safely(self):
  f=pd.DataFrame([{"asset":"BTC","pair":"BTCUSD","current_price":1,"ema20":1,"ema50":1,
                   "btc_relative_return_4h":0,"btc_relative_return_12h":0,"btc_relative_return_24h":0}])
  s=m.build_snapshot(f,{"BTC":bars(220)},"2026-02-01T00:00Z")
  self.assertEqual(s["data_quality"]["status"],"INSUFFICIENT"); self.assertIn("STALE_MARKET_DATA",s["warnings"])
  old=m.load_features
  try:
   m.load_features=lambda:pd.DataFrame()
   with self.assertRaisesRegex(RuntimeError,"no snapshot was written"):m.load_market_inputs("2026-01-01")
  finally:m.load_features=old
 def test_forward_evaluation_respects_chronology(self):
  oldp,olde=m.PREDICTIONS,m.EVALUATIONS
  with tempfile.TemporaryDirectory() as td:
   m.PREDICTIONS=Path(td)/"predictions"; m.EVALUATIONS=Path(td)/"evaluations"; m.PREDICTIONS.mkdir()
   start=pd.Timestamp("2026-01-03T00:00Z")
   pred={"timestamp":start.isoformat(),"market_state":"HEALTHY_PULLBACK","breadth":{"above_ema20_pct":50}}
   (m.PREDICTIONS/"prediction.json").write_text(json.dumps(pred))
   try:
    self.assertEqual(m.evaluate_due_predictions({"BTC":bars()},start+timedelta(hours=5)),0)
    self.assertEqual(len(list(m.EVALUATIONS.glob("*.json"))),0)
    self.assertEqual(m.evaluate_due_predictions({"BTC":bars()},start+timedelta(hours=25)),3)
    self.assertEqual(m.evaluate_due_predictions({"BTC":bars()},start+timedelta(hours=26)),0)
   finally:m.PREDICTIONS,m.EVALUATIONS=oldp,olde

if __name__=="__main__": unittest.main()
