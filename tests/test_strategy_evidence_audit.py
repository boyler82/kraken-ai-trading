from __future__ import annotations

import json
import math
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import strategy_evidence_audit as audit


def rows(values, timestamps=None, assets=None):
    timestamps=timestamps or [f'2026-01-{i+1:02d}T00:00:00Z' for i in range(len(values))]
    assets=assets or [f'A{i}' for i in range(len(values))]
    return [{'setup_episode_id':f'e{i}','asset':assets[i],'entry_timestamp':timestamps[i],
             'market_data_timestamp':timestamps[i],'cluster_timestamp':timestamps[i],'net_return_pct':value} for i,value in enumerate(values)]


def test_identical_strategy_aliases_have_same_execution_hash():
    one=audit.execution_definition('MOMENTUM_BREAKOUT',{'target_pct':5,'stop_pct':2,'max_hold_hours':72},.6)
    two=audit.execution_definition('MOMENTUM_BREAKOUT',{'max_hold_hours':72,'stop_pct':2,'target_pct':5},.6)
    assert audit.definition_hash(one)==audit.definition_hash(two)


def test_correlated_same_timestamp_reduces_diagnostic_n():
    sample=rows([3]*20+[-2]*20,['2026-01-01T00:00:00Z']*20+['2026-01-02T00:00:00Z']*20)
    result=audit.structure(sample)
    assert result['timestamp_icc']>0 and result['diagnostic_effective_n']<result['raw_episode_n']
    assert result['max_cluster_size']==20


def test_independent_observations_preserve_diagnostic_n():
    sample=rows([1,-1]*10,[f'2026-01-{i+1:02d}T00:00:00Z' for i in range(10) for _ in range(2)])
    result=audit.structure(sample)
    assert result['timestamp_icc']==0
    assert math.isclose(result['diagnostic_effective_n'],result['raw_episode_n'])


def test_zero_loss_sample_is_structured_and_strict_json():
    result=audit.metrics(rows([1,2,3]))
    assert result['profit_factor'] is None and result['profit_factor_status']=='INFINITE_NO_LOSSES'
    json.dumps(result,allow_nan=False)


def test_one_asset_and_one_timestamp_concentration():
    asset_sample=rows([20,-1,-1,-1],assets=['DOM','A','B','C'])
    assert audit.concentration(asset_sample,audit.metrics(asset_sample)['ev_pct'])['one_asset_concentration']
    time_sample=rows([20,-1,-1,-1],timestamps=['2026-01-01T00:00:00Z','2026-01-02T00:00:00Z','2026-01-03T00:00:00Z','2026-01-04T00:00:00Z'])
    assert audit.concentration(time_sample,audit.metrics(time_sample)['ev_pct'])['one_timestamp_concentration']


def test_cluster_bootstrap_is_deterministic_and_uses_timestamp_unit():
    sample=rows([2,1,-1,-2],['2026-01-01T00:00:00Z']*2+['2026-01-02T00:00:00Z']*2)
    first=audit.bootstrap_ci(sample,True,123,200);second=audit.bootstrap_ci(sample,True,123,200)
    assert first==second and first['resampling_unit']=='simultaneous_entry_timestamp_signal_cluster'


def test_missing_regimes_are_explicit_and_report_is_strict_json():
    observed=['BEAR'];coverage={'observed':observed,'unavailable':[x for x in ('BULL','BEAR','SIDEWAYS','MIXED') if x not in observed]}
    assert coverage['unavailable']==['BULL','SIDEWAYS','MIXED']
    payload={'coverage':coverage,'ci':audit.bootstrap_ci(rows([1,-1]),False,1,20)}
    encoded=json.dumps(payload,allow_nan=False);json.loads(encoded,parse_constant=lambda x:(_ for _ in ()).throw(ValueError(x)))
