"""Cohort/version/basis-separated descriptive evidence with visible attrition."""
from collections import Counter, defaultdict
from statistics import mean, median, pstdev
from .schemas import HORIZONS, FORWARD, digest, utc
from .clustering import cluster
from strategy_evidence_audit import bootstrap_ci

WARNINGS = ['MULTIPLE_TESTING_RISK', 'DATA_SNOOPING_RISK', 'CORRELATED_VARIANT_SAMPLE',
            'REGIME_IMBALANCE', 'LIMITED_REGIME_COVERAGE', 'CLUSTERS_ARE_DEPENDENCE_PROXIES',
            'OVERLAPPING_72H_HORIZONS_CAN_SPAN_CLUSTERS', 'EVENT_STUDY_NOT_EXECUTABLE_BACKTEST']

def statistics(rows):
    values = [r['return_pct'] for r in rows]
    cluster_n = len({r['cluster_id'] for r in rows})
    def distribution(key):
        vals = [r[key] for r in rows if r.get(key) is not None]
        return {'n':len(vals), 'mean':mean(vals) if vals else None, 'median':median(vals) if vals else None,
                'min':min(vals) if vals else None, 'max':max(vals) if vals else None}
    converted = [{'net_return_pct': r['return_pct'], 'cluster_timestamp': r['cluster_id']} for r in rows]
    def ci(clustered):
        result = bootstrap_ci(converted, clustered, samples=1000)
        return {k:result[k] for k in ('status', 'lower_pct', 'upper_pct', 'seed', 'samples', 'resampling_unit')}
    return {'raw_n':len(rows), 'independent_cluster_n':cluster_n,
            'asset_measurable_sample_count':len(rows),
            'benchmark_measurable_sample_count':sum(r.get('btc_return_pct') is not None for r in rows),
            'btc_relative_sample_count':sum(r.get('btc_relative_return_pct') is not None for r in rows),
            'interpretation':'STATISTICALLY_INCONCLUSIVE' if cluster_n < 20 else 'HISTORICAL_ASSOCIATION_REQUIRES_FORWARD_VALIDATION',
            'mean_return_pct':mean(values) if values else None, 'event_study_ev_pct':mean(values) if values else None,
            'median_return_pct':median(values) if values else None,
            'win_definition':'DIRECTIONAL_REFERENCE_RETURN_STRICTLY_GREATER_THAN_ZERO',
            'win_rate_pct':100*sum(v>0 for v in values)/len(values) if values else None,
            'population_std_pct':pstdev(values) if values else None,
            'naive_ci_95':ci(False), 'cluster_ci_95':ci(True),
            'mfe':distribution('mfe_pct'), 'mae':distribution('mae_pct'),
            'btc_relative':distribution('btc_relative_return_pct'),
            'regime_coverage':dict(Counter(r.get('regime_label','UNAVAILABLE') for r in rows)),
            'period_start':min((r['observation_timestamp_utc'] for r in rows),default=None),
            'period_end':max((r['observation_timestamp_utc'] for r in rows),default=None)}

def attrition(signals):
    reasons = Counter(reason for s in signals for reason in s['reason_codes'])
    return {'total_observations':len(signals),
            'measurable_observations':sum(s['classification']=='MEASURABLE' for s in signals),
            'unmeasurable_observations':sum(s['classification']=='UNMEASURABLE' for s in signals),
            'quarantined_observations':sum(s['classification']=='QUARANTINED' for s in signals),
            'prospective_forward_observations':sum(s['cohort']==FORWARD for s in signals),
            'historical_reconstructed_observations':sum(s['cohort']!=FORWARD for s in signals),
            'raw_n':len(signals), 'independent_cluster_n':len({s['cluster_id'] for s in signals if s['cluster_id']}),
            'cluster_n_shifted_12h':len({cluster(s['observation_timestamp_utc'],True) for s in signals}),
            'reason_counts_nonexclusive':dict(sorted(reasons.items())),
            'usable_by_research_purpose':dict(Counter(k for s in signals for k,v in s['research_uses'].items() if v))}

def joined(signals, outcomes):
    lookup = {s['signal_id']:s for s in signals}
    rows=[]; seen={}
    for o in outcomes:
        key=(o['signal_id'],o['timing_basis'],o['horizon_hours'])
        if key in seen:
            if seen[key]!=o:raise ValueError('DUPLICATE_MEASUREMENT_VIEW_CONFLICT')
            continue
        seen[key]=o
        s=lookup[o['signal_id']]
        if o.get('asset_state')=='ASSET_COMPLETE' or ('asset_state' not in o and o['status']=='COMPLETE'):
            rows.append({**o, 'cluster_id':s['cluster_id'], 'features':s['features']['values'],
                         'regime_label':s['regime'].get('values',{}).get('market_state','UNAVAILABLE'),
                         'strategy_id':s['strategy_id'], 'strategy_version':s['strategy_version'],
                         'configuration_version':s['configuration_version'],
                         'observation_timestamp_utc':s['observation_timestamp_utc']})
    return rows

def report(signals, outcomes, as_of):
    groups=defaultdict(list); lookup={s['signal_id']:s for s in signals}
    for s in signals:
        groups[(s['strategy_id'],s['strategy_version'],s['configuration_version'],s['cohort'],s['timing_basis'])].append(s)
    complete=joined(signals,outcomes); reports=[]
    for key, members in sorted(groups.items(),key=lambda x:str(x[0])):
        ids={s['signal_id'] for s in members}; horizons={}
        for h in HORIZONS:
            obs=[o for o in outcomes if o['signal_id'] in ids and o['horizon_hours']==h]
            rs=[r for r in complete if r['signal_id'] in ids and r['horizon_hours']==h]
            regimes={r['regime_label'] for r in rs}
            horizons[f'cc_{h}h']={'status_counts':dict(Counter(o['status'] for o in obs)),
                'reason_counts_nonexclusive':dict(Counter(v for o in obs for v in o['reason_codes'])),
                'measurement_counts':measurement_counts(members,obs),
                'statistics':statistics(rs),
                'by_regime':{g:statistics([r for r in rs if r['regime_label']==g]) for g in sorted(regimes)}}
        reports.append({'strategy_id':key[0], 'strategy_version':key[1], 'configuration_version':key[2],
                        'cohort':key[3], 'timing_basis':key[4], **attrition(members), 'horizons':horizons,
                        'warnings':WARNINGS})
    cutoffs=[utc(s['market_data_cutoff_utc']) for s in signals if s.get('market_data_cutoff_utc')]
    latest_cutoff=max(cutoffs,default=None)
    freshness='UNAVAILABLE' if latest_cutoff is None else 'STALE' if (utc(as_of)-latest_cutoff).total_seconds()>8*3600 else 'CURRENT'
    days=Counter(s['observation_timestamp_utc'][:10] for s in signals)
    weeks=Counter(str(utc(s['observation_timestamp_utc']).isocalendar()[:2]) for s in signals)
    return {'schema_version':'1.0.0','as_of_utc':as_of,'purpose':'EVENT_STUDY',
            'timing_basis':'CLOSED_CANDLE_REFERENCE_NOT_OBSERVATION_TIME_EXACT',
            'trading_capability':'DISABLED', 'inventory':attrition(signals),
            'data_quality':{'recorded_market_cutoff_freshness':freshness,'current_capture_attempted':False,
                'historical_measurement_does_not_refresh_market_data':True},
            'measurement_counts':measurement_counts(signals,outcomes),
            'horizon_counts':{f'cc_{h}h':dict(Counter(o['status'] for o in outcomes if o['horizon_hours']==h)) for h in HORIZONS},
            'strategy_reports':reports, 'warnings':WARNINGS,
            'hypotheses_reported':sum(1+len(h['by_regime']) for r in reports for h in r['horizons'].values()),
            'inference_policy':'DESCRIPTIVE_INTERVALS_NOT_MULTIPLICITY_ADJUSTED; NO_EDGE_CLAIM',
            'frequency':{'signals_by_day':dict(sorted(days.items())), 'signals_by_iso_week':dict(sorted(weeks.items())),
                         'signals_by_asset':dict(Counter(s['asset'] for s in signals)),
                         'signals_by_strategy':dict(Counter(s['strategy_id'] for s in signals)),
                         'signals_by_regime':dict(Counter(s['regime'].get('values',{}).get('market_state','UNAVAILABLE') for s in signals)),
                         'interpretation':'DIAGNOSTIC_ONLY_NO_AUTOMATIC_THRESHOLD_ADJUSTMENT'}}


def measurement_counts(signals, outcomes):
    rows = joined(signals,outcomes)
    unique = list({(r['signal_id'],r['timing_basis'],r['horizon_hours']):r for r in outcomes}.values())
    return {'sample_unit':'OBSERVATION_TIMING_BASIS_HORIZON',
            'asset_measurable_sample_count':len(rows),
            'benchmark_measurable_sample_count':sum(r.get('btc_return_pct') is not None for r in unique),
            'btc_relative_sample_count':sum(r.get('btc_relative_return_pct') is not None for r in rows),
            'distinct_asset_observations':len({r['signal_id'] for r in rows}),
            'independent_cluster_count':len({r['cluster_id'] for r in rows}),
            'benchmark_availability_policy':'AVAILABLE_AS_OF_REPORT_CUTOFF; NEVER_BACKDATED',
            'latest_benchmark_available_as_of':max((r['benchmark_available_as_of'] for r in unique if r.get('benchmark_available_as_of') and r.get('btc_return_pct') is not None),default=None)}
