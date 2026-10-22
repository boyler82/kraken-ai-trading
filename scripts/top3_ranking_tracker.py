"""Prospective append-only ranking observations. No ranking or execution logic."""
from __future__ import annotations

import hashlib
import io
import json
import math
import sqlite3
from contextlib import closing
from datetime import timedelta
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
STORE = ROOT / 'DATASETS/TOP3_RANKING_OUTCOMES/tracker.sqlite'
REPORT = ROOT / 'DAILY_REPORTS/TOP3_RANKING_OUTCOMES/latest_summary.json'
TYPES = ('CONTINUATION', 'REVERSAL', 'RELATIVE_STRENGTH')
HOUR = timedelta(hours=1)


def utc(value):
    t = pd.Timestamp(value)
    if t.tzinfo is None:
        raise ValueError('Timezone-aware timestamp required')
    return t.tz_convert('UTC')


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def ident(*parts):
    return hashlib.sha256(encode(parts).encode()).hexdigest()


def connect(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=30)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    db.execute('PRAGMA synchronous=FULL')
    db.executescript('''
      CREATE TABLE IF NOT EXISTS scans (
        id TEXT PRIMARY KEY, observed_at TEXT NOT NULL, ranking_type TEXT NOT NULL,
        payload TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS observations (
        id TEXT PRIMARY KEY, scan_id TEXT NOT NULL REFERENCES scans(id),
        ranking_type TEXT NOT NULL, rank INTEGER NOT NULL CHECK(rank BETWEEN 1 AND 3),
        regime TEXT NOT NULL, payload TEXT NOT NULL, UNIQUE(scan_id,rank));
      CREATE TABLE IF NOT EXISTS outcomes (
        observation_id TEXT NOT NULL REFERENCES observations(id),
        kind TEXT NOT NULL CHECK(kind IN ('PRICE_24H','NEXT_DAY_RANK')),
        payload TEXT NOT NULL, PRIMARY KEY(observation_id,kind));
      CREATE INDEX IF NOT EXISTS scan_time ON scans(ranking_type,observed_at);
    ''')
    for table in ('scans', 'observations', 'outcomes'):
        for action in ('UPDATE', 'DELETE'):
            db.execute(f"CREATE TRIGGER IF NOT EXISTS immutable_{table}_{action} BEFORE {action} ON {table} BEGIN SELECT RAISE(ABORT,'append-only tracker'); END")
        key = 'observation_id=NEW.observation_id AND kind=NEW.kind' if table=='outcomes' else 'id=NEW.id'
        db.execute(f"CREATE TRIGGER IF NOT EXISTS immutable_{table}_replace BEFORE INSERT ON {table} WHEN EXISTS(SELECT 1 FROM {table} WHERE {key}) BEGIN SELECT RAISE(ABORT,'append-only duplicate'); END")
    return db


class HourlyArchive:
    """Read existing local USD hourly bars; reject gaps/invalid bars, never fill."""
    def __init__(self, root=ROOT):
        self.root = Path(root)
        self.cache = {}

    def bars(self, asset, pair):
        key = (asset, pair)
        if key not in self.cache:
            if not pair or Path(pair).name != pair or not pair.endswith('USD'):
                raise ValueError(f'Unsupported/missing hourly USD pair: {pair}')
            path = self.root / f'DATASETS/market_intraday_weekly/{pair}_1H.csv'
            raw = path.read_bytes()
            d = pd.read_csv(io.BytesIO(raw))
            d['timestamp'] = pd.to_datetime(d.timestamp, utc=True)
            cols = ['open', 'high', 'low', 'close', 'volume']
            d[cols] = d[cols].apply(pd.to_numeric, errors='raise')
            invalid = (d.timestamp.duplicated(keep=False) | (d.timestamp != d.timestamp.dt.floor('h'))
                       | ~d[cols].apply(lambda s: s.map(math.isfinite)).all(axis=1)
                       | (d[cols[:4]] <= 0).any(axis=1) | (d.volume < 0)
                       | (d.high < d[['open','close','low']].max(axis=1))
                       | (d.low > d[['open','close','high']].min(axis=1)))
            # Reject all copies of bad timestamps, leaving missing hours visible.
            self.cache[key] = (d.loc[~invalid].set_index('timestamp').sort_index(),
                               str(path.relative_to(self.root)), hashlib.sha256(raw).hexdigest())
        return self.cache[key]

    def reference(self, asset, pair, boundary):
        d, path, digest = self.bars(asset, pair)
        price = float(d.at[boundary-HOUR, 'close'])
        return price, {'path': path, 'sha256': digest, 'candle_start': (boundary-HOUR).isoformat()}

    def window(self, asset, pair, boundary):
        d, path, digest = self.bars(asset, pair)
        expected = pd.date_range(boundary, periods=24, freq='h')
        w = d.reindex(expected)
        if w[['open','high','low','close','volume']].isna().any().any():
            raise ValueError('Incomplete 24h hourly window')
        return w, {'path': path, 'sha256': digest}


def capture(db, scan_key, observed_at, regime, rankings, archive):
    """rankings maps type to None (unavailable) or existing ordered Top-10 rows.

    Rows: asset, pair, rank. Missing prices remain explicit nulls forever.
    scan_key is the upstream packet identity, stable across retries.
    """
    now = utc(observed_at)
    boundary = now.floor('h')
    warnings = []
    with db:
        db.execute('BEGIN IMMEDIATE')
        for kind in TYPES:
            sid = ident(scan_key, kind)
            if db.execute('SELECT 1 FROM scans WHERE id=?', (sid,)).fetchone():
                continue
            supplied = rankings.get(kind)
            available = supplied is not None
            rows = list(supplied or [])[:10]
            assets = [r['asset'] for r in rows]
            ranks = [r['rank'] for r in rows]
            if len(set(assets)) != len(assets) or ranks != list(range(1, len(rows)+1)):
                raise ValueError(f'Invalid published order: {kind}')
            payload = dict(scan_key=scan_key, observed_at=now.isoformat(), ranking_type=kind,
                           available=available, top10=rows, regime=regime)
            db.execute('INSERT INTO scans VALUES (?,?,?,?)', (sid, now.isoformat(), kind, encode(payload)))
            if not available:
                warnings.append(f'{kind}: RANKING_UNAVAILABLE')
            for item in rows[:3]:
                refs = {}; price = btc = None
                for name, asset, pair in [('asset', item['asset'], item.get('pair')), ('btc', 'BTC', 'XBTUSD')]:
                    try:
                        val, source = archive.reference(asset, pair, boundary)
                        refs[name] = source
                        if name == 'asset': price = val
                        else: btc = val
                    except (OSError, KeyError, ValueError) as exc:
                        warnings.append(f'{kind}/{item["asset"]}: {name.upper()}_REFERENCE_UNAVAILABLE: {exc}')
                oid = ident(sid, item['rank'], item['asset'])
                obs = dict(id=oid, scan_id=sid, observed_at=now.isoformat(), ranking_type=kind,
                           rank=item['rank'], asset=item['asset'], pair=item.get('pair'), regime=regime,
                           reference_price=price, btc_reference_price=btc, price_timestamp=boundary.isoformat(),
                           sources=refs, trading='DISABLED', schema_version=1)
                db.execute('INSERT INTO observations VALUES (?,?,?,?,?,?)',
                           (oid, sid, kind, item['rank'], regime, encode(obs)))
    return warnings


def mature(db, now, archive):
    now = utc(now)
    warnings = []
    with db:
        db.execute('BEGIN IMMEDIATE')
        for row in db.execute('SELECT id,payload FROM observations').fetchall():
            obs = json.loads(row['payload']); oid = row['id']
            have = {r[0] for r in db.execute('SELECT kind FROM outcomes WHERE observation_id=?', (oid,))}
            boundary = utc(obs['price_timestamp']); target = boundary + timedelta(hours=24)
            if 'PRICE_24H' not in have and target <= now:
                if obs['reference_price'] is None or obs['btc_reference_price'] is None:
                    warnings.append(f'{oid}: IMMUTABLE_REFERENCE_UNAVAILABLE')
                else:
                    try:
                        w, source = archive.window(obs['asset'], obs['pair'], boundary)
                        b, bsource = archive.window('BTC', 'XBTUSD', boundary)
                        price = obs['reference_price']; btc = obs['btc_reference_price']
                        a_return = (float(w.close.iloc[-1])/price-1)*100
                        b_return = (float(b.close.iloc[-1])/btc-1)*100
                        result = dict(measured_at=now.isoformat(), target_timestamp=target.isoformat(),
                                      return_24h_pct=a_return, btc_return_24h_pct=b_return,
                                      btc_relative_return_24h_pct=((1+a_return/100)/(1+b_return/100)-1)*100,
                                      mfe_pct=(float(w.high.max())/price-1)*100,
                                      mae_pct=(float(w.low.min())/price-1)*100,
                                      sources={'asset': source, 'btc': bsource}, cost_basis='GROSS_NO_TRADE_SIMULATED')
                        db.execute('INSERT INTO outcomes VALUES (?,?,?)', (oid, 'PRICE_24H', encode(result)))
                    except (OSError, KeyError, ValueError) as exc:
                        warnings.append(f'{oid}: PRICE_WINDOW_PENDING: {exc}')
            if 'NEXT_DAY_RANK' not in have:
                day = (utc(obs['observed_at']).normalize()+timedelta(days=1)).date()
                candidates = db.execute('SELECT id,payload FROM scans WHERE ranking_type=? ORDER BY observed_at,id', (obs['ranking_type'],)).fetchall()
                for candidate in candidates:
                    scan = json.loads(candidate['payload']); stamp = utc(scan['observed_at'])
                    if stamp.date() != day or stamp > now or not scan['available']:
                        continue
                    rank = next((r['rank'] for r in scan['top10'] if r['asset']==obs['asset']), None)
                    result = dict(measured_at=now.isoformat(), next_scan_id=candidate['id'], next_scan_timestamp=stamp.isoformat(),
                                  next_rank=rank, remained_top3=rank is not None and rank<=3,
                                  remained_top10=rank is not None, rank_change=obs['rank']-rank if rank is not None else None,
                                  rank_change_semantics='PREVIOUS_MINUS_NEXT_POSITIVE_IS_IMPROVEMENT',
                                  rank_censored=rank is None, membership_semantics='NEXT_UTC_DATE_FIRST_AVAILABLE_SCAN_NOT_CONTINUOUS')
                    db.execute('INSERT INTO outcomes VALUES (?,?,?)', (oid, 'NEXT_DAY_RANK', encode(result)))
                    break
    return warnings


def aggregate(db):
    groups = {}
    for row in db.execute('SELECT * FROM observations'):
        obs = json.loads(row['payload'])
        events = {r['kind']: json.loads(r['payload']) for r in db.execute('SELECT kind,payload FROM outcomes WHERE observation_id=?', (row['id'],))}
        keys = [('TYPE', obs['ranking_type'], None, None), ('TYPE_RANK', obs['ranking_type'], obs['rank'], None),
                ('TYPE_REGIME', obs['ranking_type'], None, obs['regime']), ('TYPE_RANK_REGIME', obs['ranking_type'], obs['rank'], obs['regime'])]
        for key in keys:
            groups.setdefault(key, []).append((obs, events))
    out = []
    for (level, kind, rank, regime), entries in groups.items():
        prices = [e['PRICE_24H'] for _, e in entries if 'PRICE_24H' in e]
        ranks = [e['NEXT_DAY_RANK'] for _, e in entries if 'NEXT_DAY_RANK' in e]
        mean = lambda xs: sum(xs)/len(xs) if xs else None
        out.append(dict(level=level, ranking_type=kind, rank=rank, regime=regime, observations=len(entries),
                        price_completed=len(prices), rank_completed=len(ranks), price_pending=len(entries)-len(prices),
                        rank_pending=len(entries)-len(ranks), scans=len({o['scan_id'] for o,_ in entries}),
                        reference_missing=sum(o['reference_price'] is None or o['btc_reference_price'] is None for o,_ in entries),
                        mean_return_24h_pct=mean([p['return_24h_pct'] for p in prices]),
                        win_rate_pct=mean([100.*(p['return_24h_pct']>0) for p in prices]),
                        mean_btc_return_pct=mean([p['btc_return_24h_pct'] for p in prices]),
                        mean_btc_relative_return_pct=mean([p['btc_relative_return_24h_pct'] for p in prices]),
                        mean_mfe_pct=mean([p['mfe_pct'] for p in prices]), mean_mae_pct=mean([p['mae_pct'] for p in prices]),
                        remained_top3_pct=mean([100.*p['remained_top3'] for p in ranks]),
                        remained_top10_pct=mean([100.*p['remained_top10'] for p in ranks]),
                        rank_change_known=sum(p['rank_change'] is not None for p in ranks),
                        mean_rank_change=mean([p['rank_change'] for p in ranks if p['rank_change'] is not None])))
    return dict(schema_version=1, trading='DISABLED', groups=out,
                warnings=['GROSS_RETURNS_NOT_EXECUTED_TRADES', 'OVERLAPPING_SCANS_AND_ASSETS_NOT_INDEPENDENT',
                          'RANK_PERSISTENCE_IS_NEXT_DAY_ENDPOINT_ONLY', 'NO_HISTORICAL_BACKFILL'])


def track_daily(chief, opportunity, relative, now, path=STORE, report=REPORT, archive=None):
    """Consume published output only, preserving upstream order and rank numbers."""
    now = utc(now)
    generated = utc(chief['generated_at_utc'])
    if not timedelta(0) <= now-generated <= timedelta(hours=2):
        raise ValueError('Chief packet stale or from future')
    pair_map = {c['asset']: c.get('identity', {}).get('kraken_pair') for c in chief.get('candidates', [])}
    def existing(rows):
        return [dict(asset=r['asset'], rank=int(r['rank']), pair=r.get('pair') or pair_map.get(r['asset'])) for r in rows[:10]]
    rs = None
    if relative is not None:
        try:
            stamp = utc(relative['generated_at_utc'])
            if relative.get('freshness') == 'FRESH' and timedelta(0) <= now-stamp <= timedelta(hours=2):
                rs = existing(relative['candidates'])
        except (KeyError, ValueError, TypeError):
            pass  # Preserve other rankings while explicitly marking RS unavailable.
    rankings = {'CONTINUATION': existing(opportunity['continuation_watchlist']),
                'REVERSAL': existing(opportunity['reversal_watchlist']), 'RELATIVE_STRENGTH': rs}
    archive = archive or HourlyArchive()
    with closing(connect(path)) as db:
        warnings = capture(db, chief['generated_at_utc'], now, str(chief.get('market_state', {}).get('crypto_regime') or 'UNKNOWN'), rankings, archive)
        warnings += mature(db, now, archive)
        summary = aggregate(db)
        summary['run_warnings'] = warnings
        summary['generated_at_utc'] = now.isoformat()
        from weekly_consolidation_common import atomic_write
        atomic_write(Path(report), json.dumps(summary, indent=2, allow_nan=False)+'\n', backup=False)
    return summary
