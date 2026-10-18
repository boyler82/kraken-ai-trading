"""Versioned contracts; timestamps are never inferred or silently localized."""
from __future__ import annotations
import hashlib
import json
import math
from datetime import datetime, timezone

VERSION = '1.0.0'
BASIS = 'CLOSED_CANDLE_REFERENCE'
HORIZONS = (1, 4, 12, 24, 72)
FORWARD = 'FORWARD_PROSPECTIVE_CLOSED_CANDLE'
HISTORICAL = 'HISTORICAL_CLOSED_CANDLE_RECONSTRUCTED'
UNRESOLVED = 'HISTORICAL_RECONSTRUCTED'
FEATURES = ('return_1h', 'return_4h', 'return_24h', 'return_7d',
            'momentum_acceleration', 'rs_btc', 'rs_percentile', 'rs_acceleration',
            'volume_z', 'volume_acceleration', 'realized_volatility',
            'volatility_expansion', 'breakout_distance', 'range_position',
            'ema20_distance', 'quote_notional')

def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)

def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()

def strict_loads(text):
    def invalid(x):
        raise ValueError('NONFINITE_JSON:' + x)
    def pairs(items):
        result = {}
        for k, v in items:
            if k in result:
                raise ValueError('DUPLICATE_JSON_KEY:' + k)
            result[k] = v
        return result
    return json.loads(text, parse_constant=invalid, object_pairs_hook=pairs)

def utc(value):
    if not isinstance(value, str):
        raise ValueError('MISSING_TIMESTAMP')
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError('AMBIGUOUS_TIMEZONE')
    return parsed.astimezone(timezone.utc)

def stamp(value):
    return utc(value).isoformat()

def positive(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value > 0

def validate(signal, prospective=False):
    canonical(signal)
    required = ('signal_id', 'schema_version', 'source_event_id', 'asset', 'strategy_id',
                'cohort', 'timing_basis', 'provenance', 'features', 'regime',
                'classification', 'reason_codes', 'observation_timestamp_utc')
    if any(k not in signal for k in required):
        raise ValueError('MISSING_SIGNAL_FIELDS')
    if signal['schema_version'] != VERSION or signal['classification'] not in ('MEASURABLE', 'UNMEASURABLE', 'QUARANTINED'):
        raise ValueError('INVALID_SCHEMA_OR_CLASSIFICATION')
    if signal['cohort'] not in (FORWARD, HISTORICAL, UNRESOLVED):
        raise ValueError('INVALID_COHORT')
    if signal['timing_basis'] not in (BASIS, 'OBSERVATION_TIME_EXACT'):
        raise ValueError('INVALID_TIMING_BASIS')
    if not isinstance(signal['asset'],str) or not signal['asset'].strip():
        raise ValueError('INVALID_ASSET')
    if not isinstance(signal['provenance'],dict) or not isinstance(signal['reason_codes'],list):
        raise ValueError('INVALID_SIGNAL_SHAPE')
    if prospective or signal['cohort'] == FORWARD:
        for key in ('pair', 'strategy_version', 'configuration_version', 'reference_candle_close_utc',
                    'reference_price_timestamp_utc', 'market_data_cutoff_utc', 'feature_cutoff_utc',
                    'regime_version', 'cluster_id', 'cluster_method_version'):
            if not signal.get(key):
                raise ValueError('MISSING_' + key.upper())
        obs = utc(signal['observation_timestamp_utc'])
        if signal['classification']!='MEASURABLE':
            raise ValueError('INVALID_PROSPECTIVE_CLASSIFICATION')
        if signal['timing_basis']!=BASIS:
            raise ValueError('PROSPECTIVE_BASIS_NOT_IMPLEMENTED')
        for key in ('reference_candle_close_utc', 'reference_price_timestamp_utc',
                    'market_data_cutoff_utc', 'feature_cutoff_utc'):
            if utc(signal[key]) > obs:
                raise ValueError('FUTURE_' + key.upper())
        if signal['reference_price_timestamp_utc'] != signal['reference_candle_close_utc']:
            raise ValueError('REFERENCE_IS_NOT_CANDLE_CLOSE')
        if utc(signal['reference_candle_close_utc']) > utc(signal['market_data_cutoff_utc']):
            raise ValueError('REFERENCE_AFTER_MARKET_CUTOFF')
        if utc(signal['feature_cutoff_utc']) > utc(signal['market_data_cutoff_utc']):
            raise ValueError('FEATURE_AFTER_MARKET_CUTOFF')
        if not positive(signal.get('reference_price')):
            raise ValueError('MISSING_REFERENCE_PRICE')
        if not signal['provenance'].get('source_digests'):
            raise ValueError('MISSING_PROVENANCE')
        for key in ('available_at_utc', 'cutoff_utc'):
            if utc(signal['features'][key]) > obs or utc(signal['regime'][key]) > obs:
                raise ValueError('FUTURE_SNAPSHOT')
        for name,value in signal['features']['values'].items():
            if name not in FEATURES or (value is not None and (not isinstance(value,(int,float)) or isinstance(value,bool) or not math.isfinite(value))):
                raise ValueError('INVALID_FEATURE_VALUE:'+name)
        for snapshot in ('features', 'regime'):
            if utc(signal[snapshot]['cutoff_utc']) > utc(signal['market_data_cutoff_utc']):
                raise ValueError('SNAPSHOT_AFTER_CUTOFF')
        if signal.get('direction') not in ('LONG', 'SHORT'):
            raise ValueError('INVALID_DIRECTION')
    return signal
