"""Closed-candle-reference event studies, never trade or observation-time P&L."""
from __future__ import annotations
import csv
from datetime import timedelta
from pathlib import Path
from .schemas import BASIS, HORIZONS, digest, positive, utc

def load_bars(path, interval_seconds=3600):
    """CSV timestamps are documented candle STARTS; preserve arbitrary resolution."""
    if not Path(path).exists():
        return []
    with Path(path).open() as f:
        rows = list(csv.DictReader(f))
    return [{'start': row['timestamp'],
             'end': (utc(row['timestamp']) + timedelta(seconds=interval_seconds)).isoformat(),
             **{k: float(row[k]) for k in ('open', 'high', 'low', 'close', 'volume')}} for row in rows]

def valid_bar(b):
    import math
    return (utc(b['start']) < utc(b['end']) and
            all(positive(b[k]) for k in ('open', 'high', 'low', 'close')) and
            b['low'] <= min(b['open'], b['close']) <= max(b['open'], b['close']) <= b['high'] and
            math.isfinite(b['volume']) and b['volume'] >= 0)

def window(bars, start, end):
    selected = sorted([b for b in bars if utc(b['end']) > start and utc(b['start']) < end], key=lambda b: utc(b['start']))
    cursor = start
    for b in selected:
        if not valid_bar(b):
            return [], 'INVALID_OHLCV'
        if utc(b['start']) != cursor or utc(b['end']) > end:
            return [], 'MISSING_DUPLICATE_OR_MISALIGNED_CANDLES'
        cursor = utc(b['end'])
    return (selected, None) if cursor == end else ([], 'INSUFFICIENT_FUTURE_DATA')

def at_close(bars, when):
    matching = [b for b in bars if utc(b['end']) == when]
    if len(matching) != 1 or not valid_bar(matching[0]):
        return None
    return matching[0]

def outcome(signal, hours, bars, btc_bars, as_of):
    if hours not in HORIZONS:
        raise ValueError('UNSUPPORTED_HORIZON')
    row = {'schema_version': '1.0.0', 'signal_id': signal['signal_id'],
           'timing_basis': signal['timing_basis'], 'cohort': signal['cohort'],
           'horizon_hours': hours, 'metric_name': f'return_cc_{hours}h',
           'status': 'UNMEASURABLE', 'reason_codes': [], 'return_pct': None,
           'btc_return_pct': None, 'btc_relative_return_pct': None,
           'mfe_pct': None, 'mae_pct': None, 'target_hit': None, 'invalidation_hit': None,
           'first_touch': None, 'time_to_target_hours_bounds': None,
           'time_to_invalidation_hours_bounds': None, 'data_completeness': False,
           'execution_assumed': False}
    if signal['timing_basis'] != BASIS:
        row['reason_codes'] = ['BASIS_NOT_IMPLEMENTED']; return row
    if signal['classification'] != 'MEASURABLE':
        row['reason_codes'] = signal['reason_codes']; return row
    ref = utc(signal['reference_candle_close_utc'])
    obs = utc(signal['observation_timestamp_utc'])
    due = ref + timedelta(hours=hours)
    row.update(reference_candle_close_utc=ref.isoformat(), endpoint_utc=due.isoformat(),
               observation_timestamp_utc=obs.isoformat(),
               pre_creation_path_included=obs > ref)
    if due <= obs:
        row['status'] = 'INELIGIBLE_PRE_CREATION_HORIZON'
        row['reason_codes'] = ['INELIGIBLE_PRE_CREATION_HORIZON']; return row
    if utc(signal['reference_price_timestamp_utc']) > obs:
        row['reason_codes'] = ['REFERENCE_PRICE_AFTER_OBSERVATION']; return row
    if due > utc(as_of):
        row['status'] = 'PENDING'; row['reason_codes'] = ['INSUFFICIENT_FUTURE_DATA']; return row
    origin = at_close(bars, ref)
    if origin is None or abs(origin['close'] - signal['reference_price']) > max(1e-12, abs(signal['reference_price']) * 1e-10):
        row['reason_codes'] = ['REFERENCE_CANDLE_MISSING_OR_PRICE_CONFLICT']; return row
    selected, error = window(bars, ref, due)
    if error:
        row['reason_codes'] = [error]; return row
    sign = 1 if signal.get('direction', 'LONG') == 'LONG' else -1
    price = signal['reference_price']
    ret = sign * (selected[-1]['close'] / price - 1) * 100
    high = max([price] + [b['high'] for b in selected]); low = min([price] + [b['low'] for b in selected])
    row.update(status='COMPLETE', return_pct=ret, data_completeness=True,
               mfe_pct=(high / price - 1) * 100 if sign == 1 else (1 - low / price) * 100,
               mae_pct=(low / price - 1) * 100 if sign == 1 else (1 - high / price) * 100,
               candle_count=len(selected), data_digest=digest([origin] + selected))
    # Reference-level touch study only: levels are not presumed executed orders.
    levels = signal.get('event_study_levels') or {}
    target, stop = levels.get('target'), levels.get('invalidation')
    valid = positive(target) and positive(stop) and ((stop < price < target) if sign == 1 else (target < price < stop))
    if valid:
        def hit(level, favorable):
            return next((b for b in selected if (b['high'] >= level if (sign == 1) == favorable else b['low'] <= level)), None)
        target_bar, stop_bar = hit(target, True), hit(stop, False)
        row.update(target_hit=target_bar is not None, invalidation_hit=stop_bar is not None)
        for name, b in [('target', target_bar), ('invalidation', stop_bar)]:
            if b:
                row[f'time_to_{name}_hours_bounds'] = [(utc(b[k]) - ref).total_seconds()/3600 for k in ('start', 'end')]
        if target_bar and stop_bar:
            row['first_touch'] = ('AMBIGUOUS_SAME_CANDLE' if target_bar['start'] == stop_bar['start'] else
                                  'TARGET' if utc(target_bar['start']) < utc(stop_bar['start']) else 'INVALIDATION')
        else:
            row['first_touch'] = 'TARGET' if target_bar else 'INVALIDATION' if stop_bar else 'NEITHER'
    else:
        row['reason_codes'].append('LEVELS_UNAVAILABLE_OR_SEMANTICALLY_INVALID')
    btc_origin = at_close(btc_bars, ref)
    btc_window, btc_error = window(btc_bars, ref, due)
    if btc_origin and not btc_error:
        btc_return = (btc_window[-1]['close']/btc_origin['close'] - 1)*100
        row.update(btc_return_pct=btc_return, btc_relative_return_pct=ret - btc_return,
                   btc_data_digest=digest([btc_origin] + btc_window),
                   btc_relative_definition='DIRECTIONAL_ASSET_RETURN_MINUS_LONG_BTC_RETURN')
    else:
        row['reason_codes'].append('BTC_MATCHED_WINDOW_UNAVAILABLE')
    return row
