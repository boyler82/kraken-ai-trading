from __future__ import annotations
import sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from daily_decision_brief import render


class DailyDecisionBriefTests(unittest.TestCase):
    def packet(self):
        opportunity={"asset":"TEST","recommendation":"SPECULATIVE_REVIEW","conviction":"LOW","technical_action":"BUY_ON_BREAKOUT","setup_quality_score":40,"actionability_score":70,"daily_score":60,"weekly_score":30,"current_price":100,"why_recommended":["TECHNICAL_TRIGGER_PRESENT"],"why_not_actionable":["UNVALIDATED_EDGE"],"activation_requirements":["BREAKOUT_CONFIRMATION_REQUIRED"],"warnings":["INSUFFICIENT_SAMPLE"],"trade_plan":{"preferred_entry":105,"stop_loss":95,"stop_distance_pct":9.52,"stop_width_band":"VERY_WIDE","exit_method":"MOMENTUM_STRUCTURE_EXIT","expected_holding_hours":24,"target_1":None,"target_2":None,"risk_reward_tp1":None,"risk_reward_tp2":None,"exit_support_level":"FAMILY_LEVEL_ONLY","warnings":["TARGET_NOT_VALIDATED","RISK_REWARD_NOT_ESTIMABLE"]}}
        return {"generated_at_utc":"2026-08-20T00:00:00Z","objective":"BTC_ACCUMULATION","market_state":{"crypto_regime":"BEAR","environment_status":"DEFENSIVE","btc_hold_score":60,"inferred_primary_capital_flow":"NO_CLEAR_FLOW"},"decision_board":{"preferred_market_state":"HOLD_BTC_BENCHMARK"},"btc_rotation":{"btc_hold_score":60},"capital_flow":{"primary_state":"NO_CLEAR_FLOW","capital_flow_confidence":30},"tactical_opportunities":{"daily":[opportunity],"weekly":[opportunity],"avoid":[{"asset":"BAD","setup_quality_score":1,"reasons":["FAILED_BREAKOUT"]}]},"paper_strategy_validation":{"best_observed_strategy":{"strategy":"MOMENTUM_BREAKOUT","variant":"MOMENTUM_STRUCTURE_EXIT","closed_trades":111}},"research_memory":{"oos_summary":[{"strategy":"MOMENTUM_STRUCTURE_EXIT","oos_status":"OOS_POSITIVE_UNVALIDATED"}],"research_memory_statistical_warnings":["REGIME_IMBALANCE"]}}

    def test_required_sections_and_explicit_null_semantics(self):
        text=render(self.packet())
        for title in ("MARKET VERDICT","BEST DAILY OPPORTUNITIES","HIGH PRIORITY WATCH","WEEKLY OPPORTUNITIES","AVOID / DO NOT CHASE","RESEARCH CONTEXT"):self.assertIn(title,text)
        self.assertIn("Target: NOT VALIDATED",text);self.assertIn("R/R: NOT ESTIMABLE",text)
        self.assertIn("family-level historical support only",text)

    def test_speculative_review_is_not_presented_as_buy(self):
        text=render(self.packet())
        self.assertIn("speculative review only; this is not a buy recommendation",text)

    def test_analysis_and_live_prices_are_explicit(self):
        packet=self.packet();row=packet["tactical_opportunities"]["daily"][0]
        row.update({"analysis_price":100,"analysis_price_timestamp":"2026-08-20T00:00:00Z","live_reference_price":102,"live_reference_timestamp":"2026-08-20T00:00:10Z","live_price_status":"LIVE_PRICE_AVAILABLE","price_drift_pct":2})
        text=render(packet)
        assert "Analysis snapshot price: 100" in text
        assert "Kraken live reference (best bid/ask midpoint): 102" in text
        assert "Drift since snapshot: 2%" in text
        assert "Live reference price does not recompute the research hypothesis." in text

if __name__=='__main__':unittest.main()
