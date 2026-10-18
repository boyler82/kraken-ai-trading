"""Bounded downstream AI/Grok interface; no external service integration."""
from .schemas import BASIS, VERSION

def compact(evidence, signals, outcomes, run_id):
    pending=sum(o['status']=='PENDING' for o in outcomes)
    events=sorted([s for s in signals if s['classification']=='MEASURABLE'],key=lambda s:(s['observation_timestamp_utc'],s['signal_id']),reverse=True)[:10]
    return {'schema_version':VERSION,'run_id':run_id,'run_timestamp_utc':evidence['as_of_utc'],
            'timing_basis':BASIS,'purpose':'EVENT_STUDY_NOT_EXECUTED_TRADES',
            'pipeline_health':'OK_OFFLINE_MEASUREMENT','data_quality':evidence['data_quality'],'trading_capability':'DISABLED',
            'market_data_cutoff_utc':max((s['market_data_cutoff_utc'] for s in signals if s.get('market_data_cutoff_utc')),default=None),
            'inventory':evidence['inventory'],'horizon_counts':evidence['horizon_counts'],
            'lifecycle_model_version':evidence['lifecycle_model_version'],
            'measurement_counts':evidence['measurement_counts'],
            'benchmark_preflight':evidence['benchmark_preflight'],
            'pending_forward_observations':pending, 'evidence_status':'NO_CONFIRMED_EDGE',
            'warnings':evidence['warnings'],
            'strategy_evidence':[{'strategy_id':r['strategy_id'],'cohort':r['cohort'],
                'raw_n':r['raw_n'],'independent_cluster_n':r['independent_cluster_n']}
                for r in evidence['strategy_reports']][:30],
            'configuration_versions':sorted({s['configuration_version'] for s in signals if s.get('configuration_version')}),
            'material_events':[{'event_id':s['signal_id'],'timestamp_utc':s['observation_timestamp_utc'],
               'asset':s['asset'],'event_type':s['event_type'],'cohort':s['cohort'],
               'timing_basis':s['timing_basis'],'features':s['features']['values'],
               'regime':s['regime']['values'],'anomaly_score':None,
               'strategy_matches':[s['strategy_id']], 'evidence_status':'REQUIRES_FORWARD_VALIDATION',
               'data_quality_flags':s['reason_codes']} for s in events],
            'source_references':{'evidence':'RESEARCH_REPORTS/QUANT_RESEARCH_V2/latest_evidence.json',
               'parameters':'RESEARCH_REPORTS/QUANT_RESEARCH_V2/parameter_stability.json'},
            'grok_delivery':'NOT_IMPLEMENTED_INTERFACE_ONLY'}
