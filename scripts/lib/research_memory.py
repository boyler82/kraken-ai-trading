from __future__ import annotations

import hashlib
import json
import math
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import median
from typing import Any, Iterable

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "RESEARCH_MEMORY"
DB_PATH = BASE / "research_memory.sqlite"
PAPER_DB = ROOT / "PAPER_RESEARCH/paper_strategy_research.sqlite"
STATS = BASE / "STATS"
ANALOGS = BASE / "ANALOGS"
SNAPSHOTS = BASE / "SNAPSHOTS"
OUTCOMES = BASE / "OUTCOMES"
BASELINE = "RESEARCH_MEMORY_V1_BASELINE"
WARNINGS = ["MULTIPLE_TESTING_RISK", "DATA_SNOOPING_RISK", "CORRELATED_VARIANT_SAMPLE"]

SNAPSHOT_FIELDS = [
    "snapshot_id", "timestamp_utc", "run_id", "asset", "kraken_pair", "current_price",
    "market_regime", "btc_hold_score", "rotation_state", "rotation_score_advantage",
    "universe_above_ema20_pct", "universe_outperforming_btc_24h_pct",
    "relative_strength_percentile", "relative_trend", "return_vs_btc_24h_pct",
    "return_vs_btc_48h_pct", "return_vs_btc_7d_pct", "momentum_stage",
    "momentum_acceleration", "volume_z_score", "volatility_expansion",
    "distance_to_breakout_pct", "extension_risk", "range_validity", "range_state",
    "range_position_pct", "range_quality", "range_low", "range_midpoint", "range_high",
    "downside_to_invalidation_pct", "upside_to_midpoint_pct", "upside_to_high_pct",
    "spread", "liquidity", "capital_flow_alignment", "sector", "sector_rank",
    "evidence_confidence_score", "decision_impact_score", "opportunity_age_hours",
    "opportunity_age_status", "supporting_modules_json", "opposing_modules_json",
    "primary_hypothesis", "sample_role", "portfolio_weight_pct_at_snapshot", "currently_held_at_snapshot",
]

def ensure_dirs() -> None:
    for p in (BASE, STATS, ANALOGS, SNAPSHOTS, OUTCOMES): p.mkdir(parents=True, exist_ok=True)

def connect(path: Path = DB_PATH) -> sqlite3.Connection:
    ensure_dirs(); db = sqlite3.connect(path); db.row_factory = sqlite3.Row
    db.executescript("""
    PRAGMA foreign_keys=ON;
    CREATE TABLE IF NOT EXISTS research_metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS research_market_snapshots(
      snapshot_id TEXT PRIMARY KEY,timestamp_utc TEXT NOT NULL,run_id TEXT NOT NULL,asset TEXT NOT NULL,kraken_pair TEXT,current_price REAL,
      market_regime TEXT,btc_hold_score REAL,rotation_state TEXT,rotation_score_advantage REAL,universe_above_ema20_pct REAL,
      universe_outperforming_btc_24h_pct REAL,relative_strength_percentile REAL,relative_trend TEXT,return_vs_btc_24h_pct REAL,
      return_vs_btc_48h_pct REAL,return_vs_btc_7d_pct REAL,momentum_stage TEXT,momentum_acceleration REAL,volume_z_score REAL,
      volatility_expansion REAL,distance_to_breakout_pct REAL,extension_risk TEXT,range_validity INTEGER,range_state TEXT,
      range_position_pct REAL,range_quality REAL,range_low REAL,range_midpoint REAL,range_high REAL,downside_to_invalidation_pct REAL,
      upside_to_midpoint_pct REAL,upside_to_high_pct REAL,spread REAL,liquidity REAL,capital_flow_alignment TEXT,sector TEXT,
      sector_rank REAL,evidence_confidence_score REAL,decision_impact_score REAL,opportunity_age_hours REAL,opportunity_age_status TEXT,
      supporting_modules_json TEXT,opposing_modules_json TEXT,primary_hypothesis TEXT,sample_role TEXT NOT NULL CHECK(sample_role IN ('DEVELOPMENT','FORWARD_OOS')),portfolio_weight_pct_at_snapshot REAL,currently_held_at_snapshot INTEGER,
      UNIQUE(timestamp_utc,run_id,asset));
    CREATE TABLE IF NOT EXISTS research_forward_outcomes(
      snapshot_id TEXT PRIMARY KEY,return_4h_pct REAL,return_12h_pct REAL,return_24h_pct REAL,return_48h_pct REAL,
      mfe_12h_pct REAL,mae_12h_pct REAL,mfe_24h_pct REAL,mae_24h_pct REAL,mfe_48h_pct REAL,mae_48h_pct REAL,updated_at TEXT,
      FOREIGN KEY(snapshot_id) REFERENCES research_market_snapshots(snapshot_id));
    CREATE TABLE IF NOT EXISTS research_setup_outcomes(
      outcome_id TEXT PRIMARY KEY,setup_episode_id TEXT NOT NULL,snapshot_id TEXT,asset TEXT NOT NULL,strategy_family TEXT,strategy_variant TEXT,
      entry_timestamp TEXT,exit_timestamp TEXT,entry_price REAL,exit_price REAL,outcome TEXT,exit_reason TEXT,gross_return_pct REAL,net_return_pct REAL,
      mfe_pct REAL,mae_pct REAL,holding_hours REAL,target_pct REAL,stop_pct REAL,market_regime_at_entry TEXT,
      relative_strength_percentile_at_entry REAL,range_position_pct_at_entry REAL,volume_z_score_at_entry REAL,momentum_stage_at_entry TEXT,
      sample_role TEXT NOT NULL CHECK(sample_role IN ('DEVELOPMENT','FORWARD_OOS')),UNIQUE(setup_episode_id,strategy_variant),
      FOREIGN KEY(snapshot_id) REFERENCES research_market_snapshots(snapshot_id));
    CREATE INDEX IF NOT EXISTS idx_rm_snapshot_asset_time ON research_market_snapshots(asset,timestamp_utc);
    CREATE INDEX IF NOT EXISTS idx_rm_episode ON research_setup_outcomes(setup_episode_id);
    CREATE TABLE IF NOT EXISTS research_conditional_stats(
      analysis_key TEXT PRIMARY KEY,analysis_level INTEGER,dimensions_json TEXT,values_json TEXT,unique_episode_count INTEGER,variant_trade_count INTEGER,
      wins INTEGER,losses INTEGER,win_rate REAL,average_win_pct REAL,average_loss_pct REAL,mean_return_pct REAL,median_return_pct REAL,
      expected_value_pct REAL,profit_factor REAL,maximum_drawdown_pct REAL,median_mfe_pct REAL,median_mae_pct REAL,median_holding_hours REAL,
      ev_delta_vs_baseline REAL,wr_delta_vs_baseline REAL,pf_delta_vs_baseline REAL,sample_quality TEXT,research_label TEXT,warnings_json TEXT,updated_at TEXT);
    """)
    columns={x[1] for x in db.execute('PRAGMA table_info(research_market_snapshots)')}
    if 'portfolio_weight_pct_at_snapshot' not in columns:db.execute('ALTER TABLE research_market_snapshots ADD COLUMN portfolio_weight_pct_at_snapshot REAL')
    if 'currently_held_at_snapshot' not in columns:db.execute('ALTER TABLE research_market_snapshots ADD COLUMN currently_held_at_snapshot INTEGER')
    initialize_baseline(db); return db

def _now() -> str: return datetime.now(timezone.utc).isoformat()
def _clean(v: Any) -> Any:
    if v is None or (isinstance(v, float) and (math.isnan(v) or math.isinf(v))): return None
    if hasattr(v, "item"): v = v.item()
    return v
def _json(path: Path) -> dict:
    try: return json.loads(path.read_text())
    except Exception: return {}
def _csv(path: Path) -> pd.DataFrame:
    try: return pd.read_csv(path)
    except Exception: return pd.DataFrame()
def _map(frame: pd.DataFrame) -> dict[str, dict]:
    return {str(r["asset"]): {k:_clean(v) for k,v in r.to_dict().items()} for _,r in frame.iterrows()} if len(frame) and "asset" in frame else {}

def initialize_baseline(db: sqlite3.Connection, paper_db: Path = PAPER_DB) -> None:
    if db.execute("SELECT 1 FROM research_metadata WHERE key='baseline_name'").fetchone(): return
    count = 0
    if paper_db.exists():
        src=sqlite3.connect(f"file:{paper_db}?mode=ro",uri=True)
        count=src.execute("SELECT count(DISTINCT s.setup_episode_id) FROM paper_trades t JOIN paper_signals s ON s.signal_id=t.signal_id WHERE t.status='CLOSED'").fetchone()[0];src.close()
    for k,v in (("baseline_name",BASELINE),("baseline_created_at",_now()),("paper_unique_closed_at_baseline",str(count))):
        db.execute("INSERT INTO research_metadata VALUES(?,?)",(k,v))
    db.commit()

def deterministic_snapshot_id(timestamp: str, run_id: str, asset: str) -> str:
    return hashlib.sha256(f"{timestamp}|{run_id}|{asset}".encode()).hexdigest()[:24]

def capture_current_snapshots(db: sqlite3.Connection, timestamp: str, run_id: str, candidates: list[dict], market: dict,use_portfolio:bool=False) -> int:
    inserted=0
    try:
        if not use_portfolio:raise RuntimeError('portfolio context disabled')
        from portfolio_state import load_current_portfolio,get_holding
        portfolio=load_current_portfolio()
    except Exception:portfolio={}
    for c in candidates:
        asset=str(c.get("asset") or "");
        if not asset: continue
        cur=c.get("current_data",{}); con=c.get("consolidation",{}); mom=c.get("momentum",{}); rs=c.get("relative_strength",{}); rot=c.get("rotation",{}); sec=c.get("sector_capital_flow",{}); dec=c.get("decision_metrics",{}); ev=c.get("evidence",{})
        row={"snapshot_id":deterministic_snapshot_id(timestamp,run_id,asset),"timestamp_utc":timestamp,"run_id":run_id,"asset":asset,
          "kraken_pair":c.get("identity",{}).get("kraken_pair"),"current_price":cur.get("current_price"),"market_regime":market.get("crypto_regime"),
          "btc_hold_score":market.get("btc_hold_score"),"rotation_state":rot.get("rotation_state"),"rotation_score_advantage":rot.get("score_advantage"),
          "universe_above_ema20_pct":market.get("universe_above_ema20_pct"),"universe_outperforming_btc_24h_pct":market.get("universe_outperforming_btc_24h_pct"),
          "relative_strength_percentile":rs.get("percentile_rank"),"relative_trend":rs.get("relative_trend"),"return_vs_btc_24h_pct":rs.get("return_vs_btc_24h_pct"),
          "return_vs_btc_48h_pct":rs.get("return_vs_btc_48h_pct"),"return_vs_btc_7d_pct":rs.get("return_vs_btc_7d_pct"),"momentum_stage":mom.get("stage"),
          "momentum_acceleration":mom.get("acceleration"),"volume_z_score":mom.get("volume_z_score"),"volatility_expansion":mom.get("volatility_expansion"),
          "distance_to_breakout_pct":mom.get("distance_to_breakout_pct"),"extension_risk":mom.get("extension_risk"),"range_validity":con.get("range_validity"),
          "range_state":con.get("range_state"),"range_position_pct":con.get("position_percent"),"range_quality":con.get("range_quality"),"range_low":con.get("range_low"),
          "range_midpoint":con.get("midpoint"),"range_high":con.get("range_high"),"downside_to_invalidation_pct":con.get("downside_to_invalidation_pct"),
          "upside_to_midpoint_pct":con.get("net_upside_to_midpoint_pct"),"upside_to_high_pct":con.get("net_upside_to_high_pct"),"spread":cur.get("spread"),"liquidity":cur.get("liquidity"),
          "capital_flow_alignment":sec.get("capital_flow_alignment"),"sector":c.get("identity",{}).get("sector"),"sector_rank":sec.get("sector_rank"),
          "evidence_confidence_score":dec.get("evidence_confidence_score"),"decision_impact_score":dec.get("decision_impact_score"),"opportunity_age_hours":dec.get("opportunity_age_hours"),
          "opportunity_age_status":dec.get("opportunity_age_status"),"supporting_modules_json":json.dumps(ev.get("supporting_modules") or []),"opposing_modules_json":json.dumps(ev.get("opposing_modules") or []),
          "primary_hypothesis":dec.get("current_primary_hypothesis"),"sample_role":"FORWARD_OOS"}
        if use_portfolio:
            holding=get_holding(asset,portfolio) if portfolio else None
            row.update(portfolio_weight_pct_at_snapshot=holding.get('portfolio_weight_pct') if holding else None,currently_held_at_snapshot=1 if holding else 0)
        vals=[_clean(row.get(x)) for x in SNAPSHOT_FIELDS]; before=db.total_changes
        db.execute(f"INSERT OR IGNORE INTO research_market_snapshots({','.join(SNAPSHOT_FIELDS)}) VALUES({','.join('?' for _ in SNAPSHOT_FIELDS)})",vals)
        inserted += db.total_changes-before
        db.execute("INSERT OR IGNORE INTO research_forward_outcomes(snapshot_id) VALUES(?)",(row["snapshot_id"],))
    db.commit(); return inserted

def import_paper_outcomes(db: sqlite3.Connection, paper_db: Path = PAPER_DB) -> int:
    if not paper_db.exists(): return 0
    baseline=datetime.fromisoformat(db.execute("SELECT value FROM research_metadata WHERE key='baseline_created_at'").fetchone()[0])
    src=sqlite3.connect(f"file:{paper_db}?mode=ro",uri=True);src.row_factory=sqlite3.Row
    rows=src.execute("""SELECT t.*,s.setup_episode_id,s.pair,v.config_json FROM paper_trades t JOIN paper_signals s ON s.signal_id=t.signal_id
      LEFT JOIN paper_strategy_variants v ON v.strategy_name=t.strategy_name AND v.strategy_variant=t.strategy_variant WHERE t.status='CLOSED'""").fetchall();src.close(); inserted=0
    for r in rows:
        entry=datetime.fromisoformat(str(r["entry_timestamp"]).replace("Z","+00:00")).astimezone(timezone.utc)
        snap=db.execute("SELECT * FROM research_market_snapshots WHERE asset=? AND timestamp_utc<=? ORDER BY abs(julianday(timestamp_utc)-julianday(?)) LIMIT 1",(r["asset"],entry.isoformat(),entry.isoformat())).fetchone()
        # Historical context is linked only if it existed at or before entry; it is never reconstructed.
        cfg=json.loads(r["config_json"] or "{}")
        role="DEVELOPMENT" if entry <= baseline else "FORWARD_OOS"
        oid=hashlib.sha256(f'{r["setup_episode_id"]}|{r["strategy_variant"]}'.encode()).hexdigest()[:24]
        values=(oid,r["setup_episode_id"],snap["snapshot_id"] if snap else None,r["asset"],r["strategy_name"],r["strategy_variant"],r["entry_timestamp"],r["exit_timestamp"],r["entry_price"],r["exit_price"],r["result_class"],r["exit_reason"],r["gross_return_pct"],r["net_return_pct"],r["mfe_pct"],r["mae_pct"],r["holding_hours"],cfg.get("target_pct"),cfg.get("stop_pct"),snap["market_regime"] if snap else None,snap["relative_strength_percentile"] if snap else None,snap["range_position_pct"] if snap else None,snap["volume_z_score"] if snap else None,snap["momentum_stage"] if snap else None,role)
        before=db.total_changes;db.execute("INSERT OR IGNORE INTO research_setup_outcomes VALUES("+",".join("?" for _ in values)+")",values);inserted+=db.total_changes-before
    db.commit();return inserted

def _market_frame(pair: str) -> pd.DataFrame:
    p=ROOT/f"DATASETS/market_intraday_weekly/{pair}_1H.csv"
    d=_csv(p)
    if d.empty: return d
    d["timestamp"]=pd.to_datetime(d["timestamp"],utc=True);return d.sort_values("timestamp")

def update_forward_outcomes(db: sqlite3.Connection, now: str | None = None) -> int:
    cutoff=pd.Timestamp(now or _now()); updated=0
    for s in db.execute("SELECT s.*,f.* FROM research_market_snapshots s JOIN research_forward_outcomes f USING(snapshot_id)").fetchall():
        d=_market_frame(s["kraken_pair"] or "")
        if d.empty or not s["current_price"]: continue
        ts=pd.Timestamp(s["timestamp_utc"]); vals={}; price=float(s["current_price"])
        for h in (4,12,24,48):
            target=ts+timedelta(hours=h)
            if cutoff < target: continue
            eligible=d[(d.timestamp>ts)&(d.timestamp<=target)]
            at=d[d.timestamp>=target]
            if at.empty or eligible.empty: continue
            vals[f"return_{h}h_pct"]=(float(at.iloc[0].close)/price-1)*100
            if h in (12,24,48): vals[f"mfe_{h}h_pct"]=(float(eligible.high.max())/price-1)*100;vals[f"mae_{h}h_pct"]=(float(eligible.low.min())/price-1)*100
        vals={k:v for k,v in vals.items() if s[k] is None}
        if vals:
            db.execute("UPDATE research_forward_outcomes SET "+",".join(f"{k}=?" for k in vals)+",updated_at=? WHERE snapshot_id=?",(*vals.values(),_now(),s["snapshot_id"]));updated+=1
    db.commit();return updated

def sample_quality(n: int) -> str:
    return "INSUFFICIENT" if n<10 else "VERY_LOW" if n<30 else "LOW" if n<50 else "MEDIUM" if n<100 else "HIGHER_CONFIDENCE"
def rs_bucket(v): return _bucket(v,[(20,"0-20"),(40,"20-40"),(60,"40-60"),(80,"60-80"),(90,"80-90"),(101,"90-100")])
def range_bucket(v):
    if v is None:return None
    if v<0 or v>100:return "outside_range"
    return _bucket(v,[(10,"<10%"),(20,"10-20%"),(40,"20-40%"),(60,"40-60%"),(80,"60-80%"),(101,"80-100%")])
def volume_bucket(v): return _bucket(v,[(-1,"<-1"),(0,"-1 to 0"),(1,"0 to 1"),(2,"1 to 2"),(float("inf"),">2")])
def breadth_bucket(v): return _bucket(v,[(20,"0-20"),(40,"20-40"),(60,"40-60"),(80,"60-80"),(101,"80-100")])
def _bucket(v,bounds):
    if v is None:return None
    return next((label for upper,label in bounds if float(v)<upper),bounds[-1][1])
def maximum_drawdown(returns: Iterable[float]) -> float:
    equity=peak=1.0; worst=0.0
    for r in returns: equity*=1+float(r)/100;peak=max(peak,equity);worst=min(worst,(equity/peak-1)*100)
    return worst
def metrics(rows: list[dict]) -> dict:
    # One deterministic representative per correlated setup episode for outcome metrics.
    reps={}
    for r in sorted(rows,key=lambda x:(x["setup_episode_id"],x["strategy_variant"] or "")): reps.setdefault(r["setup_episode_id"],r)
    u=list(reps.values()); raw_returns=[float(x["net_return_pct"]) for x in u if x["net_return_pct"] is not None]
    returns=[x for x in raw_returns if math.isfinite(x)]; non_finite_count=len(raw_returns)-len(returns)
    wins=[x for x in returns if x>0]; losses=[x for x in returns if x<=0]
    n=len(returns); loss_sum=sum(losses)
    if wins and loss_sum == 0:
        pf=None;pf_status="INFINITE_NO_LOSSES";pf_reason="positive gross profit with zero gross loss"
    elif not wins and loss_sum == 0:
        pf=None;pf_status="UNDEFINED_NO_GAINS_OR_LOSSES";pf_reason="no positive gain or negative loss observations"
    else:
        pf=sum(wins)/abs(loss_sum);pf_status="FINITE";pf_reason=None
    return {"unique_episode_count":n,"variant_trade_count":len(rows),"wins":len(wins),"losses":len(losses),"win_rate":100*len(wins)/n if n else None,
      "average_win_pct":sum(wins)/len(wins) if wins else None,"average_loss_pct":sum(losses)/len(losses) if losses else None,"mean_return_pct":sum(returns)/n if n else None,
      "median_return_pct":median(returns) if returns else None,"expected_value_pct":sum(returns)/n if n else None,"profit_factor":pf,"profit_factor_status":pf_status,"profit_factor_reason":pf_reason,"non_finite_observation_count":non_finite_count,"observation_status":"NON_FINITE_OBSERVATIONS_EXCLUDED" if non_finite_count else "VALID_FINITE_OBSERVATIONS","maximum_drawdown_pct":maximum_drawdown(returns),
      "median_mfe_pct":median([x["mfe_pct"] for x in u if x["mfe_pct"] is not None]) if any(x["mfe_pct"] is not None for x in u) else None,
      "median_mae_pct":median([x["mae_pct"] for x in u if x["mae_pct"] is not None]) if any(x["mae_pct"] is not None for x in u) else None,
      "median_holding_hours":median([x["holding_hours"] for x in u if x["holding_hours"] is not None]) if any(x["holding_hours"] is not None for x in u) else None}

def conditional_analysis(db: sqlite3.Connection) -> list[dict]:
    raw=[dict(x) for x in db.execute("SELECT o.*,s.universe_above_ema20_pct FROM research_setup_outcomes o LEFT JOIN research_market_snapshots s USING(snapshot_id) WHERE o.exit_timestamp IS NOT NULL")]
    for r in raw:r.update(relative_strength_bucket=rs_bucket(r["relative_strength_percentile_at_entry"]),range_position_bucket=range_bucket(r["range_position_pct_at_entry"]),volume_z_bucket=volume_bucket(r["volume_z_score_at_entry"]),breadth_bucket=breadth_bucket(r["universe_above_ema20_pct"]))
    baseline={}
    for key in {(r["strategy_family"],r["strategy_variant"]) for r in raw}: baseline[key]=metrics([r for r in raw if (r["strategy_family"],r["strategy_variant"])==key])
    specs=[(1,["market_regime"]),(1,["relative_strength_bucket"]),(1,["range_position_bucket"]),(1,["volume_z_bucket"]),(1,["breadth_bucket"]),(1,["momentum_stage"]),(1,["capital_flow_alignment"]),(2,["market_regime","relative_strength_bucket"]),(2,["market_regime","range_position_bucket"]),(2,["market_regime","volume_z_bucket"]),(2,["relative_strength_bucket","range_position_bucket"])]
    out=[];db.execute("DELETE FROM research_conditional_stats")
    for level,dims in specs:
      groups={}
      for r in raw:
        vals=tuple(r.get(d) for d in dims)
        if any(v is None for v in vals):continue
        groups.setdefault((r["strategy_family"],r["strategy_variant"],*vals),[]).append(r)
      for key,items in groups.items():
        m=metrics(items)
        if level==2 and m["unique_episode_count"]<10:continue
        b=baseline[key[:2]]; vals=dict(zip(["strategy_family","strategy_variant",*dims],key)); m.update(analysis_level=level,dimensions=dims,values=vals,
          ev_delta_vs_baseline=_delta(m["expected_value_pct"],b["expected_value_pct"]),wr_delta_vs_baseline=_delta(m["win_rate"],b["win_rate"]),pf_delta_vs_baseline=_delta(m["profit_factor"],b["profit_factor"]),sample_quality=sample_quality(m["unique_episode_count"]),research_label="POTENTIAL_EDGE_ONLY" if (m["expected_value_pct"] or 0)>0 and (m["profit_factor"] or 0)>1 else "RESEARCH_ONLY",warnings=WARNINGS)
        aid=hashlib.sha256(json.dumps([level,vals],sort_keys=True).encode()).hexdigest()[:24]; cols=["analysis_level","dimensions_json","values_json","unique_episode_count","variant_trade_count","wins","losses","win_rate","average_win_pct","average_loss_pct","mean_return_pct","median_return_pct","expected_value_pct","profit_factor","maximum_drawdown_pct","median_mfe_pct","median_mae_pct","median_holding_hours","ev_delta_vs_baseline","wr_delta_vs_baseline","pf_delta_vs_baseline","sample_quality","research_label","warnings_json","updated_at"]
        encoded={**m,"dimensions_json":json.dumps(dims),"values_json":json.dumps(vals,sort_keys=True),"warnings_json":json.dumps(m["warnings"])}
        db.execute("INSERT INTO research_conditional_stats VALUES("+",".join("?" for _ in range(26))+")",(aid,*[encoded.get(x) for x in cols[:-1]],_now()))
        out.append(m)
    db.commit();return out
def _delta(a,b):
    if a is None or b is None or not math.isfinite(float(a)) or not math.isfinite(float(b)):return None
    return a-b

def atomic_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix(path.suffix+".tmp");tmp.write_text(json.dumps(obj,indent=2,sort_keys=True,allow_nan=False)+"\n");tmp.replace(path)
