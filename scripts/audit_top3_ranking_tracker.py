"""Read-only Top-3 ledger audit. Never captures scans or repairs frozen prices."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sqlite3
from collections import Counter
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from top3_ranking_tracker import ROOT, STORE, HourlyArchive, aggregate, encode, price_diagnostics, utc


def table_hash(db, table):
    rows = sorted(tuple(r) for r in db.execute(f'SELECT * FROM {table}'))
    return hashlib.sha256(encode(rows).encode()).hexdigest()


def audit(store, as_of, root=ROOT):
    with closing(sqlite3.connect(Path(store).resolve().as_uri()+'?mode=ro', uri=True)) as db:
        db.row_factory = sqlite3.Row
        db.execute('BEGIN')  # Consistent read snapshot, including aggregates/hashes.
        rows = price_diagnostics(db, as_of, HourlyArchive(root))
        groups = aggregate(db, as_of)['groups']
        totals = {key: sum(g[key] for g in groups if g['level'] == 'TYPE') for key in
                  ('observations', 'price_completed', 'price_pending', 'reference_missing',
                   'price_not_yet_mature', 'price_mature_reference_missing', 'price_mature_window_pending')}
        return dict(as_of=utc(as_of).isoformat(), inspected_at=datetime.now(timezone.utc).isoformat(),
                    trading='DISABLED', policy='READ_ONLY_NO_HISTORICAL_REFERENCE_BACKFILL',
                    totals=totals, statuses=dict(Counter(r['status'] for r in rows)),
                    table_hashes={t: table_hash(db, t) for t in ('scans', 'observations', 'outcomes')},
                    groups=groups, observations=rows)


def write_audit(report, prefix):
    prefix = Path(prefix)
    prefix.parent.mkdir(parents=True, exist_ok=True)
    prefix.with_suffix('.json').write_text(json.dumps(report, indent=2, allow_nan=False)+'\n')
    fields = ['observation_id', 'scan_utc', 'ranking', 'rank', 'asset', 't0_utc', 'target_utc',
              'mature', 'scan_24h_timestamp', 'scan_24h_elapsed', 'status', 'frozen_asset_t0', 'frozen_btc_t0', 'local_asset_t0',
              'local_asset_t24', 'local_btc_t0', 'local_btc_t24', 'asset_window', 'btc_window', 'reasons']
    with prefix.with_suffix('.csv').open('w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for r in report['observations']:
            writer.writerow(dict(observation_id=r['observation_id'], scan_utc=r['observed_at'],
                                 ranking=r['ranking_type'], rank=r['rank'], asset=r['asset'],
                                 t0_utc=r['price_timestamp'], target_utc=r['target_timestamp'],
                                 mature=r['mature'], status=r['status'],
                                 scan_24h_timestamp=r['scan_24h_timestamp'], scan_24h_elapsed=r['scan_24h_elapsed'],
                                 frozen_asset_t0=r['frozen_asset_t0'], frozen_btc_t0=r['frozen_btc_t0'],
                                 reasons=';'.join(r['reasons']),
                                 **{f'local_{name}_{point}': r[f'local_{name}'][point]['available']
                                    for name in ('asset', 'btc') for point in ('t0', 't24')},
                                 **{f'{name}_window': r[f'local_{name}']['window']['available']
                                    for name in ('asset', 'btc')}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--store', type=Path, default=STORE)
    parser.add_argument('--as-of', required=True, help='UTC audit/maturity time, not the candle-start cutoff')
    parser.add_argument('--out', type=Path, required=True, help='JSON/CSV output prefix')
    args = parser.parse_args()
    report = audit(args.store, args.as_of)
    write_audit(report, args.out)
    print(json.dumps(report['totals'], sort_keys=True))


if __name__ == '__main__':
    main()
