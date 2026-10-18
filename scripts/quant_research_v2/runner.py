"""Deterministic offline measurement runner. All network work remains upstream."""
import hashlib
import fcntl
import os
import tempfile
from pathlib import Path
from datetime import datetime, timezone
from .schemas import HORIZONS, VERSION, canonical, digest, stamp, strict_loads, utc
from .registry import Registry
from .adapters import historical
from .capture import capture
from .outcomes import load_bars, outcome
from .lifecycle import MODEL, benchmark, preflight
from .evidence import report, joined
from .parameters import research
from .context import compact
from .governance import snapshot_existing_definitions, state


def write_json(path, data):
    path.parent.mkdir(parents=True,exist_ok=True)
    encoded=canonical(data)+'\n'
    if path.exists() and path.read_text()==encoded:return
    fd,tmp=tempfile.mkstemp(dir=path.parent,prefix=path.name+'.')
    try:
        with os.fdopen(fd,'w') as f:f.write(encoded)
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)


def run(root, as_of, *, capture_current=False, db_path=None, output_dir=None, windows=None, require_benchmark=False):
    root=Path(root); as_of=stamp(as_of)
    output_dir=Path(output_dir or root/'RESEARCH_REPORTS/QUANT_RESEARCH_V2')
    cfg=strict_loads((root/'config/quant_research_v2.json').read_text())
    if cfg['trading_capability']!='DISABLED':raise ValueError('TRADING_MUST_REMAIN_DISABLED')
    source_path=root/'DATASETS/TACTICAL_OUTCOMES/tactical_candidate_snapshots.jsonl'
    raw=source_path.read_bytes()
    source_rows=[strict_loads(line) for line in raw.decode().splitlines() if line.strip()]
    if any(utc(r['timestamp'])>utc(as_of) for r in source_rows):raise ValueError('SOURCE_OBSERVATION_AFTER_AS_OF')
    database=Path(db_path or root/'DATASETS/QUANT_RESEARCH_V2/research.sqlite')
    registry=Registry(database)
    lock=database.with_suffix(database.suffix+'.lock').open('a')
    fcntl.flock(lock,fcntl.LOCK_EX)
    try:
        registry.db.execute('BEGIN IMMEDIATE')
        last=registry.db.execute("SELECT payload FROM metadata WHERE key='last_as_of'").fetchone()
        if last and utc(as_of)<utc(strict_loads(last[0])):raise ValueError('AS_OF_REGRESSION_USE_SEPARATE_REPLAY_DB')
        for row in source_rows:
            registry.register(historical(row))
        definition_ids=snapshot_existing_definitions(registry,root,as_of)
        diagnostics=None
        if capture_current:
            activation=registry.db.execute("SELECT payload FROM metadata WHERE key='activation'").fetchone()
            if activation:
                activation_at=strict_loads(activation[0])['at']
            else:
                activation_at=as_of
                registry.immutable('metadata','activation',{'at':as_of,'schema_version':VERSION,
                                    'timing_basis':'CLOSED_CANDLE_REFERENCE','owner_authorized':True})
            diagnostics=capture(registry,root,as_of,activation_at,cfg['maximum_source_age_hours'])
        signals=registry.signals()
        market=root/'DATASETS/market_intraday_weekly'; cache={}; market_hashes={}
        def bars(pair):
            if not pair:return []
            if pair not in cache:
                path=market/f'{pair}_1H.csv'
                cache[pair]=load_bars(path)
                market_hashes[pair]=hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None
            return cache[pair]
        registry.bind_legacy_availability(as_of)
        benchmark_preflight = preflight(signals,bars('XBTUSD'),as_of) if require_benchmark else {'status':'OFFLINE_REPLAY'}
        for signal in signals:
            # Do not read huge market files for observations already disqualified.
            available=signal['classification']=='MEASURABLE'
            asset_bars=bars(signal['pair']) if available else []
            btc_bars=bars('XBTUSD') if available else []
            for h in HORIZONS:
                row=outcome(signal,h,asset_bars,[],as_of)
                asset=registry.put_asset(row,as_of)
                registry.put_benchmark(benchmark(signal,asset,btc_bars,as_of))
        outcomes=registry.measurements(as_of)
        evidence=report(signals,outcomes,as_of)
        evidence['configuration_registry']=[{'version_id':key,'status':state(registry,key)['status']} for key in definition_ids]
        evidence['capture_diagnostics']=diagnostics
        evidence['benchmark_preflight']=benchmark_preflight
        evidence['lifecycle_model_version']=MODEL
        evidence['data_quality']['current_capture_attempted']=capture_current
        if windows is not None:
            registry.immutable('metadata','parameter_protocol:'+digest(windows),
                {'windows':windows,'method':'TRAIN_QUANTILE_3X3_V1','basis':'CLOSED_CANDLE_REFERENCE',
                 'warning':'NO_OOS_BASED_PARAMETER_SELECTION; NEW_VERSION_REQUIRED_AFTER_TUNING'})
        parameters=research(joined(signals,outcomes),windows)
        if windows is not None:
            registry.immutable('metadata','parameter_access:'+digest([windows,as_of]),
                {'windows':windows,'as_of':as_of,'oos_results_examined':True,
                 'report_digest':digest(parameters)})
        # Descriptions remain usable even when outcome reconstruction is rejected.
        parameters['recorded_feature_inventory']={name:{
            'available_observations':sum(s['features']['values'].get(name) is not None for s in signals),
            'missing_observations':sum(s['features']['values'].get(name) is None for s in signals),
            'outcome_association':'NOT_ESTIMATED_WITHOUT_VALID_MEASUREMENTS'}
            for name in ('rs_percentile','volume_z','momentum_acceleration','volatility_expansion')}
        audit_path=root/'RESEARCH_REPORTS/strategy_evidence_audit_latest.json'
        if audit_path.exists():
            audit=strict_loads(audit_path.read_text())
            evidence['legacy_strategy_context']=[{
                'strategy_id':x['strategy_name'], 'classification':x.get('classification'),
                'legacy_raw_n':x.get('sample_structure',{}).get('raw_episode_n'),
                'warnings':x.get('major_warnings',[]),
                'v2_observations':sum(s['strategy_id']==x['strategy_name'] for s in signals),
                'interpretation':'LEGACY_EVIDENCE_NOT_IMPORTED_AS_V2_CC_OR_PROSPECTIVE_RESULTS'}
                for x in audit.get('strategies',[])]
            evidence['legacy_audit_digest']=digest(audit)
        from .semantic_identity import load_contract, measurement_identity
        manifest={'configuration_identity_contract':'RESEARCH_SEMANTICS_V1',
                  'measurement_contract_digest':measurement_identity(load_contract()),
                  'schema_version':VERSION,'as_of_utc':as_of,'source_sha256':hashlib.sha256(raw).hexdigest(),
                  'configuration_digest':digest(cfg),'market_file_hashes':market_hashes,
                  'registry_signals_digest':digest(signals),'outcomes_digest':digest(registry.outcomes()),
                  'measurement_view_digest':digest(outcomes),'lifecycle_model_version':MODEL,
                  'evidence_digest':digest(evidence),'parameter_report_digest':digest(parameters),
                  'trading_capability':'DISABLED','network_calls':0}
        run_id=digest(manifest); manifest['run_id']=run_id
        context=compact(evidence,signals,outcomes,run_id)
        registry.immutable('metadata','manifest:'+run_id,manifest)
        registry.db.execute("INSERT INTO metadata VALUES('last_as_of',?) ON CONFLICT(key) DO UPDATE SET payload=excluded.payload",(canonical(as_of),))
        registry.db.commit()
        # Readers compare run IDs: an interrupted publication cannot masquerade as
        # a consistent bundle. Manifest is written last as the completion marker.
        for name,value in [('latest_evidence.json',evidence),('parameter_stability.json',parameters),('latest_context.json',context)]:
            value['run_id']=run_id; write_json(output_dir/name,value)
        text='# Parameter stability research\n\nBasis: CLOSED_CANDLE_REFERENCE. Event study only.\n\n'+parameters['status']+'\n\nNo thresholds promoted.\n\nSee parameter_stability.json for region cells, counts and declared windows.\n'
        (output_dir/'parameter_stability.md').write_text(text)
        write_json(output_dir/'latest_manifest.json',manifest)
        if output_dir==root/'RESEARCH_REPORTS/QUANT_RESEARCH_V2':
            write_json(root/'DAILY_REPORTS/CHATGPT_HANDOFF/latest_quant_research_v2.json',context)
        return context
    except Exception:
        registry.db.rollback()
        raise
    finally:
        registry.close()
        fcntl.flock(lock,fcntl.LOCK_UN)
        lock.close()
