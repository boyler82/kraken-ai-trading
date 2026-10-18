from __future__ import annotations
import json
from market_transition_monitor import MEMORY

INTERPRETATIONS = {
 "CONTINUATION_READY":"Evidence is aligned with renewed expansion, without constituting a trading instruction.",
 "HEALTHY_PULLBACK":"The impulse retracement remains supported by structure, participation, or leadership.",
 "CONSOLIDATION":"Signals are balanced or range-like; directional transition is not established.",
 "DEEPER_CORRECTION_RISK":"Multiple market-only measures indicate elevated risk of further deterioration.",
 "INDETERMINATE":"Available evidence or data quality is insufficient for a supported transition state.",
}

def render(s: dict) -> str:
    leaders = s.get("rs_leaders") or []
    leader_lines = [f"{i}. {x['asset']} (4h {x.get('rs_4h_pct')}, 12h {x.get('rs_12h_pct')}, 24h {x.get('rs_24h_pct')})" for i,x in enumerate(leaders,1)] or ["None"]
    warnings = s.get("warnings") or ["None"]
    return "\n".join(["MARKET TRANSITION MONITOR","", "State:",s["market_state"],"", "Evidence:",
      f"Continuation: {s['continuation_evidence']}",f"Correction: {s['correction_evidence']}",f"Neutral: {s['neutral_evidence']}","",
      "BTC structure:",f"1h: {s['btc_structure_1h']}",f"4h: {s['btc_structure_4h']}","", "Breadth:",str(s['breadth']),f"Delta: {s['breadth_delta']}","",
      "Sell pressure:",str(s['sell_pressure']),"", "Breakout retention:",f"{s.get('breakout_retention_pct')}%","", "Median pullback:",f"{s.get('median_pullback_depth_pct')}%","",
      "Relative-strength leaders:",*leader_lines,"", "Interpretation:",INTERPRETATIONS[s['market_state']],"", "Data quality:",str(s['data_quality']),"", "Warnings:",*warnings,
      "", "RESEARCH ONLY — MARKET ONLY — NOT A BUY OR SELL SIGNAL"])

def main() -> None:
    path=MEMORY/"latest.json"
    if not path.exists(): raise SystemExit("No market-transition snapshot found. Run market_transition_monitor.py first.")
    print(render(json.loads(path.read_text())))
if __name__ == "__main__": main()
