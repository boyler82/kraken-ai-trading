"""Immutable asset evidence with independently available benchmark evidence.

Legacy outcome bytes are authoritative version-zero asset records. Projection
removes only benchmark fields; neither enrichment nor reporting rewrites them.
"""
from copy import deepcopy
from datetime import timedelta
from .schemas import BASIS, HORIZONS, canonical, digest, stamp, utc
from .outcomes import at_close, window

MODEL = 'ASSET_BENCHMARK_V1'
BENCHMARK_VERSION = 'LONG_BTC_CC_V1'
BENCHMARK_FIELDS = {'btc_return_pct', 'btc_relative_return_pct', 'btc_data_digest',
                    'btc_relative_definition'}
AVAILABILITY_FIELDS = {'asset_state', 'asset_available_as_of', 'lifecycle_model_version'}


def asset_state(row):
    if row['status'] == 'COMPLETE':
        return 'ASSET_COMPLETE'
    if row['status'] == 'PENDING':
        return 'ASSET_PENDING'
    return 'ASSET_UNMEASURABLE'


def asset_facts(row):
    result = {k: deepcopy(v) for k, v in row.items()
              if k not in BENCHMARK_FIELDS | AVAILABILITY_FIELDS}
    result['reason_codes'] = [x for x in result['reason_codes']
                              if x != 'BTC_MATCHED_WINDOW_UNAVAILABLE']
    return result


def benchmark(signal, asset, bars, as_of):
    """No network or writes. Availability is when this calculation was possible."""
    ref = asset.get('reference_candle_close_utc')
    end = asset.get('endpoint_utc')
    row = {'lifecycle_model_version': MODEL, 'calculation_version': BENCHMARK_VERSION,
           'observation_id': signal['signal_id'], 'timing_basis': asset['timing_basis'],
           'horizon_hours': asset['horizon_hours'], 'benchmark_symbol': 'XBTUSD',
           'benchmark_reference_timestamp': ref, 'benchmark_endpoint_timestamp': end,
           'benchmark_return_pct': None, 'btc_relative_return_pct': None,
           'benchmark_data_digest': None, 'available_as_of': stamp(as_of),
           'state': 'BENCHMARK_PENDING_REFERENCE_DATA', 'reason_codes': [],
           'calculation_definition': 'DIRECTIONAL_ASSET_RETURN_MINUS_LONG_BTC_RETURN',
           'asset_measurement_digest': None,
           'source': {'provider': 'KRAKEN_PUBLIC_OHLC',
                      'path': 'DATASETS/market_intraday_weekly/XBTUSD_1H.csv',
                      'interval_seconds': 3600, 'timestamp_semantics': 'CANDLE_START'}}
    if (signal['classification'] != 'MEASURABLE' or not ref or not end
            or utc(end) <= utc(signal['observation_timestamp_utc'])):
        row.update(state='BENCHMARK_UNMEASURABLE', reason_codes=['INELIGIBLE_REFERENCE_WINDOW'])
        return row
    if not ref or not end or utc(end) > utc(as_of):
        row['reason_codes'] = ['HORIZON_NOT_MATURE']
        return row
    origin = at_close(bars, utc(ref))
    selected, error = window(bars, utc(ref), utc(end))
    if origin is None or error:
        row['reason_codes'] = [error or 'BENCHMARK_REFERENCE_CANDLE_UNAVAILABLE']
        return row
    row.update(state='BENCHMARK_COMPLETE',
               benchmark_return_pct=(selected[-1]['close'] / origin['close'] - 1) * 100,
               benchmark_data_digest=digest([origin] + selected))
    row['source']['reference_and_window'] = [origin] + selected
    if asset_state(asset) == 'ASSET_COMPLETE':
        row['asset_measurement_digest'] = digest(asset_facts(asset))
        row['btc_relative_return_pct'] = asset['return_pct'] - row['benchmark_return_pct']
    return row


def preflight(signals, bars, as_of):
    """Production requires every eligible hourly benchmark window, fail closed."""
    latest = utc(as_of).replace(minute=0, second=0, microsecond=0)
    if at_close(bars, latest) is None:
        raise ValueError('BTC_HOURLY_PREFLIGHT_FAILED:LATEST_CLOSED_CANDLE_UNAVAILABLE')
    windows = set()
    for s in signals:
        if s['classification'] != 'MEASURABLE' or s['timing_basis'] != BASIS:
            continue
        ref = utc(s['reference_candle_close_utc'])
        for h in HORIZONS:
            end = ref + timedelta(hours=h)
            if utc(s['observation_timestamp_utc']) < end <= utc(as_of):
                windows.add((ref, end))
    for ref, end in sorted(windows):
        _, error = window(bars, ref, end)
        if at_close(bars, ref) is None or error:
            raise ValueError(f'BTC_HOURLY_PREFLIGHT_FAILED:{ref.isoformat()}:{end.isoformat()}:{error or "MISSING_REFERENCE"}')
    return {'status': 'OK', 'required_windows': len(windows),
            'latest_closed_candle': latest.isoformat(), 'source': 'XBTUSD_1H.csv'}


def combined(asset, enrichment, as_of, legacy_availability=None):
    """Read-only as-known view; never count a measurement version as an event."""
    row = asset_facts(asset)
    state = asset_state(asset)
    availability = asset.get('asset_available_as_of') or legacy_availability
    if state == 'ASSET_COMPLETE' and (not availability or utc(availability) > utc(as_of)):
        # Do not leak future asset measurements into an earlier evidence view.
        return None
    row.update(lifecycle_model_version=MODEL, asset_state=state,
               asset_available_as_of=availability,
               asset_storage_version=asset.get('lifecycle_model_version', 'LEGACY_V0'),
               benchmark_state='BENCHMARK_PENDING_REFERENCE_DATA',
               benchmark_available_as_of=None, btc_return_pct=None,
               btc_relative_return_pct=None)
    if enrichment is not None:
        if utc(enrichment['available_as_of']) > utc(as_of):
            raise ValueError('FUTURE_BENCHMARK_VIEW')
        row['benchmark_state'] = enrichment['state']
        row['benchmark_available_as_of'] = enrichment['available_as_of']
        row['benchmark_evidence_id'] = enrichment['evidence_id']
        if enrichment['state'] == 'BENCHMARK_COMPLETE':
            row['btc_return_pct'] = enrichment['benchmark_return_pct']
            if state == 'ASSET_COMPLETE' and enrichment['asset_measurement_digest'] is not None:
                if enrichment['asset_measurement_digest'] != digest(asset_facts(asset)):
                    raise ValueError('BENCHMARK_ASSET_LINK_CONFLICT')
                row['btc_relative_return_pct'] = enrichment['btc_relative_return_pct']
        row['reason_codes'] += enrichment['reason_codes']
    elif state == 'ASSET_UNMEASURABLE':
        row['benchmark_state'] = 'BENCHMARK_UNMEASURABLE'
    row['status'] = ('UNMEASURABLE' if state == 'ASSET_UNMEASURABLE' else
                     'PENDING' if state == 'ASSET_PENDING' else
                     'COMPLETE' if row['benchmark_state'] == 'BENCHMARK_COMPLETE' else
                     'PARTIALLY_MEASURABLE')
    row['data_completeness'] = row['status'] == 'COMPLETE'
    row['asset_data_completeness'] = asset.get('data_completeness', False)
    return row
