from __future__ import annotations

import hashlib
import sys
import unittest
from datetime import timedelta
from pathlib import Path

import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))

import daily_momentum_breakout_radar as momentum
import morning_brief
import run_daily_consolidation_scan as daily


def bars(count=520, growth=.0002, volume_spike=False):
    ts=pd.date_range("2026-07-01",periods=count,freq="1h",tz="UTC")
    close=100*np.power(1+growth,np.arange(count)); volume=np.full(count,100.0)
    if volume_spike: volume[-4:]=400
    return pd.DataFrame({"timestamp":ts,"open":close*.999,"high":close*1.001,"low":close*.998,"close":close,"volume":volume,"trades":1})


def candidate(asset="A",net=5,cycle=40,position=20):
    timing={"count":1,"average_hours":cycle/2,"average_bars":cycle/8,"median_bars":1,"median_hours":4,"events":[]}
    return {"asset":asset,"freshness_status":"FRESH","range_still_valid":True,"is_valid_horizontal_consolidation":True,"confirmed_breakouts":0,"confirmed_breakdowns":0,"risk_flags":[],"liquidity_pass":True,"data_quality_status":"OK","range_quality":70,"estimated_net_range_return_pct":net,"lower_boundary_tests":2,"upper_boundary_tests":2,"low_to_high":timing,"high_to_low":timing,"sufficient_native_intraday_history":True,"position_pct":position,"average_full_cycle_hours":cycle,"kraken_24h_quote_volume":1_000_000,"breakout_risk":"LOW","freshness_age_hours":1}


class DailyConsolidationTests(unittest.TestCase):
    def test_top_four_and_stale_replacement(self):
        rows=[candidate(chr(65+i),net=10-i) for i in range(6)]
        rows[0]["freshness_status"]="STALE"
        selected=daily.select_daily(daily.rank_daily(rows),4)
        self.assertEqual(len(selected),4)
        self.assertNotIn("A",[r["asset"] for r in selected])

    def test_ranking_return_then_cycle_and_determinism(self):
        rows=[candidate("B",5,30),candidate("A",6,100),candidate("C",5,20)]
        first=[r["asset"] for r in daily.rank_daily(rows.copy())]
        second=[r["asset"] for r in daily.rank_daily(list(reversed(rows)))]
        self.assertEqual(first,["A","C","B"]); self.assertEqual(first,second)

    def test_no_weekly_persistence_bias(self):
        rows=[candidate("NEW",7),candidate("OLD",3)]
        self.assertEqual(daily.select_daily(daily.rank_daily(rows),1)[0]["asset"],"NEW")


class MomentumTests(unittest.TestCase):
    def test_returns_acceleration_and_btc_relative_strength(self):
        own=bars(growth=.001); btc=bars(growth=.0002)
        row=momentum.calculate_features(own,btc,as_of=own.iloc[-1]["timestamp"]+timedelta(hours=1))
        expected=(float(own.close.iloc[-1])/float(own.close.iloc[-25])-1)*100
        self.assertAlmostEqual(row["change_24h_pct"],expected)
        self.assertIsNotNone(row["change_4h_pct"]); self.assertIsNotNone(row["change_12h_pct"]); self.assertIsNotNone(row["change_48h_pct"])
        self.assertAlmostEqual(row["relative_strength_vs_btc_24h_pct"],row["change_24h_pct"]-((btc.close.iloc[-1]/btc.close.iloc[-25]-1)*100))
        self.assertIsNotNone(row["acceleration_4h_pct"])

    def test_breakout_periods_and_volume_expansion(self):
        work=bars(volume_spike=True); work.loc[work.index[-1],"close"]=work.high.iloc[:-1].max()*1.01; work.loc[work.index[-1],"high"]=work.close.iloc[-1]*1.001
        row=momentum.calculate_features(work,bars(),as_of=work.iloc[-1]["timestamp"]+timedelta(hours=1))
        self.assertTrue(row["close_above_previous_7d_high"]); self.assertTrue(row["close_above_previous_14d_high"]); self.assertTrue(row["close_above_previous_20d_high"])
        self.assertGreater(row["volume_z_score"],1.5); self.assertGreater(row["volume_ratio"],1)

    def test_consolidation_transition(self):
        work=bars(growth=.0005,volume_spike=True); high=float(work.close.iloc[-2]*.999)
        row=momentum.calculate_features(work,bars(),{"range_high":high},work.iloc[-1]["timestamp"]+timedelta(hours=1))
        self.assertEqual(row["consolidation_transition"],"CONSOLIDATION_TO_BREAKOUT_TRANSITION")

    def test_stage_classifications(self):
        base={"freshness_status":"FRESH","failed_breakout":False,"overextension_risk":"LOW","close_above_previous_7d_high":False,"distance_to_7d_high_pct":-1,"volume_ratio":1.2,"relative_strength_vs_btc_24h_pct":2,"relative_strength_vs_btc_4h_pct":1,"acceleration_4h_pct":1,"acceleration_12h_pct":1,"number_completed_closes_above_breakout":0,"volatility_expansion_ratio":1.3}
        self.assertEqual(momentum.classify_stage(base),"BREAKOUT_DEVELOPING")
        early={**base,"distance_to_7d_high_pct":-5}; self.assertEqual(momentum.classify_stage(early),"EARLY_MOMENTUM")
        confirmed={**base,"close_above_previous_7d_high":True,"number_completed_closes_above_breakout":1}; self.assertEqual(momentum.classify_stage(confirmed),"BREAKOUT_CONFIRMED")
        self.assertEqual(momentum.classify_stage({**base,"overextension_risk":"HIGH"}),"EXTENDED_MOVE")
        self.assertEqual(momentum.classify_stage({**base,"failed_breakout":True}),"FAILED_BREAKOUT")

    def test_breakout_activation_and_stage_aware_invalidation(self):
        base={"breakout_level":110.0,"local_swing_low":96.0,"ema20":100.0}
        developing=momentum.decision_conditions({**base,"momentum_stage":"BREAKOUT_DEVELOPING"})
        self.assertEqual(developing["activation_condition"],"CLOSE_ABOVE_BREAKOUT_LEVEL")
        self.assertEqual(developing["invalidation_condition"],"CLOSE_BELOW_LOCAL_SWING_LOW")
        confirmed=momentum.decision_conditions({**base,"momentum_stage":"BREAKOUT_CONFIRMED"})
        self.assertEqual(confirmed["invalidation_condition"],"CLOSE_BELOW_BREAKOUT_LEVEL")
        failed=momentum.decision_conditions({**base,"momentum_stage":"FAILED_BREAKOUT"})
        self.assertEqual(failed["activation_condition"],"CLOSE_ABOVE_BREAKOUT_LEVEL")
        self.assertEqual(failed["invalidation_condition"],"CLOSE_BELOW_LOCAL_SWING_LOW")

    def test_penalty_and_score_contribution_total(self):
        row={"close_above_previous_7d_high":True,"breakout_from_consolidation":True,"volume_ratio":2,"relative_strength_vs_btc_24h_pct":3,"acceleration_4h_pct":2,"ema20_slope_pct":1,"current_price":2,"ema20":1,"volatility_expansion_ratio":1.4,"freshness_status":"FRESH","overextension_risk":"HIGH","failed_breakout":False,"change_1h_pct":1}
        score,parts,penalties=momentum.score_momentum(row)
        self.assertEqual(score,round(max(0,min(100,sum(parts.values())-sum(penalties.values()))),4)); self.assertEqual(penalties["overextension"],20)

    def test_stale_exclusion_and_deterministic_ranking(self):
        base={"change_24h_pct":4,"momentum_breakout_score":50}
        self.assertEqual(momentum.classify_stage({"freshness_status":"STALE"}),"NO_MOMENTUM")
        rows=[{**base,"asset":"B","momentum_stage":"EARLY_MOMENTUM"},{**base,"asset":"A","momentum_stage":"EARLY_MOMENTUM"}]
        self.assertEqual([r["asset"] for r in momentum.rank_rows(rows)], ["A","B"])

    def test_morning_brief_fallback_and_adaptive_price(self):
        self.assertEqual(morning_brief._momentum_rows(pd.DataFrame()),[])
        self.assertEqual(morning_brief._daily_consolidation_rows(pd.DataFrame()),[])
        self.assertEqual(morning_brief._fmt_num(.01765),"0.017650")

    def test_feature_helpers_do_not_mutate_protected_artifacts(self):
        protected=list((ROOT/"journal").glob("*.sqlite"))+list((ROOT/"STRATEGIES"/"btc_4h_donchian_v1").rglob("*.py"))+[ROOT/"DATASETS/BTC_4H_DONCHIAN_V1/BTCUSD_15m_operational.csv"]
        before={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in protected if p.exists()}
        momentum.calculate_features(bars(),bars(),as_of=bars().iloc[-1]["timestamp"]+timedelta(hours=1))
        after={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in protected if p.exists()}
        self.assertEqual(before,after)


if __name__=="__main__": unittest.main()
