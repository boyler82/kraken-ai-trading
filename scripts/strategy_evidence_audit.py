from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any

from lib.research_memory import DB_PATH, ROOT, atomic_json

OUT_DIR = ROOT / "RESEARCH_REPORTS"
OUT_JSON = OUT_DIR / "strategy_evidence_audit_latest.json"
OUT_MD = OUT_DIR / "strategy_evidence_audit_latest.md"
PAPER_DB = ROOT / "PAPER_RESEARCH/paper_strategy_research.sqlite"
SEED = 20260905
BOOTSTRAP_SAMPLES = 4000


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def execution_definition(family: str, config: dict, cost_pct: float) -> dict:
    return {
        "entry_definition": {"signal_family": family, "entry_price": "entry_reference_price"},
        "target": {k: config[k] for k in ("target", "target_pct") if k in config},
        "stop": {"stop_pct": config.get("stop_pct")},
        "expiry_max_hold_hours": config.get("max_hold_hours"),
        "exit_logic": "FIRST_COMPLETED_OBSERVATION_OF_TARGET_OR_STOP; OTHERWISE_TIME_EXIT",
        "cost_assumptions": {"estimated_round_trip_cost_pct": cost_pct},
        "execution_semantics": {"paper_only": True, "real_orders": False},
    }


def definition_hash(definition: dict) -> str:
    return hashlib.sha256(canonical(definition).encode()).hexdigest()


def normalized_timestamp(value: Any) -> str:
    stamp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if stamp.tzinfo is None: stamp = stamp.replace(tzinfo=timezone.utc)
    return stamp.astimezone(timezone.utc).isoformat()


def load_definitions(path: Path = PAPER_DB) -> dict[tuple[str, str], dict]:
    config_path = ROOT / "config/paper_strategy_research_v1.json"
    root_config = json.loads(config_path.read_text())
    cost = float(root_config["estimated_round_trip_cost_pct"])
    definitions = {}
    if path.exists():
        with sqlite3.connect(path) as db:
            for family, variant, encoded in db.execute("SELECT strategy_name,strategy_variant,config_json FROM paper_strategy_variants"):
                economic = execution_definition(str(family), json.loads(encoded), cost)
                definitions[(str(family), str(variant))] = economic
    for family, variants in root_config["variants"].items():
        for variant, config in variants.items():
            definitions.setdefault((family, variant), execution_definition(family, config, cost))
    return definitions


def percentile(values: list[float], probability: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values); position = (len(ordered) - 1) * probability
    lower = int(position); upper = min(lower + 1, len(ordered) - 1); weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def bootstrap_ci(rows: list[dict], clustered: bool, seed: int = SEED, samples: int = BOOTSTRAP_SAMPLES) -> dict:
    finite = [r for r in rows if r.get("net_return_pct") is not None and math.isfinite(float(r["net_return_pct"]))]
    unit = "simultaneous_entry_timestamp_signal_cluster" if clustered else "episode"
    minimum = len({r["cluster_timestamp"] for r in finite}) if clustered else len(finite)
    if minimum < 2:
        return {"status": "INSUFFICIENT_RESAMPLING_UNITS", "resampling_unit": unit, "samples": samples, "seed": seed, "lower_pct": None, "upper_pct": None}
    rng = random.Random(seed); estimates = []
    if clustered:
        groups = defaultdict(list)
        for row in finite: groups[row["cluster_timestamp"]].append(float(row["net_return_pct"]))
        keys = sorted(groups)
        for _ in range(samples):
            draw = [value for _key in range(len(keys)) for value in groups[rng.choice(keys)]]
            estimates.append(sum(draw) / len(draw))
    else:
        values = [float(r["net_return_pct"]) for r in finite]
        for _ in range(samples): estimates.append(sum(rng.choice(values) for _x in values) / len(values))
    return {"status": "AVAILABLE", "resampling_unit": unit, "samples": samples, "seed": seed,
            "lower_pct": percentile(estimates, .025), "upper_pct": percentile(estimates, .975)}


def structure(rows: list[dict]) -> dict:
    clusters = Counter(r["cluster_timestamp"] for r in rows); sizes = list(clusters.values())
    asset_time = {(r["asset"], r["market_data_timestamp"]) for r in rows}
    values = [float(r["net_return_pct"]) for r in rows if r.get("net_return_pct") is not None and math.isfinite(float(r["net_return_pct"]))]
    icc = design = effective = None
    if len(clusters) > 1 and len(values) > len(clusters):
        grouped = defaultdict(list)
        for r in rows:
            if r.get("net_return_pct") is not None and math.isfinite(float(r["net_return_pct"])): grouped[r["cluster_timestamp"]].append(float(r["net_return_pct"]))
        groups = [x for x in grouped.values() if x]; n = sum(map(len, groups)); k = len(groups)
        if k > 1 and n > k:
            grand = sum(map(sum, groups)) / n
            ssb = sum(len(g) * ((sum(g) / len(g)) - grand) ** 2 for g in groups)
            ssw = sum(sum((x - sum(g) / len(g)) ** 2 for x in g) for g in groups)
            msb, msw = ssb / (k - 1), ssw / (n - k)
            n0 = (n - sum(len(g) ** 2 for g in groups) / n) / (k - 1)
            denominator = msb + (n0 - 1) * msw
            icc = max(0.0, (msb - msw) / denominator) if denominator else 0.0
            mean_size = n / k; variance = sum((len(g) - mean_size) ** 2 for g in groups) / (k - 1)
            cv2 = variance / mean_size ** 2 if mean_size else 0
            design = 1 + (((1 + cv2) * mean_size) - 1) * icc
            effective = n / design if design else None
    return {"raw_episode_n": len(rows), "unique_episode_ids": len({r["setup_episode_id"] for r in rows}),
            "unique_assets": len({r["asset"] for r in rows}), "unique_entry_timestamps": len({r["entry_timestamp"] for r in rows}),
            "unique_market_data_timestamps": len({r["market_data_timestamp"] for r in rows}), "unique_signal_observation_clusters":len(clusters), "unique_asset_timestamp_clusters": len(asset_time),
            "median_cluster_size": median(sizes) if sizes else 0, "max_cluster_size": max(sizes, default=0),
            "timestamp_icc": icc, "design_effect": design, "diagnostic_effective_n": effective,
            "effective_n_status": "DIAGNOSTIC_CLUSTER_MODEL_NOT_CANONICAL" if effective is not None else "NOT_ESTIMABLE"}


def metrics(rows: list[dict]) -> dict:
    vals = [float(r["net_return_pct"]) for r in rows if r.get("net_return_pct") is not None and math.isfinite(float(r["net_return_pct"]))]
    wins = [x for x in vals if x > 0]; losses = [x for x in vals if x < 0]
    if wins and not losses: pf, status = None, "INFINITE_NO_LOSSES"
    elif not wins and not losses: pf, status = None, "UNDEFINED"
    else: pf, status = sum(wins) / abs(sum(losses)), "FINITE"
    return {"n": len(vals), "ev_pct": sum(vals) / len(vals) if vals else None, "profit_factor": pf, "profit_factor_status": status}


def grouped_metrics(rows: list[dict], key) -> list[dict]:
    groups = defaultdict(list)
    for r in rows: groups[str(key(r) or "UNAVAILABLE")].append(r)
    return [{"value": value, **metrics(items), **structure(items)} for value, items in sorted(groups.items())]


def concentration(rows: list[dict], overall_ev: float | None) -> dict:
    def sensitivity(field: str) -> dict:
        groups = defaultdict(list)
        for r in rows: groups[r[field]].append(r)
        results = []
        for value in sorted(groups):
            remaining = [r for r in rows if r[field] != value]; ev = metrics(remaining)["ev_pct"]
            results.append({"omitted": value, "remaining_n": len(remaining), "ev_pct": ev, "ev_delta_pct": None if ev is None or overall_ev is None else ev - overall_ev})
        deltas = [abs(x["ev_delta_pct"]) for x in results if x["ev_delta_pct"] is not None]
        worst = max(results, key=lambda x: abs(x["ev_delta_pct"] or 0), default=None)
        return {"max_absolute_ev_delta_pct": max(deltas, default=None), "most_influential": worst, "all": results}
    finite = sorted((float(r["net_return_pct"]) for r in rows if r.get("net_return_pct") is not None and math.isfinite(float(r["net_return_pct"]))), reverse=True)
    positive = sum(x for x in finite if x > 0)
    asset = sensitivity("asset"); timestamp = sensitivity("cluster_timestamp")
    return {"leave_one_asset_out": asset, "leave_one_timestamp_out": timestamp,
            "largest_winner_pct": finite[0] if finite else None,
            "largest_winner_share_of_gross_gains": finite[0] / positive if finite and positive else None,
            "one_asset_concentration": bool(asset["max_absolute_ev_delta_pct"] is not None and abs(asset["max_absolute_ev_delta_pct"]) > max(.25, .25*abs(overall_ev or 0))),
            "one_timestamp_concentration": bool(timestamp["max_absolute_ev_delta_pct"] is not None and abs(timestamp["max_absolute_ev_delta_pct"]) > max(.25, .25*abs(overall_ev or 0)))}


def classification(result: dict) -> tuple[str, list[str]]:
    ev = result["statistics"]["ev_pct"]; ci = result["cluster_aware_ci"]; s = result["sample_structure"]; c = result["concentration"]
    regimes = result["regime_coverage"]["observed"]
    warnings = []
    if s["raw_episode_n"] == 0: warnings.append("NO_REALIZED_OUTCOME_EVIDENCE")
    if result["alias_status"] == "EXECUTION_IDENTICAL_ALIAS": warnings.append("ALIAS_NOT_INDEPENDENT_EVIDENCE")
    if s["diagnostic_effective_n"] is not None and s["diagnostic_effective_n"] < 30: warnings.append("LOW_DIAGNOSTIC_EFFECTIVE_N")
    if len(regimes) < 2: warnings.append("LIMITED_REGIME_COVERAGE")
    if c["one_asset_concentration"]: warnings.append("ONE_ASSET_CONCENTRATION")
    if c["one_timestamp_concentration"]: warnings.append("ONE_TIMESTAMP_CONCENTRATION")
    lower, upper = ci["lower_pct"], ci["upper_pct"]
    if ev is not None and upper is not None and upper < 0 and (s["diagnostic_effective_n"] or 0) >= 30: label = "RETIRE"
    elif ev is not None and upper is not None and upper <= 0 and (s["diagnostic_effective_n"] or 0) >= 10: label = "DEPRIORITIZE"
    elif ev is not None and lower is not None and lower > 0 and (s["diagnostic_effective_n"] or 0) >= 20 and len(regimes) >= 2 and not c["one_asset_concentration"] and not c["one_timestamp_concentration"]: label = "FORWARD_VALIDATE"
    else: label = "RESEARCH"
    return label, warnings


def analyze(db_path: Path = DB_PATH, paper_db: Path = PAPER_DB) -> dict:
    definitions = load_definitions(paper_db)
    with sqlite3.connect(db_path) as db:
        db.row_factory = sqlite3.Row
        rows = [dict(x) for x in db.execute("""SELECT o.*,s.timestamp_utc snapshot_timestamp,COALESCE(s.timestamp_utc,o.entry_timestamp) market_data_timestamp,
            COALESCE(s.market_regime,o.market_regime_at_entry) resolved_regime FROM research_setup_outcomes o
            LEFT JOIN research_market_snapshots s ON s.snapshot_id=o.snapshot_id WHERE o.exit_timestamp IS NOT NULL""")]
    for row in rows:
        row["entry_timestamp"] = normalized_timestamp(row["entry_timestamp"])
        row["market_data_timestamp"] = normalized_timestamp(row["market_data_timestamp"])
        row["cluster_timestamp"] = row["entry_timestamp"]
        if row.get("snapshot_timestamp"): row["snapshot_timestamp"]=normalized_timestamp(row["snapshot_timestamp"])
    # Variants from one asset/entry signal share the linked market observation even
    # when only one sibling retained its snapshot foreign key.
    linked={(r["asset"],r["entry_timestamp"]):r["snapshot_timestamp"] for r in rows if r.get("snapshot_timestamp")}
    for row in rows: row["market_data_timestamp"]=linked.get((row["asset"],row["entry_timestamp"]),row["market_data_timestamp"])
    groups = defaultdict(list)
    for row in rows: groups[(row["strategy_family"], row["strategy_variant"])].append(row)
    for key in groups:
        definitions.setdefault(key, execution_definition(key[0], {"target_pct": groups[key][0].get("target_pct"), "stop_pct": groups[key][0].get("stop_pct"), "max_hold_hours": None}, .6))
    identities = {key: definition_hash(value) for key, value in definitions.items()}; hash_groups = defaultdict(list)
    for key, digest in identities.items(): hash_groups[digest].append(key)
    aliases = {digest: f"ALIAS_{i:03d}" for i, (digest, keys) in enumerate(sorted(hash_groups.items()), 1) if len(keys) > 1}
    strategies = []
    for key in sorted(definitions):
        all_rows = groups.get(key,[]); oos = [x for x in all_rows if x["sample_role"] == "FORWARD_OOS"]
        sample = oos or [x for x in all_rows if x["sample_role"] == "DEVELOPMENT"]
        digest = identities[key]; stat = metrics(sample); sample_structure = structure(sample)
        seed = SEED + int(digest[:8], 16)
        naive, clustered = bootstrap_ci(sample, False, seed), bootstrap_ci(sample, True, seed)
        regimes = sorted({str(x["resolved_regime"]) for x in sample if x.get("resolved_regime")})
        result = {"strategy_name": key[1], "strategy_family": key[0], "execution_definition_hash": digest,
                  "alias_group": aliases.get(digest), "alias_status": "EXECUTION_IDENTICAL_ALIAS" if digest in aliases else "ECONOMICALLY_UNIQUE",
                  "economic_definition": definitions[key], "evidence_sample": "FORWARD_OOS" if oos else "DEVELOPMENT_FALLBACK",
                  "role_counts": dict(Counter(x["sample_role"] for x in all_rows)), "sample_structure": sample_structure,
                  "statistics": stat, "oos_status":"FORWARD_OOS_POSITIVE_POINT_ESTIMATE" if oos and (stat["ev_pct"] or 0)>0 else "FORWARD_OOS_NEGATIVE_POINT_ESTIMATE" if oos else "NO_FORWARD_OOS_SAMPLE", "naive_ci": naive, "cluster_aware_ci": clustered,
                  "regime_coverage": {"observed": regimes, "unavailable": [x for x in ("BULL", "BEAR", "SIDEWAYS", "MIXED") if x not in regimes], "robustness_claim_allowed": len(regimes) >= 2},
                  "robustness": {"by_asset": grouped_metrics(sample, lambda x:x["asset"]), "by_market_regime": grouped_metrics(sample, lambda x:x["resolved_regime"]),
                      "by_time_period": grouped_metrics(sample, lambda x:str(x["market_data_timestamp"])[:7]),
                      "by_signal_cluster_size": grouped_metrics(sample, lambda x:Counter(y["cluster_timestamp"] for y in sample)[x["cluster_timestamp"]])},
                  "concentration": concentration(sample, stat["ev_pct"])}
        result["classification"], result["major_warnings"] = classification(result)
        independence=10*math.log10(1+(sample_structure["diagnostic_effective_n"] or 0))
        result["evidence_quality_score"] = round(min(40,independence) + min(20,len(regimes)*10) + (20 if clustered["lower_pct"] is not None else 0) + (10 if not result["concentration"]["one_asset_concentration"] else 0) + (10 if not result["concentration"]["one_timestamp_concentration"] else 0) - (10 if result["alias_status"]=="EXECUTION_IDENTICAL_ALIAS" else 0),3)
        strategies.append(result)
    strategies.sort(key=lambda x:(-x["evidence_quality_score"], x["strategy_family"], x["strategy_name"]))
    tested_rows=[x for x in strategies if x["sample_structure"]["raw_episode_n"]>0];tested=len(tested_rows);unique=len({x["execution_definition_hash"] for x in tested_rows})
    return {"schema_version":"1.0.0", "generated_at_utc":datetime.now(timezone.utc).isoformat(), "purpose":"RESEARCH_EVIDENCE_AUDIT_ONLY",
            "controls":["NO_PARAMETER_OPTIMIZATION","NO_STRATEGY_DEFINITION_CHANGES","NO_SAME_SAMPLE_TUNING","NO_TRADING_CAPABILITY"],
            "methodology":{"primary_sample":"FORWARD_OOS_WHEN_AVAILABLE","cluster_resampling_unit":"simultaneous_entry_timestamp_signal_cluster; conservative because per-asset snapshot timestamps within one signal batch differ","bootstrap_samples":BOOTSTRAP_SAMPLES,"deterministic_seed_base":SEED,"diagnostic_effective_n":"ONE_WAY_RANDOM_EFFECTS_ICC_WITH_UNEQUAL_CLUSTER_DESIGN_EFFECT"},
            "multiple_testing":{"configured_strategy_variants":len(strategies),"strategy_variants_tested":tested,"economically_unique_execution_definitions":unique,"alias_count":tested-unique,"configurations_without_outcomes":len(strategies)-tested,"correction":"NOT_APPLIED; raw and clustered uncertainty retained"},
            "alias_groups":[{"alias_group":aliases[d],"execution_definition_hash":d,"strategies":[{"strategy_family":k[0],"strategy_name":k[1]} for k in sorted(hash_groups[d])]} for d in sorted(aliases)],
            "ranking_basis":"EVIDENCE_QUALITY_NOT_HISTORICAL_EV", "strategies":strategies}


def render(report: dict) -> str:
    lines=["# Strategy Evidence Audit V1","","RESEARCH ONLY — no trading instructions or parameter selection.","",f"Variants: {report['multiple_testing']['strategy_variants_tested']} | economically unique: {report['multiple_testing']['economically_unique_execution_definitions']} | aliases: {report['multiple_testing']['alias_count']}","","## Evidence-quality ranking",""]
    for x in report["strategies"]:
        s=x["sample_structure"];lines.append(f"- {x['strategy_family']} / {x['strategy_name']} | {x['classification']} | quality {x['evidence_quality_score']} | raw N {s['raw_episode_n']} | diagnostic effective N {s['diagnostic_effective_n']} | EV {x['statistics']['ev_pct']} | naive CI [{x['naive_ci']['lower_pct']}, {x['naive_ci']['upper_pct']}] | clustered CI [{x['cluster_aware_ci']['lower_pct']}, {x['cluster_aware_ci']['upper_pct']}] | alias {x['alias_group'] or 'none'} | warnings {','.join(x['major_warnings']) or 'none'}")
    lines += ["","## Alias groups",""] + [f"- {x['alias_group']}: "+", ".join(y['strategy_name'] for y in x['strategies']) for x in report["alias_groups"]]
    lines += ["","Cluster bootstrap resamples simultaneous entry-timestamp signal clusters with replacement. Diagnostic effective N does not replace canonical N.","","TRADING DISABLED"]
    return "\n".join(lines)+"\n"


def run(db_path: Path = DB_PATH, paper_db: Path = PAPER_DB, out_json: Path = OUT_JSON, out_md: Path = OUT_MD) -> dict:
    report=analyze(Path(db_path),Path(paper_db));atomic_json(out_json,report);out_md.parent.mkdir(parents=True,exist_ok=True);out_md.write_text(render(report));return report


def main() -> None:
    p=argparse.ArgumentParser();p.add_argument("--db",type=Path,default=DB_PATH);p.add_argument("--paper-db",type=Path,default=PAPER_DB);a=p.parse_args();run(a.db,a.paper_db);print(OUT_JSON);print(OUT_MD)


if __name__ == "__main__": main()
