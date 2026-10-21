"""Public trade-backed BTC refresh gate; never substitutes a different dataset."""
import csv
import math
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT/'DATASETS/BTC_4H_DONCHIAN_V1/BTCUSD_15m_operational.csv'
REFRESHER = ROOT/'STRATEGIES/btc_4h_donchian_v1/recent_trade_backfill.py'
INTERVAL = 900


def timestamp(value=None):
    when = datetime.now(timezone.utc) if value is None else datetime.fromisoformat(str(value).replace('Z','+00:00'))
    if when.tzinfo is None: raise ValueError('BTC_OPERATIONAL_AMBIGUOUS_TIME')
    return int(when.timestamp())


def read_rows(path):
    with Path(path).open(newline='') as handle:
        return list(csv.DictReader(handle))


def validate(path, as_of, required_start=None):
    rows = read_rows(path)
    if not rows: raise ValueError('BTC_OPERATIONAL_EMPTY')
    times = [int(r['timestamp']) for r in rows]
    end = timestamp(as_of)//INTERVAL*INTERVAL-INTERVAL
    if times != sorted(set(times)) or any(t % INTERVAL for t in times):
        raise ValueError('BTC_OPERATIONAL_TIMESTAMP_ALIGNMENT')
    if times[-1] < end: raise ValueError('BTC_OPERATIONAL_STALE:'+str(times[-1]))
    if times[-1] > end: raise ValueError('BTC_OPERATIONAL_FUTURE_OR_UNCLOSED_CANDLE')
    # A complete last hourly bucket is required by hourly BTC consumers.
    start = min(required_start if required_start is not None else end, end//3600*3600-3600)
    available = set(times)
    if any(t not in available for t in range(start,end+INTERVAL,INTERVAL)):
        raise ValueError('BTC_OPERATIONAL_REFERENCE_WINDOW_GAP')
    for r in rows:
        o,h,l,c,v = (float(r[k]) for k in ('open','high','low','close','volume'))
        if not all(math.isfinite(x) for x in (o,h,l,c,v)) or min(o,h,l,c)<=0 or v<0 or not l<=min(o,c)<=max(o,c)<=h:
            raise ValueError('BTC_OPERATIONAL_INVALID_OHLCV')
    return {'status':'OK','validated_as_of_utc':datetime.fromtimestamp(timestamp(as_of),timezone.utc).isoformat(),'source':str(path),'latest_candle_start_utc':datetime.fromtimestamp(end,timezone.utc).isoformat(),'rows':len(rows)}


def ensure_operational(as_of=None, refresh=True, path=SOURCE, refresher=REFRESHER):
    cutoff = datetime.now(timezone.utc).isoformat() if as_of is None else as_of
    before = read_rows(path)
    last = int(before[-1]['timestamp']) if before else None
    if refresh:
        # Catch up again if a long archive refresh crosses a candle boundary.
        # Never report a stale catch-up as a successful current-data refresh.
        for attempt in range(3):
            tail = read_rows(path)
            current_last = int(tail[-1]['timestamp']) if tail else None
            days = max(1,math.ceil((timestamp(cutoff)-(current_last or timestamp(cutoff)))/86400)+1)
            result = subprocess.run([sys.executable,str(refresher),'--incremental','--days',str(days)],cwd=ROOT)
            if result.returncode: raise ValueError('BTC_OPERATIONAL_REFRESH_FAILED:'+str(result.returncode))
            cutoff = datetime.now(timezone.utc).isoformat()
            updated = read_rows(path)
            latest = int(updated[-1]['timestamp']) if updated else -1
            if latest >= timestamp(cutoff)//INTERVAL*INTERVAL-INTERVAL:
                break
            if current_last is not None and latest <= current_last:
                raise ValueError('BTC_OPERATIONAL_REFRESH_NO_PROGRESS')
    result = validate(path,cutoff,required_start=last)
    after = {r['timestamp']:r for r in read_rows(path)}
    if any(after.get(r['timestamp'])!=r for r in before):
        raise ValueError('BTC_OPERATIONAL_EXISTING_CANDLE_CHANGED')
    return result
