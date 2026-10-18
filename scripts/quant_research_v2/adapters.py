"""Conservative imports: missing historical facts stay missing."""
from .schemas import (BASIS, FEATURES, FORWARD, UNRESOLVED, VERSION, digest,
                      positive, stamp, utc, validate)
from .clustering import METHOD, cluster


def historical(row):
    obs = row.get('timestamp')
    flags = []
    if not row.get('market_data_cutoff'):
        flags.append('MISSING_MARKET_CUTOFF')
    scenario = row.get('technical_scenario') or {}
    ref_time = scenario.get('reference_timestamp')
    if not ref_time:
        flags.append('MISSING_REFERENCE_PRICE_TIMESTAMP')
    elif utc(ref_time) > utc(obs):
        flags.append('REFERENCE_PRICE_AFTER_OBSERVATION')
    if not positive(row.get('current_price')):
        flags.append('MISSING_REFERENCE_PRICE')
    # No historical record promises its reference is a candle CLOSE. Never infer it.
    flags.append('MISSING_REFERENCE_CANDLE_CLOSE')
    if not row.get('strategy_version') or not row.get('configuration_version'):
        flags.append('AMBIGUOUS_CONFIGURATION_VERSION')
    if utc(obs).minute or utc(obs).second or utc(obs).microsecond:
        flags.append('INSUFFICIENT_TIMESTAMP_PRECISION_FOR_HOURLY_EXACT_OUTCOME')
    components = row.get('raw_opportunity_components') or {}
    mapping = {'return_4h': 'return_4h_pct', 'return_24h': 'return_24h_pct',
               'momentum_acceleration': 'momentum_acceleration', 'rs_percentile': 'relative_strength_percentile',
               'rs_acceleration': 'relative_acceleration', 'volume_z': 'volume_z_score',
               'volatility_expansion': 'volatility_expansion'}
    values = {k: components.get(mapping.get(k, k)) for k in FEATURES}
    return {'schema_version': VERSION, 'signal_id': 'v2h_' + digest(row['snapshot_id'])[:32],
            'source_event_id': row['snapshot_id'], 'asset': row['asset'], 'pair': row.get('kraken_pair'),
            'strategy_id': row.get('planned_trade_family') or ('OPPORTUNITY_' + row.get('opportunity_family', 'UNSPECIFIED')),
            'strategy_version': row.get('strategy_version'), 'configuration_version': row.get('configuration_version'),
            'observation_timestamp_utc': stamp(obs), 'reference_candle_close_utc': None,
            'reference_price_timestamp_utc': stamp(ref_time) if ref_time else None,
            'reference_price': row.get('current_price'), 'market_data_cutoff_utc': row.get('market_data_cutoff'),
            'feature_cutoff_utc': None, 'cohort': UNRESOLVED, 'timing_basis': BASIS,
            'classification': 'QUARANTINED' if any(x in flags for x in ('AMBIGUOUS_CONFIGURATION_VERSION','REFERENCE_PRICE_AFTER_OBSERVATION')) else 'UNMEASURABLE', 'reason_codes': sorted(flags),
            'cluster_id': cluster(obs), 'cluster_method_version': METHOD,
            'direction': 'LONG', 'signal_type': 'RECORDED_OBSERVATION', 'event_type': row.get('opportunity_family'),
            'decision_status': row.get('recommendation'),
            'quality_flags': row.get('warnings', []), 'regime_version': None,
            'features': {'values': values, 'available_at_utc': None, 'cutoff_utc': None,
                         'missing': [k for k,v in values.items() if v is None],
                         'usage': 'DESCRIPTIVE_ONLY_TEMPORAL_LINEAGE_UNVERIFIED'},
            'regime': {'values': {}, 'available_at_utc': None, 'cutoff_utc': None, 'missing': ['HISTORICAL_REGIME']},
            'research_uses': {'inventory': True, 'recorded_component_description': bool(components),
                              'versioned_strategy_evidence': False, 'cc_outcomes': False},
            'event_study_levels': {},
            'provenance': {'source_pipeline': row.get('methodology_version', 'TACTICAL_OUTCOME_TRACKER'),
                           'source_digests': [digest(row)], 'transformation_version': VERSION,
                           'retrieved_at_utc': None}, 'source_record': row}


def prospective(*, source_event_id, asset, pair, strategy_id, strategy_version,
                configuration_version, observation_time, reference_close, reference_price,
                features, regime, provenance, levels=None, direction='LONG'):
    observation_time, reference_close = stamp(observation_time), stamp(reference_close)
    # Identity deliberately excludes rerun wall clock. First creation is immutable.
    identity = [source_event_id, strategy_id, strategy_version, configuration_version, BASIS]
    result = {'schema_version': VERSION, 'signal_id': 'v2p_' + digest(identity)[:32],
              'source_event_id': source_event_id, 'asset': asset, 'pair': pair,
              'strategy_id': strategy_id, 'strategy_version': strategy_version,
              'configuration_version': configuration_version, 'observation_timestamp_utc': observation_time,
              'reference_candle_close_utc': reference_close, 'reference_price_timestamp_utc': reference_close,
              'reference_price': reference_price, 'market_data_cutoff_utc': reference_close,
              'feature_cutoff_utc': features['cutoff_utc'], 'cohort': FORWARD, 'timing_basis': BASIS,
              'classification': 'MEASURABLE', 'reason_codes': [], 'direction': direction,
              'cluster_id': cluster(observation_time), 'cluster_method_version': METHOD,
              'signal_type': 'QUALIFYING_RESEARCH_SETUP', 'event_type': 'CLOSED_CANDLE_REFERENCE_EVENT',
              'decision_status': 'RESEARCH_ONLY', 'quality_flags': [],
              'features': features, 'regime': regime, 'regime_version': regime['version'],
              'event_study_levels': levels or {}, 'provenance': provenance,
              'research_uses': {'inventory': True, 'recorded_component_description': True,
                                'versioned_strategy_evidence': True, 'cc_outcomes': True}}
    return validate(result, prospective=True)
