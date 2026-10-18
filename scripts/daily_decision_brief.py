from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from weekly_consolidation_common import ROOT, atomic_write, utc_timestamp


OUT = ROOT / "DAILY_REPORTS" / "DECISION_BRIEF"
DEFAULT_PACKET = ROOT / "DAILY_REPORTS" / "CHATGPT_EXPORT" / "latest_ai_chief_strategist_packet.json"


def _value(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, float):
        return f"{value:.8g}"
    return str(value)


def _items(values: list[Any] | None) -> str:
    return ", ".join(str(value) for value in (values or [])) or "none"


def _risk_reward(plan: dict | None) -> str:
    if not plan or (plan.get("risk_reward_tp1") is None and plan.get("risk_reward_tp2") is None):
        return "NOT ESTIMABLE"
    return f"TP1={_value(plan.get('risk_reward_tp1'))}; TP2={_value(plan.get('risk_reward_tp2'))}"


def _target(plan: dict | None) -> str:
    if not plan or (plan.get("target_1") is None and plan.get("target_2") is None):
        return "NOT VALIDATED"
    return f"TP1={_value(plan.get('target_1'))}; TP2={_value(plan.get('target_2'))}"


def _support(plan: dict | None) -> str:
    if not plan:
        return "null"
    level = plan.get("exit_support_level")
    return "family-level historical support only" if level == "FAMILY_LEVEL_ONLY" else _value(level)


def _opportunity_lines(row: dict) -> list[str]:
    plan = row.get("trade_plan")
    live = row.get("live_reference_price") if row.get("live_price_status") == "LIVE_PRICE_AVAILABLE" else row.get("live_price_status", "LIVE_PRICE_UNAVAILABLE")
    lines = [
        f"### {row.get('asset')} — {row.get('recommendation')}",
        f"- Conviction / technical state: {_value(row.get('conviction'))} / {_value(row.get('technical_action'))}",
        f"- Scores: setup {_value(row.get('setup_quality_score'))} | actionability {_value(row.get('actionability_score'))} | daily {_value(row.get('daily_score'))} | weekly {_value(row.get('weekly_score'))}",
        f"- Analysis snapshot price: {_value(row.get('analysis_price', row.get('current_price')))}",
        f"- Analysis timestamp: {_value(row.get('analysis_price_timestamp'))}",
        f"- Kraken live reference (best bid/ask midpoint): {_value(live)}",
        f"- Live timestamp: {_value(row.get('live_reference_timestamp'))}",
        f"- Drift since snapshot: {_value(row.get('price_drift_pct'))}%" if row.get("price_drift_pct") is not None else "- Drift since snapshot: unavailable",
        "- Research conclusions are based on the analysis snapshot. Live reference price does not recompute the research hypothesis.",
    ]
    if not plan:
        lines += ["- Trade plan: null", "- Target: NOT VALIDATED", "- R/R: NOT ESTIMABLE"]
    else:
        lines += [
            f"- Entry / stop: {_value(plan.get('preferred_entry'))} / {_value(plan.get('stop_loss'))}",
            f"- Stop distance: {_value(plan.get('stop_distance_pct'))}% ({_value(plan.get('stop_width_band'))})",
            f"- Exit / holding: {_value(plan.get('exit_method'))} / {_value(plan.get('expected_holding_hours'))}h",
            f"- Exit support: {_support(plan)}",
            f"- Target: {_target(plan)}",
            f"- R/R: {_risk_reward(plan)}",
        ]
    lines += [
        f"- Why recommended: {_items(row.get('why_recommended'))}",
        f"- Why not actionable: {_items(row.get('why_not_actionable'))}",
        f"- Activation: {_items(row.get('activation_requirements'))}",
        f"- Warnings: {_items((plan or {}).get('warnings') or row.get('warnings'))}",
    ]
    if row.get("recommendation") == "SPECULATIVE_REVIEW":
        lines.append("- Interpretation: speculative review only; this is not a buy recommendation.")
    return lines + [""]


def _weekly_line(row: dict) -> str:
    plan = row.get("trade_plan")
    return (
        f"- {row.get('asset')}: {row.get('recommendation')} ({row.get('conviction')}) | "
        f"technical {row.get('technical_action')} | weekly score {_value(row.get('weekly_score'))} | "
        f"entry {_value((plan or {}).get('preferred_entry'))} | stop {_value((plan or {}).get('stop_loss'))} | "
        f"Target: {_target(plan)} | R/R: {_risk_reward(plan)}"
    )


def render(packet: dict) -> str:
    market = packet.get("market_state", {})
    board = packet.get("decision_board", {})
    rotation = packet.get("btc_rotation", {})
    flow = packet.get("capital_flow", {})
    tactical = packet.get("tactical_opportunities", {})
    preferred = board.get("preferred_market_state") or rotation.get("preferred_state")
    regime = market.get("crypto_regime")
    flow_state = flow.get("primary_state") or market.get("inferred_primary_capital_flow")
    interpretation = f"{preferred}: BTC remains the benchmark; review tactical setups selectively under a {regime} regime and {flow_state} capital-flow backdrop."
    lines = [
        "# Daily Decision Brief",
        "",
        f"Generated: {_value(packet.get('generated_at_utc'))}",
        f"Objective: {_value(packet.get('objective'))}",
        "",
        "## 1. MARKET VERDICT",
        "",
        f"- Preferred market state: {_value(preferred)}",
        f"- BTC benchmark score: {_value(rotation.get('btc_hold_score') or market.get('btc_hold_score'))}",
        f"- Regime: {_value(regime)} / {_value(market.get('environment_status'))}",
        f"- Capital flow: {_value(flow_state)} (confidence {_value(flow.get('capital_flow_confidence') or market.get('capital_flow_confidence'))})",
        f"- Interpretation: {interpretation}",
        "",
        "## 2. BEST DAILY OPPORTUNITIES",
        "",
    ]
    daily = sorted(tactical.get("daily", []), key=lambda row: -(row.get("daily_score") or 0))[:3]
    if daily:
        for row in daily:
            lines += _opportunity_lines(row)
    else:
        lines += ["No daily opportunities.", ""]

    lines += ["## 3. HIGH PRIORITY WATCH", ""]
    watch = []
    seen = set()
    for bucket in (tactical.get("weekly", []), tactical.get("daily", [])):
        for row in bucket:
            if row.get("recommendation") == "HIGH_PRIORITY_WATCH" and row.get("asset") not in seen:
                seen.add(row.get("asset"));watch.append(row)
    if watch:
        for row in sorted(watch, key=lambda item: -(item.get("setup_quality_score") or 0)):
            lines += _opportunity_lines(row)
    else:
        lines += ["No high-priority watch candidates.", ""]

    lines += ["## 4. WEEKLY OPPORTUNITIES", ""]
    weekly = sorted(tactical.get("weekly", []), key=lambda row: -(row.get("weekly_score") or 0))[:5]
    if weekly:
        lines += [_weekly_line(row) for row in weekly] + [""]
    else:
        lines += ["No weekly opportunities.", ""]

    lines += ["## 5. AVOID / DO NOT CHASE", ""]
    avoid = tactical.get("avoid", [])
    if avoid:
        for row in avoid:
            lines.append(f"- {row.get('asset')}: AVOID — {_items(row.get('reasons') or row.get('warnings'))}; setup quality {_value(row.get('setup_quality_score'))}.")
    else:
        lines.append("- None.")

    paper = packet.get("paper_strategy_validation", {})
    best = paper.get("best_observed_strategy") or {}
    memory = packet.get("research_memory", {})
    variant = best.get("variant")
    oos = next((row for row in memory.get("oos_summary", []) if row.get("strategy") == variant), {})
    research_warnings = list(memory.get("research_memory_statistical_warnings", []))
    if any("INSUFFICIENT_SAMPLE" in (row.get("warnings") or []) for row in tactical.get("daily", [])):
        research_warnings.append("CURRENT_TACTICAL_SETUPS_HAVE_INSUFFICIENT_SAMPLE")
    lines += [
        "",
        "## 6. RESEARCH CONTEXT",
        "",
        f"- Best strategy family: {_value(best.get('strategy'))} / {_value(variant)}",
        f"- OOS status: {_value(oos.get('oos_status'))}",
        f"- Sample size: {_value(best.get('closed_trades'))}",
        f"- Important warnings: {_items(list(dict.fromkeys(research_warnings)))}",
        "",
        "Research only. User decision required. No order is executed by this report.",
        "",
    ]
    return "\n".join(lines)


def generate(packet_or_path: dict | str | Path, as_of: Any = None) -> tuple[str, Path]:
    packet = packet_or_path if isinstance(packet_or_path, dict) else json.loads(Path(packet_or_path).read_text())
    now = utc_timestamp(as_of or packet.get("generated_at_utc"))
    text = render(packet)
    latest = OUT / "latest_daily_decision_brief.md"
    dated = OUT / f"{now:%Y-%m-%d}_daily_decision_brief.md"
    atomic_write(dated, text)
    atomic_write(latest, text, backup=False)
    return text, latest.resolve()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--packet", default=str(DEFAULT_PACKET))
    parser.add_argument("--as-of")
    args = parser.parse_args()
    _, path = generate(args.packet, args.as_of)
    print(path)


if __name__ == "__main__":
    main()
