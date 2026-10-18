from __future__ import annotations

import argparse
import json
import math
import random
from collections import Counter
from pathlib import Path
from statistics import median
from typing import Any, Callable

from lib.research_memory import (
    STATS,
    atomic_json,
    breadth_bucket,
    connect,
    metrics,
    range_bucket,
    rs_bucket,
    volume_bucket,
)

BOOTSTRAP_ITERATIONS = 5000
CONFIDENCE_LEVEL = 95
SEED = 42
MIN_BOOTSTRAP_N = 10
WARNINGS = [
    "OOS_NOT_FOR_OPTIMIZATION",
    "MULTIPLE_TESTING_RISK",
    "DATA_SNOOPING_RISK",
    "CORRELATED_VARIANT_SAMPLE",
]
OUT_JSON = STATS / "latest_oos_strategy_validation.json"
OUT_MD = STATS / "latest_oos_strategy_validation.md"


def episode_representatives(rows: list[dict]) -> list[dict]:
    """Deterministically collapse correlated variants to one row per setup episode."""
    reps: dict[str, dict] = {}
    for row in sorted(rows, key=lambda x: (str(x.get("setup_episode_id")), str(x.get("strategy_variant") or ""))):
        reps.setdefault(str(row["setup_episode_id"]), row)
    return list(reps.values())


def percentile(values: list[float], p: float) -> float:
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * p
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def bootstrap_intervals(
    returns: list[float], iterations: int = BOOTSTRAP_ITERATIONS,
    confidence_level: float = CONFIDENCE_LEVEL, seed: int = SEED,
) -> dict[str, Any]:
    if len(returns) < MIN_BOOTSTRAP_N:
        return {
            "bootstrap_status": "BOOTSTRAP_INSUFFICIENT_SAMPLE",
            "ev_ci_lower_pct": None, "ev_ci_upper_pct": None,
            "wr_ci_lower_pct": None, "wr_ci_upper_pct": None,
            "mean_return_ci_lower_pct": None, "mean_return_ci_upper_pct": None,
        }
    rng = random.Random(seed)
    n = len(returns)
    means: list[float] = []
    win_rates: list[float] = []
    for _ in range(iterations):
        sample = [returns[rng.randrange(n)] for _ in range(n)]
        means.append(sum(sample) / n)
        win_rates.append(100 * sum(x > 0 for x in sample) / n)
    alpha = (100 - confidence_level) / 200
    lo, hi = alpha, 1 - alpha
    # In this subsystem EV is the arithmetic expected trade return, so its CI
    # intentionally equals the mean-return CI.
    mean_lo, mean_hi = percentile(means, lo), percentile(means, hi)
    return {
        "bootstrap_status": "AVAILABLE",
        "ev_ci_lower_pct": mean_lo, "ev_ci_upper_pct": mean_hi,
        "wr_ci_lower_pct": percentile(win_rates, lo), "wr_ci_upper_pct": percentile(win_rates, hi),
        "mean_return_ci_lower_pct": mean_lo, "mean_return_ci_upper_pct": mean_hi,
    }


def negative_expectancy_status(n: int, ev: float | None, ci_upper: float | None) -> str:
    if n < 30:
        return "INSUFFICIENT_SAMPLE"
    if ev is None or ev >= 0:
        return "NEGATIVE_POINT_ESTIMATE_ONLY"
    if ci_upper is not None and ci_upper < 0:
        return "HIGHER_CONFIDENCE_NEGATIVE" if n >= 100 else "LIKELY_NEGATIVE"
    return "NEGATIVE_POINT_ESTIMATE_ONLY"


def sample_metrics(rows: list[dict]) -> dict[str, Any]:
    result = metrics(rows)
    reps = episode_representatives(rows)
    returns = [float(x["net_return_pct"]) for x in reps if x.get("net_return_pct") is not None]
    result.update(bootstrap_intervals(returns))
    result["negative_expectancy_status"] = negative_expectancy_status(
        result["unique_episode_count"], result["expected_value_pct"], result["ev_ci_upper_pct"]
    )
    return result


def delta(a: float | None, b: float | None) -> float | None:
    if a is None or b is None or not math.isfinite(float(a)) or not math.isfinite(float(b)):
        return None
    return a - b


def profitable_pf(metric: dict) -> bool:
    return metric.get("profit_factor_status") == "INFINITE_NO_LOSSES" or (
        metric.get("profit_factor") is not None and metric["profit_factor"] > 1
    )


def oos_status(dev: dict, oos: dict) -> str:
    if oos["unique_episode_count"] < 20:
        return "INSUFFICIENT_OOS"
    ev, pf = oos["expected_value_pct"], oos["profit_factor"]
    if ev is not None and ev < 0 and (pf is None or pf < 1):
        return "OOS_NEGATIVE"
    if ev is not None and ev > 0 and profitable_pf(oos):
        return "OOS_POSITIVE_UNVALIDATED"
    ev_change = delta(ev, dev["expected_value_pct"])
    if ev_change is not None and ev_change < -0.25:
        return "OOS_WORSE"
    if ev_change is not None and ev_change > 0.25:
        return "OOS_BETTER"
    return "OOS_SIMILAR"


def degradation(dev: dict, oos: dict) -> dict[str, Any]:
    return {
        "ev_delta_oos_minus_dev": delta(oos["expected_value_pct"], dev["expected_value_pct"]),
        "pf_delta_oos_minus_dev": delta(oos["profit_factor"], dev["profit_factor"]),
        "wr_delta_oos_minus_dev": delta(oos["win_rate"], dev["win_rate"]),
        "median_return_delta": delta(oos["median_return_pct"], dev["median_return_pct"]),
        "max_drawdown_delta": delta(oos["maximum_drawdown_pct"], dev["maximum_drawdown_pct"]),
    }


def rolling_metrics(rows: list[dict], windows: tuple[int, ...] = (20, 50, 100)) -> dict[str, Any]:
    reps = sorted(episode_representatives(rows), key=lambda x: (str(x.get("entry_timestamp") or ""), str(x["setup_episode_id"])))
    output: dict[str, Any] = {}
    for window in windows:
        if len(reps) < window:
            output[str(window)] = {"status": "INSUFFICIENT_SAMPLE", "rolling_ev": None, "rolling_pf": None, "rolling_wr": None, "rolling_max_drawdown": None}
        else:
            m = metrics(reps[-window:])
            output[str(window)] = {"status": "AVAILABLE", "rolling_ev": m["expected_value_pct"], "rolling_pf": m["profit_factor"], "rolling_pf_status": m["profit_factor_status"], "rolling_wr": m["win_rate"], "rolling_max_drawdown": m["maximum_drawdown_pct"]}
    return output


def stability_status(n: int, rolling: dict[str, Any]) -> str:
    if n < 50:
        return "INSUFFICIENT_SAMPLE"
    current = rolling["50"]
    ev, pf = current["rolling_ev"], current["rolling_pf"]
    if ev is not None and ev < 0 and (pf is None or pf < 1):
        return "STABLE_NEGATIVE"
    if ev is not None and ev > 0 and (current.get("rolling_pf_status") == "INFINITE_NO_LOSSES" or (pf is not None and pf > 1)):
        w20 = rolling["20"]["rolling_ev"]
        return "DETERIORATING" if w20 is not None and w20 < ev - 0.25 else "STABLE_POSITIVE_UNVALIDATED"
    w20 = rolling["20"]["rolling_ev"]
    if w20 is not None and ev is not None and w20 < ev - 0.25:
        return "DETERIORATING"
    return "UNSTABLE"


def research_status(dev: dict, oos: dict, overall: dict) -> str:
    n, ev, pf = overall["unique_episode_count"], overall["expected_value_pct"], overall["profit_factor"]
    if n < 30:
        return "INSUFFICIENT"
    if n >= 100 and ev is not None and ev < 0 and overall["ev_ci_upper_pct"] is not None and overall["ev_ci_upper_pct"] < 0:
        return "ANTI_EDGE_CANDIDATE"
    if oos["unique_episode_count"] >= 20 and (oos["expected_value_pct"] or 0) > 0 and profitable_pf(oos):
        return "POTENTIAL_EDGE_UNVALIDATED"
    if (dev["expected_value_pct"] or 0) > 0 and profitable_pf(dev) and oos["unique_episode_count"] < 20:
        return "OOS_RESEARCH_PRIORITY"
    if ev is not None and ev < 0 and (pf is None or pf < 1):
        return "NEGATIVE_CANDIDATE"
    return "CONTINUE_OBSERVATION"


CONDITIONS: tuple[tuple[str, Callable[[Any], Any]], ...] = (
    ("market_regime", lambda x: x),
    ("relative_strength_bucket", rs_bucket),
    ("range_position_bucket", range_bucket),
    ("volume_bucket", volume_bucket),
    ("breadth_bucket", breadth_bucket),
)


def enrich_conditions(row: dict) -> dict:
    row = dict(row)
    row["market_regime"] = row.get("market_regime_at_entry") or row.get("market_regime")
    row["relative_strength_bucket"] = rs_bucket(row.get("relative_strength_percentile_at_entry"))
    row["range_position_bucket"] = range_bucket(row.get("range_position_pct_at_entry"))
    row["volume_bucket"] = volume_bucket(row.get("volume_z_score_at_entry"))
    row["breadth_bucket"] = breadth_bucket(row.get("universe_above_ema20_pct"))
    return row


def conditional_validation(rows: list[dict]) -> list[dict[str, Any]]:
    """Validate only one-factor hypotheses that exist in DEVELOPMENT; never rank OOS."""
    development = [enrich_conditions(x) for x in rows if x["sample_role"] == "DEVELOPMENT"]
    oos = [enrich_conditions(x) for x in rows if x["sample_role"] == "FORWARD_OOS"]
    hypotheses: list[tuple[str, str, str, Any]] = []
    for dimension, _ in CONDITIONS:
        keys = {(x.get("strategy_family"), x.get("strategy_variant"), x.get(dimension)) for x in development if x.get(dimension) is not None}
        hypotheses.extend((family, variant, dimension, value) for family, variant, value in sorted(keys, key=lambda x: tuple(map(str, x))))
    output = []
    for family, variant, dimension, value in hypotheses:
        dev_rows = [x for x in development if x.get("strategy_family") == family and x.get("strategy_variant") == variant and x.get(dimension) == value]
        oos_rows = [x for x in oos if x.get("strategy_family") == family and x.get("strategy_variant") == variant and x.get(dimension) == value]
        dev_m, oos_m = metrics(dev_rows), metrics(oos_rows)
        n, ev, pf = oos_m["unique_episode_count"], oos_m["expected_value_pct"], oos_m["profit_factor"]
        if n == 0:
            status = "NO_OOS_SAMPLE"
        elif n < 20:
            status = "INSUFFICIENT_OOS"
        elif ev is not None and ev > 0 and profitable_pf(oos_m):
            status = "SUPPORTED_OOS_UNVALIDATED"
        elif ev is not None and ev <= 0 and (pf is None or pf <= 1):
            status = "FAILED_OOS"
        else:
            status = "MIXED_OOS"
        output.append({
            "strategy_family": family, "strategy_variant": variant,
            "dimension": dimension, "value": value,
            "development_n": dev_m["unique_episode_count"], "development_ev": dev_m["expected_value_pct"], "development_pf": dev_m["profit_factor"],
            "oos_n": n, "oos_ev": ev, "oos_pf": pf, "oos_confirmation_status": status,
        })
    return output


def analyze(db) -> dict[str, Any]:
    rows = [dict(x) for x in db.execute("""SELECT o.*,s.universe_above_ema20_pct
        FROM research_setup_outcomes o LEFT JOIN research_market_snapshots s USING(snapshot_id)
        WHERE o.exit_timestamp IS NOT NULL AND o.sample_role IN ('DEVELOPMENT','FORWARD_OOS')""")]
    groups: dict[tuple[str, str], list[dict]] = {}
    for row in rows:
        groups.setdefault((row.get("strategy_family"), row.get("strategy_variant")), []).append(row)
    strategies = []
    for (family, variant), items in sorted(groups.items(), key=lambda x: tuple(map(str, x[0]))):
        dev_rows = [x for x in items if x["sample_role"] == "DEVELOPMENT"]
        oos_rows = [x for x in items if x["sample_role"] == "FORWARD_OOS"]
        dev, oos, overall = sample_metrics(dev_rows), sample_metrics(oos_rows), sample_metrics(items)
        rolling = rolling_metrics(items)
        record = {
            "strategy_family": family, "strategy_variant": variant,
            "DEVELOPMENT": dev, "FORWARD_OOS": oos,
            **degradation(dev, oos), "oos_status": oos_status(dev, oos),
            "negative_expectancy_status": overall["negative_expectancy_status"],
            "rolling_performance": rolling,
            "stability_status": stability_status(overall["unique_episode_count"], rolling),
            "strategy_research_status": research_status(dev, oos, overall),
        }
        strategies.append(record)
    regimes = Counter(x[0] for x in db.execute("SELECT market_regime FROM research_market_snapshots WHERE market_regime IS NOT NULL"))
    warnings = list(WARNINGS)
    warning_details: dict[str, str] = {}
    if regimes and len(regimes) == 1:
        warnings.append("REGIME_IMBALANCE")
        only = next(iter(regimes)).upper()
        warning_details["REGIME_IMBALANCE"] = "BEAR_ONLY_SAMPLE" if "BEAR" in only else f"{only}_ONLY_SAMPLE"
    return {
        "status": "OK", "purpose": "RESEARCH_ONLY", "policy": "OOS_VALIDATES_DEVELOPMENT_HYPOTHESES_ONLY",
        "bootstrap": {"iterations": BOOTSTRAP_ITERATIONS, "confidence_level_pct": CONFIDENCE_LEVEL, "seed": SEED},
        "sample": {
            "development_unique_episodes": len({x["setup_episode_id"] for x in rows if x["sample_role"] == "DEVELOPMENT"}),
            "oos_unique_episodes": len({x["setup_episode_id"] for x in rows if x["sample_role"] == "FORWARD_OOS"}),
        },
        "strategies": strategies, "conditional_hypothesis_validation": conditional_validation(rows),
        "warnings": warnings, "warning_details": warning_details,
    }


def fmt(value: Any) -> str:
    if value is None:
        return "N/A"
    if isinstance(value, float):
        return f"{value:.3f}"
    return str(value)


def json_safe(value: Any) -> Any:
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {key: json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_safe(item) for item in value]
    return value


def render_markdown(payload: dict[str, Any]) -> str:
    lines = ["# Forward OOS Validation", "", "Research-only. OOS validates development hypotheses; it is never searched or ranked for optimization.", "", "## Strategy Development vs OOS", ""]
    for row in payload["strategies"]:
        dev, oos = row["DEVELOPMENT"], row["FORWARD_OOS"]
        lines.append(f"- {row['strategy_family']} / {row['strategy_variant']}: DEV N={dev['unique_episode_count']} EV={fmt(dev['expected_value_pct'])}% PF={fmt(dev['profit_factor'])}; OOS N={oos['unique_episode_count']} EV={fmt(oos['expected_value_pct'])}% PF={fmt(oos['profit_factor'])}; {row['oos_status']}")
    lines += ["", "## Statistical Confidence", ""]
    for row in payload["strategies"]:
        oos = row["FORWARD_OOS"]
        lines.append(f"- {row['strategy_variant']}: OOS EV 95% CI=[{fmt(oos['ev_ci_lower_pct'])}, {fmt(oos['ev_ci_upper_pct'])}]; {oos['bootstrap_status']}; {row['negative_expectancy_status']}")
    counts = Counter(x["oos_confirmation_status"] for x in payload["conditional_hypothesis_validation"])
    lines += ["", "## Conditional Hypothesis Validation", "", "- Development-defined one-factor hypotheses only; no OOS discovery or ranking."]
    lines += [f"- {key}: {value}" for key, value in sorted(counts.items())]
    lines += ["", "## Strategy Stability", ""]
    lines += [f"- {x['strategy_variant']}: {x['stability_status']}" for x in payload["strategies"]]
    lines += ["", "## Warnings", ""] + [f"- {x}: {payload['warning_details'].get(x, '')}".rstrip() for x in payload["warnings"]]
    return "\n".join(lines) + "\n"


def run(db_path: str | Path | None = None) -> dict[str, Any]:
    db = connect(Path(db_path)) if db_path else connect()
    try:
        payload = json_safe(analyze(db))
    finally:
        db.close()
    atomic_json(OUT_JSON, payload)
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    temp = OUT_MD.with_suffix(".md.tmp")
    temp.write_text(render_markdown(payload))
    temp.replace(OUT_MD)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db")
    args = parser.parse_args()
    payload = run(args.db)
    print(f"OOS validation: {len(payload['strategies'])} strategies; {payload['sample']['oos_unique_episodes']} OOS episodes")


if __name__ == "__main__":
    main()
