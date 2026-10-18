"""Transactional, immutable signals and resumable outcomes in a local SQLite store."""
import sqlite3
import zlib
from pathlib import Path
from .schemas import canonical, digest, strict_loads, validate

class Registry:
    def __init__(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, timeout=30)
        self.db.execute('PRAGMA foreign_keys=ON')
        self.db.executescript('''
          CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY, payload TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS signals(id TEXT PRIMARY KEY, payload TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS snapshots(id TEXT PRIMARY KEY, kind TEXT NOT NULL, payload TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS sources(id TEXT PRIMARY KEY, payload BLOB NOT NULL);
          CREATE TABLE IF NOT EXISTS outcomes(signal_id TEXT REFERENCES signals(id), basis TEXT,
             horizon INTEGER, payload TEXT NOT NULL, PRIMARY KEY(signal_id,basis,horizon));
          CREATE TABLE IF NOT EXISTS benchmark_measurements(id TEXT PRIMARY KEY,
             signal_id TEXT REFERENCES signals(id), basis TEXT, horizon INTEGER,
             symbol TEXT, version TEXT, payload TEXT NOT NULL);
          CREATE INDEX IF NOT EXISTS benchmark_measurement_key ON benchmark_measurements(signal_id,basis,horizon,symbol,version);
          CREATE TRIGGER IF NOT EXISTS benchmark_no_update BEFORE UPDATE ON benchmark_measurements
             BEGIN SELECT RAISE(ABORT,'IMMUTABLE_BENCHMARK'); END;
          CREATE TRIGGER IF NOT EXISTS benchmark_no_delete BEFORE DELETE ON benchmark_measurements
             BEGIN SELECT RAISE(ABORT,'IMMUTABLE_BENCHMARK'); END;
          CREATE TABLE IF NOT EXISTS versions(id TEXT PRIMARY KEY, payload TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS governance_events(id TEXT PRIMARY KEY, payload TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS scan_runs(id TEXT PRIMARY KEY, payload TEXT NOT NULL);
        ''')
    def close(self):
        self.db.close()
    def immutable(self, table, key, value):
        if table not in ('signals', 'metadata', 'versions', 'governance_events', 'scan_runs'):
            raise ValueError('INVALID_TABLE')
        column = 'key' if table == 'metadata' else 'id'
        encoded = canonical(value)
        self.db.execute(f'INSERT OR IGNORE INTO {table}({column},payload) VALUES(?,?)', (key, encoded))
        prior = self.db.execute(f'SELECT payload FROM {table} WHERE {column}=?', (key,)).fetchone()[0]
        if prior != encoded:
            raise ValueError('IMMUTABLE_PAYLOAD_CONFLICT:' + key)
    def register(self, signal):
        validate(signal)
        self.immutable('signals', signal['signal_id'], signal)
        for kind in ('features', 'regime'):
            value = canonical(signal[kind])
            self.db.execute('INSERT OR IGNORE INTO snapshots VALUES(?,?,?)', (digest(signal[kind]), kind, value))
    def source(self, value):
        key = digest(value)
        self.db.execute('INSERT OR IGNORE INTO sources VALUES(?,?)', (key, zlib.compress(canonical(value).encode())))
        return key
    def signals(self):
        return [strict_loads(x[0]) for x in self.db.execute('SELECT payload FROM signals ORDER BY id')]
    def outcomes(self):
        return [strict_loads(x[0]) for x in self.db.execute('SELECT payload FROM outcomes ORDER BY signal_id,basis,horizon')]
    def put_outcome(self, row):
        key = (row['signal_id'], row['timing_basis'], row['horizon_hours'])
        prior = self.db.execute('SELECT payload FROM outcomes WHERE signal_id=? AND basis=? AND horizon=?', key).fetchone()
        if prior and strict_loads(prior[0])['status'] == 'COMPLETE':
            if prior[0] != canonical(row):
                raise ValueError('COMPLETED_OUTCOME_CONFLICT')
            return
        self.db.execute('INSERT INTO outcomes VALUES(?,?,?,?) ON CONFLICT(signal_id,basis,horizon) DO UPDATE SET payload=excluded.payload', (*key, canonical(row)))

    def bind_legacy_availability(self, as_of):
        """Add provenance links only; leave every legacy outcome byte untouched."""
        from .schemas import utc
        rows = self.outcomes()
        legacy = [r for r in rows if r['status']=='COMPLETE' and 'lifecycle_model_version' not in r]
        if not legacy:
            return
        manifests = [strict_loads(v) for (v,) in self.db.execute("SELECT payload FROM metadata WHERE key LIKE 'manifest:%'")]
        matching = [m['as_of_utc'] for m in manifests if m.get('outcomes_digest')==digest(rows)]
        known = min(matching, key=utc) if matching else None
        for row in legacy:
            key = 'legacy_asset_availability:' + digest([row['signal_id'],row['timing_basis'],row['horizon_hours']])
            if self.db.execute('SELECT 1 FROM metadata WHERE key=?',(key,)).fetchone():
                continue
            self.immutable('metadata',key,{'available_as_of':known or as_of,
                'availability_basis':'MATCHING_ORIGINAL_RUN_MANIFEST' if known else 'FIRST_VERIFIED_EXISTENCE_ORIGINAL_TIME_UNKNOWN',
                'original_payload_digest':digest(row), 'legacy_version':'LEGACY_V0'})

    def put_asset(self, calculated, as_of):
        from .lifecycle import MODEL, asset_facts, asset_state
        row = asset_facts(calculated)
        key = (row['signal_id'],row['timing_basis'],row['horizon_hours'])
        prior = self.db.execute('SELECT payload FROM outcomes WHERE signal_id=? AND basis=? AND horizon=?',key).fetchone()
        if prior:
            old = strict_loads(prior[0])
            if old['status']=='COMPLETE':
                if canonical(asset_facts(old)) != canonical(row):
                    raise ValueError('IMMUTABLE_ASSET_OUTCOME_CONFLICT:'+row['signal_id']+':'+str(row['horizon_hours']))
                return old
        row.update(lifecycle_model_version=MODEL,asset_state=asset_state(row),asset_available_as_of=as_of)
        if prior:
            previous = strict_loads(prior[0])
            if canonical(asset_facts(previous))==canonical(asset_facts(row)):
                return previous
        self.put_outcome(row)
        return row

    def put_benchmark(self, row):
        from .schemas import utc
        row = dict(row)
        key = [row[k] for k in ('observation_id','timing_basis','horizon_hours','benchmark_symbol','calculation_version')]
        # Benchmark-only completion and its later asset link are append-only evidence.
        identity = key + [row['state']]
        if row['state']!='BENCHMARK_COMPLETE':
            identity.append(row['reason_codes'])
        elif row['asset_measurement_digest'] is None:
            identity.append('BENCHMARK_ONLY')
        if row['state']=='BENCHMARK_COMPLETE':
            excluded={'available_as_of','evidence_id','asset_measurement_digest','btc_relative_return_pct'}
            facts=lambda r: {k:v for k,v in r.items() if k not in excluded}
            for raw, in self.db.execute('SELECT payload FROM benchmark_measurements WHERE signal_id=? AND basis=? AND horizon=? AND symbol=? AND version=?',key):
                old=strict_loads(raw)
                if old['state']=='BENCHMARK_COMPLETE' and canonical(facts(old))!=canonical(facts(row)):
                    raise ValueError('IMMUTABLE_BENCHMARK_CONFLICT:'+old['evidence_id'])
        record_id = 'bm_' + digest(identity)
        row['evidence_id'] = record_id
        prior = self.db.execute('SELECT payload FROM benchmark_measurements WHERE id=?',(record_id,)).fetchone()
        if prior:
            old = strict_loads(prior[0])
            if utc(row['available_as_of']) < utc(old['available_as_of']):
                raise ValueError('BENCHMARK_AVAILABILITY_REGRESSION')
            row['available_as_of'] = old['available_as_of']
            if canonical(row)!=canonical(old):
                raise ValueError('IMMUTABLE_BENCHMARK_CONFLICT:'+record_id)
            return old
        self.db.execute('INSERT INTO benchmark_measurements VALUES(?,?,?,?,?,?,?)',
            (record_id,*key,canonical(row)))
        return row

    def measurements(self, as_of):
        from .schemas import utc
        from .lifecycle import combined
        benchmarks = {}
        for raw, in self.db.execute('SELECT payload FROM benchmark_measurements ORDER BY id'):
            row = strict_loads(raw)
            if utc(row['available_as_of']) > utc(as_of):
                continue
            key = (row['observation_id'],row['timing_basis'],row['horizon_hours'])
            old = benchmarks.get(key)
            priority = lambda r: (r['state']=='BENCHMARK_COMPLETE',utc(r['available_as_of']),r['btc_relative_return_pct'] is not None,r['evidence_id'])
            if old is None or priority(row)>priority(old):benchmarks[key]=row
        result = []
        for asset in self.outcomes():
            key = (asset['signal_id'],asset['timing_basis'],asset['horizon_hours'])
            link = self.db.execute('SELECT payload FROM metadata WHERE key=?',
                ('legacy_asset_availability:'+digest(list(key)),)).fetchone()
            if link and strict_loads(link[0])['original_payload_digest']!=digest(asset):
                raise ValueError('LEGACY_ASSET_PAYLOAD_CONFLICT:'+asset['signal_id'])
            row = combined(asset,benchmarks.get(key),as_of,
                strict_loads(link[0])['available_as_of'] if link else None)
            if row is not None:result.append(row)
        return result
