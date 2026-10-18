from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

LABELS=["RESEARCH_ONLY","NOT_A_BUY_SIGNAL","NOT_A_SELL_SIGNAL","PAPER_NOT_AUTHORIZED","LIVE_NOT_AUTHORIZED","USER_DECISION_REQUIRED"]
PERIODS={"4h":4,"12h":12,"24h":24,"48h":48,"7d":168,"14d":336,"30d":720}
DEFAULTS={"minimum_score_advantage":10.0,"minimum_net_edge_pct":1.5,"minimum_holding_hours":24.0,"cooldown_hours":24.0,"maximum_rotations_7d":2,"fees_pct":.4,"slippage_pct":.2}


def synchronized_relative_series(alt: pd.DataFrame, btc: pd.DataFrame) -> pd.DataFrame:
    required={"timestamp","close"}
    if not required.issubset(alt.columns) or not required.issubset(btc.columns): raise ValueError("timestamp and close are required")
    a=alt[["timestamp","close"]].copy(); b=btc[["timestamp","close"]].copy()
    a["timestamp"]=pd.to_datetime(a["timestamp"],utc=True,errors="coerce"); b["timestamp"]=pd.to_datetime(b["timestamp"],utc=True,errors="coerce")
    a["alt_usd"]=pd.to_numeric(a.pop("close"),errors="coerce"); b["btc_usd"]=pd.to_numeric(b.pop("close"),errors="coerce")
    merged=a.merge(b,on="timestamp",how="inner",validate="one_to_one").dropna().sort_values("timestamp")
    merged=merged[(merged["alt_usd"]>0)&(merged["btc_usd"]>0)].drop_duplicates("timestamp",keep="last")
    merged["alt_btc"]=merged["alt_usd"]/merged["btc_usd"]
    return merged.reset_index(drop=True)


def _return(series: pd.Series,hours:int)->float|None:
    return None if len(series)<=hours else (float(series.iloc[-1])/float(series.iloc[-1-hours])-1)*100


def rotation_features(alt: pd.DataFrame,btc: pd.DataFrame)->dict[str,Any]:
    relative=synchronized_relative_series(alt,btc)
    if len(relative)<50: raise ValueError("insufficient synchronized history")
    alt_close=relative["alt_usd"]; btc_close=relative["btc_usd"]; rel=relative["alt_btc"]
    out:dict[str,Any]={"source_timestamp":relative.iloc[-1]["timestamp"].isoformat(),"synchronized_rows":len(relative),"sufficient_history":len(relative)>720}
    for label,hours in PERIODS.items():
        out[f"absolute_return_{label}_pct"]=_return(alt_close,hours)
        out[f"btc_return_{label}_pct"]=_return(btc_close,hours)
        out[f"relative_return_{label}_pct"]=_return(rel,hours)
    ema20=rel.ewm(span=20,adjust=False).mean(); ema50=rel.ewm(span=50,adjust=False).mean()
    out.update({"alt_btc_current":float(rel.iloc[-1]),"alt_btc_roc_24h_pct":_return(rel,24),"alt_btc_ema20":float(ema20.iloc[-1]),"alt_btc_ema50":float(ema50.iloc[-1]),"alt_btc_ema20_slope_pct":(float(ema20.iloc[-1])/float(ema20.iloc[-5])-1)*100,"alt_btc_distance_ema20_pct":(float(rel.iloc[-1])/float(ema20.iloc[-1])-1)*100})
    recent=_return(rel,12); previous=None if len(rel)<=24 else (float(rel.iloc[-13])/float(rel.iloc[-25])-1)*100
    out["relative_acceleration_pct"]=None if recent is None or previous is None else recent-previous
    rel_returns=rel.pct_change(); out["relative_strength_persistence_pct"]=float((rel_returns.tail(24)>0).mean()*100)
    a20=alt_close.ewm(span=20,adjust=False).mean(); a50=alt_close.ewm(span=50,adjust=False).mean()
    out.update({"price_vs_ema20_pct":(float(alt_close.iloc[-1])/float(a20.iloc[-1])-1)*100,"price_vs_ema50_pct":(float(alt_close.iloc[-1])/float(a50.iloc[-1])-1)*100,"ema20_slope_pct":(float(a20.iloc[-1])/float(a20.iloc[-5])-1)*100,"ema50_slope_pct":(float(a50.iloc[-1])/float(a50.iloc[-5])-1)*100})
    high=pd.to_numeric(alt.loc[alt["timestamp"].isin(relative["timestamp"]),"high"],errors="coerce") if "high" in alt else alt_close
    low=pd.to_numeric(alt.loc[alt["timestamp"].isin(relative["timestamp"]),"low"],errors="coerce") if "low" in alt else alt_close
    # Volatility is computed on synchronized closes; no missing bars are manufactured.
    ar=alt_close.pct_change().dropna(); downside=ar[ar<0]
    out.update({"realized_volatility_pct":float(ar.tail(168).std(ddof=0)*np.sqrt(24*365)*100),"downside_volatility_pct":float(downside.tail(168).std(ddof=0)*np.sqrt(24*365)*100) if len(downside) else 0.0,"maximum_adverse_move_7d_pct":float((alt_close/alt_close.cummax()-1).tail(168).min()*100)})
    prev=alt_close.shift(1); proxy_high=alt_close if len(high)!=len(alt_close) else high.reset_index(drop=True); proxy_low=alt_close if len(low)!=len(alt_close) else low.reset_index(drop=True)
    tr=pd.concat([(proxy_high-proxy_low),(proxy_high-prev).abs(),(proxy_low-prev).abs()],axis=1).max(axis=1)
    out["atr14_pct"]=float(tr.rolling(14).mean().iloc[-1]/alt_close.iloc[-1]*100)
    out["relative_trend_state"]="POSITIVE" if rel.iloc[-1]>ema20.iloc[-1]>ema50.iloc[-1] and out["alt_btc_ema20_slope_pct"]>0 else "DETERIORATING" if rel.iloc[-1]<ema20.iloc[-1] and out["relative_acceleration_pct"]<0 else "MIXED"
    return out


def btc_hold_score(btc_features:dict[str,Any],alt_features:list[dict[str,Any]],market_regime:str="UNKNOWN",fresh:bool=True)->tuple[float,dict[str,float],str]:
    trend=25 if btc_features.get("price_vs_ema20_pct",0)>0 and btc_features.get("price_vs_ema50_pct",0)>0 else 12.5 if btc_features.get("price_vs_ema20_pct",0)>0 else 0
    momentum=min(20,max(0,10+(btc_features.get("absolute_return_24h_pct") or 0)*2))
    regime={"BULL":20,"MIXED":10,"BEAR":2}.get(str(market_regime).upper(),8)
    median_rel=np.median([r.get("relative_return_24h_pct") or 0 for r in alt_features]) if alt_features else 0
    relative=min(15,max(0,7.5-median_rel*2))
    risk=10 if btc_features.get("atr14_pct",99)<3 and btc_features.get("maximum_adverse_move_7d_pct",-99)>-10 else 5
    liquid=10 if fresh else 0
    parts={"btc_absolute_trend":trend,"btc_momentum":momentum,"btc_market_regime":regime,"btc_relative_strength_alt_universe":relative,"btc_volatility_risk":risk,"btc_liquidity_freshness":liquid}
    score=round(min(100,max(0,sum(parts.values()))),4)
    state="BTC_STRONG_HOLD_ENVIRONMENT" if score>=80 else "BTC_FAVORED" if score>=60 else "NEUTRAL" if score>=40 else "USD_DEFENSIVE_BIAS" if score>=20 else "STRONG_DEFENSIVE_ENVIRONMENT"
    return score,{k:round(v,4) for k,v in parts.items()},state


def alt_rotation_score(features:dict[str,Any],context:dict[str,Any])->tuple[float,dict[str,float],dict[str,float]]:
    rs=min(25,max(0,12.5+(features.get("relative_return_24h_pct") or 0)*2.5))
    rm=min(20,max(0,10+(features.get("alt_btc_ema20_slope_pct") or 0)*5+(features.get("relative_acceleration_pct") or 0)*2))
    breakout=min(15,max(0,float(context.get("momentum_breakout_score") or 0)*.15))
    zone=str(context.get("simple_zone","")); consolidation=10 if zone=="LOWER_RANGE" and bool(context.get("range_still_valid")) else 6 if zone=="OBSERVE" else 2
    volume=min(10,max(0,5+(float(context.get("volume_z_score") or 0)*2)))
    liquidity=10 if context.get("liquidity_pass") else 0
    trend=5 if features.get("price_vs_ema20_pct",0)>0 and features.get("price_vs_ema50_pct",0)>0 else 0
    fresh=5 if context.get("freshness_status")=="FRESH" else 0
    parts={"relative_strength_vs_btc":rs,"relative_momentum_vs_btc":rm,"breakout_momentum_quality":breakout,"consolidation_location_quality":consolidation,"volume_confirmation":volume,"liquidity":liquidity,"trend_quality":trend,"data_freshness":fresh}
    over=str(context.get("overextension_risk","UNKNOWN")); rel48=features.get("relative_return_48h_pct") or 0
    penalties={"overextension":20 if over=="HIGH" else 8 if over=="MEDIUM" else 0,"failed_breakout":20 if context.get("failed_breakout") else 0,"stale_data":30 if context.get("freshness_status")!="FRESH" else 0,"low_liquidity":25 if not context.get("liquidity_pass") else 0,"wide_spread":10 if context.get("spread_pass") is False else 0,"insufficient_history":10 if not features.get("sufficient_history") else 0,"excessive_volatility":10 if features.get("atr14_pct",0)>8 else 0,"negative_downside_asymmetry":10 if features.get("maximum_adverse_move_7d_pct",0)<-15 else 0,"relative_momentum_deterioration":15 if features.get("relative_trend_state")=="DETERIORATING" else 0,"finished_move":15 if rel48>10 and over in {"MEDIUM","HIGH"} else 0,"one_candle_spike":10 if (features.get("absolute_return_4h_pct") or 0)>8 else 0}
    return round(max(0,min(100,sum(parts.values())-sum(penalties.values()))),4),{k:round(v,4) for k,v in parts.items()},penalties


def theoretical_edge(features:dict[str,Any],cost_pct:float=.6)->dict[str,Any]:
    rel=features["alt_btc_current"]; ema20=features["alt_btc_ema20"]
    momentum=max(0,features.get("relative_return_7d_pct") or 0)
    upside=min(15,max(0,momentum*.5+(features.get("relative_return_24h_pct") or 0)))
    downside=min(-.5,(ema20/rel-1)*100) if rel>ema20 else min(-1.0,(features.get("maximum_adverse_move_7d_pct") or -5)*.5)
    net=upside-cost_pct; rr=None if downside>=0 else net/abs(downside)
    return {"theoretical_relative_upside_to_target_pct":upside,"theoretical_target_edge":net,"theoretical_target_edge_pct":net,"validated_expected_edge":None,"validated_expected_edge_pct":None,"edge_validation_status":"UNVALIDATED","theoretical_relative_downside_to_invalidation_pct":downside,"relative_risk_reward":rr,"expected_holding_window":"3–10 days","probability_band":"UNKNOWN","estimated_round_trip_cost_pct":cost_pct,"estimated_slippage_pct":.2,"net_relative_upside_after_costs":net,"break_even_outperformance_vs_btc":cost_pct,"historical_sample_size":0,"historical_win_rate":None,"average_relative_gain":None,"average_relative_loss":None,"profit_factor":None,"expected_value":None,"historical_maximum_drawdown":None,"confidence":"LOW","invalidation_condition":"ALT/BTC closes below relative EMA20"}


def rotation_disposition(candidate:dict[str,Any])->tuple[str,list[str]]:
    """Label non-actionable research candidates without suppressing theoretical metrics."""
    reasons=[]
    controls=candidate.get("controls") or {}
    if candidate.get("score_advantage",float("-inf"))<DEFAULTS["minimum_score_advantage"]: reasons.append("SCORE_ADVANTAGE_TOO_LOW")
    if candidate.get("edge_validation_status")!="VALIDATED": reasons.append("UNVALIDATED_EDGE")
    if not candidate.get("historical_sample_size"): reasons.append("INSUFFICIENT_SAMPLE")
    if candidate.get("confidence") == "LOW": reasons.append("LOW_CONFIDENCE")
    if candidate.get("momentum_stage") != "BREAKOUT_CONFIRMED": reasons.append("BREAKOUT_NOT_CONFIRMED")
    if candidate.get("overextension_risk") in {"MEDIUM","HIGH"}: reasons.append("OVEREXTENSION")
    if controls.get("rotation_cost_guard") != "PASS": reasons.append("COST_GUARD_FAILED")
    return ("MONITOR_ONLY" if reasons else "ACTIONABLE_REVIEW"),reasons


def risk_flags(features:dict[str,Any],context:dict[str,Any],rotations_7d:int=0)->list[str]:
    flags=[]
    if context.get("freshness_status")!="FRESH": flags.append("STALE_DATA")
    if not context.get("liquidity_pass"): flags.append("LOW_LIQUIDITY")
    if context.get("spread_pass") is False: flags.append("WIDE_SPREAD")
    if context.get("overextension_risk")=="HIGH": flags.extend(["CHASING_EXTENDED_MOVE","FOMO_RISK"])
    if (features.get("relative_return_48h_pct") or 0)>10: flags.append("RECENCY_BIAS_RISK")
    if (features.get("absolute_return_4h_pct") or 0)>8: flags.append("ONE_CANDLE_SPIKE")
    if rotations_7d>=DEFAULTS["maximum_rotations_7d"]: flags.extend(["EXCESSIVE_ROTATION_RISK","OVERCONFIDENCE_RISK"])
    return sorted(set(flags))


def rotation_controls(score_advantage:float,net_edge:float,hours_held:float=999,hours_since_rotation:float=999,rotations_7d:int=0)->dict[str,str]:
    return {"rotation_hysteresis_status":"PASS" if score_advantage>=DEFAULTS["minimum_score_advantage"] else "NOISE_BAND","rotation_cooldown_status":"PASS" if hours_since_rotation>=DEFAULTS["cooldown_hours"] else "COOLDOWN_ACTIVE","minimum_holding_period_status":"PASS" if hours_held>=DEFAULTS["minimum_holding_hours"] else "MINIMUM_HOLD_ACTIVE","rotation_cost_guard":"PASS" if net_edge>=DEFAULTS["minimum_net_edge_pct"] else "EDGE_BELOW_COST_GUARD","overtrading_risk":"HIGH" if rotations_7d>=DEFAULTS["maximum_rotations_7d"] else "LOW"}


def choose_state(objective:str,current_holding:str,btc_score:float,best:dict[str,Any]|None,controls:dict[str,str],market_regime:str,market_only:bool=False)->str:
    holding=current_holding.upper(); objective=objective.lower()
    passes=best is not None and all(controls[k]=="PASS" for k in ("rotation_hysteresis_status","rotation_cooldown_status","minimum_holding_period_status","rotation_cost_guard")) and controls["overtrading_risk"]!="HIGH" and not best.get("critical_risk",False)
    if market_only:return "ROTATION_CANDIDATE" if passes else "HOLD_BTC_BENCHMARK" if btc_score>=60 else "MONITOR_ALT"
    if holding not in {"BTC","USD"} and best and best.get("asset")!=holding and features_deteriorating(best.get("current_holding_context",{})): return "REVIEW_ALT_TO_BTC"
    if objective=="btc":
        if holding=="BTC" and passes: return "REVIEW_BTC_TO_ALT"
        if holding=="BTC": return "HOLD_BTC"
        if holding=="USD" and btc_score>=60 and not passes: return "REVIEW_USD_TO_BTC"
        return "NO_ROTATION"
    if btc_score<40 and str(market_regime).upper()=="BEAR" and not passes: return "REVIEW_BTC_TO_USD" if holding=="BTC" else "NO_ROTATION"
    if holding=="USD" and btc_score>=60 and not passes: return "REVIEW_USD_TO_BTC"
    if holding=="BTC" and not passes: return "HOLD_BTC"
    return "REVIEW_BTC_TO_ALT" if passes and holding=="BTC" else "NO_ROTATION"


def features_deteriorating(context:dict[str,Any])->bool:
    return context.get("relative_trend_state")=="DETERIORATING" or context.get("invalidation_triggered",False)


def allocation_review_band(candidate:dict[str,Any]|None)->str:
    if not candidate or candidate.get("confidence")!="MEDIUM": return "NONE"
    return "10–25%" if candidate.get("relative_risk_reward",0)<2 else "10–50%"
