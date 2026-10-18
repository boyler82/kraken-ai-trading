from __future__ import annotations

import hashlib
import io
import json
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import daily_consolidation_watchlist_monitor as monitor
import morning_brief
import weekly_consolidation_common as common
import weekly_consolidation_scanner as scanner
import weekly_consolidation_universe as universe
import weekly_intraday_market_backfill as backfill
from consolidation_range_engine import completed_4h_bars


def _coin(symbol="btc", name="Bitcoin", rank=1):
    return {"id": name.lower().replace(" ", "-"), "symbol": symbol, "name": name, "market_cap_rank": rank, "market_cap": 1_000_000, "total_volume": 2_000_000}


def _pair(base="BTC", quote="USD", status="online", pair_id=None):
    return {"pair_id": pair_id or base+quote, "altname": pair_id or base+quote, "base": base, "quote": quote, "status": status}


def _hourly(count=40, start="2026-01-01T00:00:00Z"):
    ts=pd.date_range(start,periods=count,freq="1h",tz="UTC"); values=pd.Series(range(count),dtype=float)+100
    return pd.DataFrame({"timestamp":ts,"open":values,"high":values+2,"low":values-2,"close":values+.5,"volume":values/10,"trades":1})


def _range_row(asset="BTC"):
    timing={"count":2,"average_bars":6.0,"median_bars":6.0,"average_hours":24.0,"median_hours":24.0,"events":[]}
    return {"asset":asset,"range_low":100.0,"range_high":105.0,"midpoint":102.5,"width_pct":5.0,"range_quality":80.0,"position_zone":"NEAR_RANGE_LOW","low_to_high":timing.copy(),"high_to_low":timing.copy(),"full_traversal":timing.copy(),"duration_calendar_days":10.0,"lower_boundary_tests":3,"upper_boundary_tests":3,"false_breakouts_above":0,"false_breakdowns_below":0,"confirmed_breakouts":0,"confirmed_breakdowns":0,"trend_flatness_pass":True,"continuity_status":"CONTINUOUS","is_valid_horizontal_consolidation":True,"freshness_status":"FRESH","data_quality_status":"OK","liquidity_pass":True,"spread_pass":True,"latest_available_market_timestamp":"2026-01-10T00:00:00+00:00","status":"NEAR_RANGE_LOW"}


def test_coingecko_top_150_parsing_and_malformed():
    payload=[_coin("b", "B", 2),_coin("a","A",1)]
    assert [r["symbol"] for r in universe.parse_coingecko(payload,150)]==["a","b"]
    with pytest.raises(ValueError): universe.parse_coingecko({},150)


def test_stablecoin_and_wrapped_exclusion():
    assert common.exclusion_reason(_coin("usdt","Tether"))=="STABLECOIN_OR_FIAT_PEG"
    assert common.exclusion_reason(_coin("wbtc","Wrapped Bitcoin"))=="WRAPPED_DUPLICATE"
    assert common.exclusion_reason(_coin()) is None


def test_pair_mapping_quote_preference_and_inactive_exclusion():
    pairs=[_pair("BTC","EUR"),_pair("BTC","USDT"),_pair("BTC","USD"),_pair("BTC","USD","cancel_only","BAD")]
    assert universe.map_pair("BTC",pairs)["quote"]=="USD"
    assert universe.map_pair("ETH",pairs) is None


def test_kraken_pair_parser_malformed():
    payload={"error":[],"result":{"XXBTZUSD":{"wsname":"XBT/USD","altname":"XBTUSD","status":"online"}}}
    assert universe.parse_kraken_pairs(payload)[0]["base"]=="BTC"
    with pytest.raises(ValueError): universe.parse_kraken_pairs([])


def test_liquidity_and_spread_filters():
    coins=[_coin()]; pairs=[_pair()]
    low={"BTCUSD":{"c":["100"],"v":["1","10"],"a":["101"],"b":["99"]}}
    row=universe.build_universe(coins,pairs,low,"x")[0]
    assert row["inclusion_status"]=="EXCLUDED" and row["exclusion_reason"]=="INSUFFICIENT_KRAKEN_LIQUIDITY"
    rich={"BTCUSD":{"c":["100"],"v":["1","10000"],"a":["100.1"],"b":["99.9"]}}
    assert universe.build_universe(coins,pairs,rich,"x")[0]["inclusion_status"]=="INCLUDED"


def test_incremental_update_incomplete_exclusion_and_no_fill():
    existing=_hourly(5); incoming=_hourly(5,start="2026-01-01T05:00:00Z")
    combined,quality=backfill.merge_incremental(existing,incoming,"2026-01-01T09:30:00Z")
    assert len(combined)==9 and quality["incomplete_bars_rejected"]==1
    gapped=_hourly(8).drop(index=2); derived=completed_4h_bars(gapped,"2026-01-02T00:00:00Z","1H")
    assert len(derived)==1


def test_atomic_write_and_backup(tmp_path):
    path=tmp_path/"x.txt"; common.atomic_write(path,"one");common.atomic_write(path,"two")
    assert path.read_text()=="two" and path.with_suffix(".txt.bak").read_text()=="one"


def test_retry_backoff_with_mocked_opener(monkeypatch):
    calls=[]
    class Response:
        def __enter__(self): return self
        def __exit__(self,*args): return False
        def read(self): return b'{"ok": true}'
    def opener(*args,**kwargs):
        calls.append(1)
        if len(calls)<2: raise OSError("temporary")
        return Response()
    monkeypatch.setattr(common.time,"sleep",lambda _:None)
    assert common.get_json("https://example.test",retries=2,pause=0,opener=opener)=={"ok":True}
    assert len(calls)==2


def test_kraken_ohlc_missing_and_malformed_response():
    rows=[[1,1,2,.5,1.5,1,10,2]]
    assert len(backfill.parse_kraken_ohlc({"error":[],"result":{"PAIR":rows,"last":1}}))==1
    with pytest.raises(ValueError): backfill.parse_kraken_ohlc({"error":["bad"]})


def test_theoretical_cost_and_cycle_calculations():
    result=common.opportunity_metrics(_range_row())
    assert result["gross_range_return_pct"]==pytest.approx(5)
    assert result["estimated_total_friction_pct"]==pytest.approx(.6)
    assert result["estimated_net_range_return_pct"]==pytest.approx(4.4)
    assert result["average_full_cycle_hours"]==48
    assert result["estimated_cycles_per_30d"]==15


def test_insufficient_cycle_handling():
    row=_range_row();row["high_to_low"]["average_hours"]=None
    result=common.opportunity_metrics(row)
    assert result["estimated_cycles_per_30d"] is None
    assert result["cycle_history_status"]=="INSUFFICIENT_CYCLE_HISTORY"


def test_opportunity_score_contributions_total():
    row=_range_row();row.update(common.opportunity_metrics(row));score,parts=common.opportunity_score(row)
    assert score==round(sum(parts.values()),4)


def test_weekly_ranking_is_deterministic():
    a=_range_row("A");b=_range_row("B")
    for i,row in enumerate((a,b)): row.update({"weekly_range_opportunity_score":50,"estimated_net_range_return_pct":4,"completed_traversals_per_30d":4,"kraken_24h_quote_volume":1000})
    assert [r["asset"] for r in scanner.rank_rows([b,a])]==["A","B"]


def test_watchlist_selection_and_expiry():
    row=_range_row();row.update(common.opportunity_metrics(row));row.update({"weekly_rank":1,"kraken_pair":"BTCUSD","weekly_range_opportunity_score":80,"risk_flags":[]})
    selected=scanner.select_watchlist([row],"2026-01-04",15)
    assert selected[0]["watchlist_expiry_date"]=="2026-01-11"


def test_stale_and_critical_risk_excluded_from_watchlist():
    row=_range_row();row.update(common.opportunity_metrics(row));row.update({"weekly_rank":1,"kraken_pair":"BTCUSD","weekly_range_opportunity_score":80,"risk_flags":["STALE_DATA"],"freshness_status":"STALE"})
    assert scanner.select_watchlist([row],"2026-01-04",15)==[]


def test_daily_status_update_and_invalidation():
    selected={"range_low":100,"range_high":110,"watchlist_expiry_date":"2026-02-01"}
    bars=_hourly(80);bars.loc[:,"close"]=105;bars.loc[:,"open"]=105;bars.loc[:,"high"]=106;bars.loc[:,"low"]=104
    row=monitor.monitor_row(selected,completed_4h_bars(bars,"2026-01-05T00:00:00Z","1H"),"2026-01-05T00:00:00Z")
    assert row["range_still_valid"] and row["status"]=="IN_RANGE"
    selected["watchlist_expiry_date"]="2026-01-01"
    assert not monitor.monitor_row(selected,completed_4h_bars(bars,"2026-01-05T00:00:00Z","1H"),"2026-01-05T00:00:00Z")["range_still_valid"]


def test_morning_brief_graceful_fallback():
    assert morning_brief._weekly_consolidation_rows(pd.DataFrame())==[]


@pytest.mark.archive
def test_no_sqlite_strategy_or_btc_mutation(tmp_path):
    protected=list((ROOT/"journal").glob("*.sqlite"))+list((ROOT/"STRATEGIES").rglob("*.py"))+[ROOT/"DATASETS/BTC_4H_DONCHIAN_V1/BTCUSD_15m_operational.csv"]
    before={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
    row=_range_row();row.update(common.opportunity_metrics(row));common.opportunity_score(row)
    common.atomic_write(tmp_path/"research.txt","ok")
    assert before=={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
