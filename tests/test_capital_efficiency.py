from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import capital_efficiency_engine as ce
import run_complete_daily_research as daily


def candles(count=240, hourly_return=.001, volume=10000):
    rows=[];price=100.0
    for i in range(count):
        close=price*(1+hourly_return);rows.append({"timestamp":f"2026-01-{1+i//24:02d}T{i%24:02d}:00:00Z","open":price,"high":max(price,close)*1.005,"low":min(price,close)*.995,"close":close,"volume":volume});price=close
    return pd.DataFrame(rows)


class CapitalEfficiencyTests(unittest.TestCase):
    def setUp(self): self.cfg=json.loads(ce.CONFIG_PATH.read_text())

    def test_deterministic_market_and_event_calculations(self):
        frame=candles()
        self.assertEqual(ce.market_statistics(frame,168),ce.market_statistics(frame,168))
        self.assertEqual(ce.barrier_events(frame,3,2,168,10),ce.barrier_events(frame,3,2,168,10))

    def test_insufficient_sample(self):
        self.assertEqual(ce.market_statistics(candles(20),168)["history_status"],"INSUFFICIENT_SAMPLE")
        event=ce.barrier_events(candles(20,0),3,2,12,10)
        self.assertEqual(event["status"],"INSUFFICIENT_SAMPLE");self.assertIsNone(event["probability_pct"])

    def test_liquidity_penalty_and_notional_scaling(self):
        good=ce.liquidity_metrics(10_000_000,.05,self.cfg["liquidity"]);poor=ce.liquidity_metrics(100_000,.05,self.cfg["liquidity"])
        self.assertEqual(good["liquidity_status"],"GOOD");self.assertEqual(poor["liquidity_status"],"UNSUITABLE")
        self.assertGreater(good["estimated_slippage_10k"],good["estimated_slippage_5k"])
        stats={"median_range_24h":10};event={"probability_pct":90,"median_time_hours":12}
        _,score=ce.score_asset(stats,event,event,poor,3,100,self.cfg);self.assertLessEqual(score,35)

    def test_actual_position_liquidity_scales_and_drives_held_score(self):
        standard=ce.liquidity_metrics(1_000_000,.05,self.cfg['liquidity']);actual=ce.liquidity_metrics(1_000_000,.05,self.cfg['liquidity'],40_000)
        self.assertGreater(actual['estimated_slippage_position_size'],actual['estimated_slippage_10k']);self.assertAlmostEqual(actual['estimated_execution_cost_position_size'],actual['estimated_slippage_position_size']+.2);self.assertIn(actual['liquidity_status_position_size'],{'GOOD','ACCEPTABLE','POOR','UNSUITABLE'});self.assertIsNotNone(actual['POSITION_LIQUIDITY_SCORE'])
        stats={'median_range_24h':5};event={'probability_pct':50,'median_time_hours':24};_,standard_score=ce.score_asset(stats,event,event,standard,1,50,self.cfg);_,actual_score=ce.score_asset(stats,event,event,actual,1,50,self.cfg);self.assertLessEqual(actual_score,standard_score)

    def test_manual_disagreement_warning_requires_explicit_note(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);self.assertEqual(ce.manual_execution_disagreement_warning(root),[]);path=root/'PORTFOLIO_MEMORY/manual_execution_notes.json';path.parent.mkdir();path.write_text(json.dumps({'notes':[{'model_disagreement':True}]}));self.assertEqual(ce.manual_execution_disagreement_warning(root),['MODEL_EXECUTION_DISAGREES_WITH_OBSERVED_EXPERIENCE'])

    def test_missing_portfolio_and_modules(self):
        with patch.object(ce,"load_current_portfolio",return_value={}),patch.object(ce,"PORTFOLIO",Path("/missing.csv")): rows,warnings=ce.portfolio_rows({})
        self.assertEqual(rows,[]);self.assertIn("PORTFOLIO_CONTEXT_UNAVAILABLE",warnings)
        with patch.object(ce,"MODULE_FILES",{"MISSING":Path("/missing.json")}): active,quality,warnings=ce.module_context()
        self.assertEqual(active,{});self.assertEqual(quality,{});self.assertIn("MISSING_UNAVAILABLE",warnings)

    def test_snapshot_duplicate_safety(self):
        with tempfile.TemporaryDirectory() as temp:
            out=Path(temp);payload={"status":"AVAILABLE","purpose":"RESEARCH_ONLY","generated_at_utc":"2026-01-01T00:00:00+00:00","config_version":"1","market_regime":"BEAR","assets":[],"portfolio_capital_efficiency":[],"best_capital_efficiency_candidates":[],"FAST_RANGE_CANDIDATES":[],"warnings":[],"controls":[]}
            with patch.object(ce,"OUT",out),patch.object(ce,"SNAPSHOTS",out/"SNAPSHOTS"),patch.object(ce,"LATEST_JSON",out/"latest.json"),patch.object(ce,"LATEST_MD",out/"latest.md"),patch.object(ce,"build",return_value=payload):
                ce.run("2026-01-01T00:00:00Z");first=list((out/"SNAPSHOTS").glob("*.json"));ce.run("2026-01-01T00:00:00Z");second=list((out/"SNAPSHOTS").glob("*.json"))
            self.assertEqual(first,second);self.assertEqual(len(second),1)

    def test_no_private_endpoints_or_order_actions(self):
        text=Path(ce.__file__).read_text().lower()
        self.assertNotIn("/private/",text);self.assertNotIn("addorder",text);self.assertNotIn("place_order",text)

    @patch.object(daily, "run_tactical_outcome_tracker", return_value=(None, {}))
    @patch.object(daily, "generate_decision_brief", return_value=(None, {}))
    @patch.object(daily,"generate_chief",side_effect=[("x","chief"),("x","chief")])
    @patch.object(daily,"generate_observations",return_value=("x","observations"))
    @patch.object(daily,"generate",return_value=({"run_status":{"x":"OK"}},"latest","full"))
    @patch.object(daily,"run_modular",return_value={"errors":{},"succeeded":1,"total":1})
    @patch.object(daily,"call")
    def test_pipeline_failure_is_fail_soft(self,call,*_):
        call.side_effect=lambda args:(False,"boom") if "scripts/capital_efficiency_engine.py" in args else (True,"ok")
        result=daily.run(reuse=True)
        self.assertTrue(result["success"]);self.assertTrue(any(x.startswith("CAPITAL_EFFICIENCY_UNAVAILABLE") for x in result["warnings"]))


if __name__=="__main__":unittest.main()
