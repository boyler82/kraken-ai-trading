"""Capture ALL setups returned by the existing extractor, without new selection rules.

Legacy latest_completed_candle_timestamp is a candle START (see momentum
calculate_features); converting that explicit timestamp by the documented 1h
interval is a schema conversion, not inference of a missing historical timestamp.
"""
from datetime import timedelta
from copy import deepcopy
from pathlib import Path
from paper_setup_extractor import SOURCES, extract_setups
from .schemas import FEATURES, VERSION, canonical, digest, stamp, strict_loads, utc
from .adapters import prospective
from .outcomes import at_close, load_bars
from .governance import configuration_signature, snapshot_existing_definitions
from .diagnostics import gates

IDENTITY_VERSION='PARENT_SETUP_V2'

def ordered_report(report):
    report=deepcopy(report)
    for key in ('candidates','assets','top_candidates'):
        if isinstance(report.get(key),list):
            report[key]=sorted(report[key],key=canonical)
    return report

def replay_event(event, old):
    event=deepcopy(event)
    # First observation/capture times are creation facts, not rerun wall clock.
    for key in ('observation_timestamp_utc','cluster_id'):
        event[key]=old[key]
    for section,key in (('features','available_at_utc'),('regime','available_at_utc'),('provenance','retrieved_at_utc')):
        event[section][key]=old[section][key]
    if canonical(event)!=canonical(old):
        raise ValueError('IMMUTABLE_PAYLOAD_CONFLICT:'+event['signal_id'])
    return event

FEATURE_MAPPING={'return_1h':'change_1h_pct','return_4h':'change_4h_pct','return_24h':'change_24h_pct',
 'return_7d':'change_7d_pct','momentum_acceleration':'acceleration_4h_pct',
 'rs_btc':'relative_strength_vs_btc_24h_pct','volume_z':'volume_z_score',
 'realized_volatility':'realized_volatility_pct','volatility_expansion':'volatility_expansion_ratio',
 'breakout_distance':'distance_above_breakout_pct'}


def capture(registry, root, observed_at, activation_at, maximum_age_hours=8):
    if utc(observed_at)<utc(activation_at): raise ValueError('CAPTURE_BEFORE_V2_ACTIVATION')
    reports={}; source_digests=[]
    for name, original in sorted(SOURCES.items()):
        path=root/original.relative_to(Path(__file__).resolve().parents[2])
        if not path.exists():raise ValueError('MISSING_CAPTURE_SOURCE:'+name)
        report=ordered_report(strict_loads(path.read_text()))
        ts=report.get('generated_at_utc') or report.get('report_timestamp')
        if not ts:raise ValueError('MISSING_SOURCE_AVAILABILITY:'+name)
        if utc(ts)>utc(observed_at):raise ValueError('FUTURE_SOURCE:'+name)
        if (utc(observed_at)-utc(ts)).total_seconds()>maximum_age_hours*3600:raise ValueError('STALE_SOURCE:'+name)
        reports[name]=report; source_digests.append(digest(report))
    cfg=strict_loads((root/'config/paper_strategy_research_v1.json').read_text())
    # Fingerprint executable definitions, not merely human version labels.
    configuration_version=configuration_signature(root,cfg)
    setups=extract_setups(reports, observed_at, include_parent_provenance=True)
    momentum={r['asset']:r for r in reports['momentum']['candidates']}
    rs={r['asset']:r for r in reports['relative_strength'].get('candidates',[])}
    existing={s['signal_id']:s for s in registry.signals()}
    captured=[]; excluded=[]; pending={}
    for s in setups:
        asset=s['asset']; m=momentum.get(asset,{})
        start=m.get('latest_completed_candle_timestamp');pair=m.get('kraken_pair')
        if not start or not pair:
            excluded.append({'asset':asset,'family':s['strategy_name'],'reason':'MISSING_EXPLICIT_CANDLE_OR_PAIR'});continue
        close=(utc(start)+timedelta(hours=1)).isoformat()
        if utc(close)>utc(observed_at):raise ValueError('FUTURE_REFERENCE_CANDLE')
        if (utc(observed_at)-utc(close)).total_seconds()>maximum_age_hours*3600:
            excluded.append({'asset':asset,'family':s['strategy_name'],'reason':'STALE_REFERENCE_CANDLE'});continue
        bars=load_bars(root/'DATASETS/market_intraday_weekly'/f'{pair}_1H.csv')
        candle=at_close(bars,utc(close))
        if candle is None:raise ValueError('MISSING_OR_INVALID_REFERENCE_CANDLE:'+pair)
        if candle['close']!=m.get('current_price'):raise ValueError('FEATURE_REFERENCE_PRICE_CONFLICT:'+pair)
        # A snapshot has field-level missingness; never reuse a later source feature.
        values={k:m.get(FEATURE_MAPPING.get(k,'')) for k in FEATURES}
        r=rs.get(asset,{})
        # RS report row may not expose a candle timestamp; omit rather than infer.
        if r.get('source_timestamp')==start:
            values['rs_percentile']=r.get('percentile_rank')
            values['rs_acceleration']=r.get('relative_acceleration')
        features={'version':VERSION,'values':values,'missing':[k for k,v in values.items() if v is None],
                  'available_at_utc':stamp(observed_at),'cutoff_utc':close,
                  'last_closed_candle_start_utc':stamp(start),'normalization':'RAW_UNITS_NO_IMPUTATION'}
        eligible=[x for x in momentum.values() if x.get('latest_completed_candle_timestamp')==start]
        btc=momentum.get('BTC',{})
        if btc.get('latest_completed_candle_timestamp')!=start:btc={}
        breadth=[x for x in eligible if x.get('current_price') is not None and x.get('ema20') is not None]
        regime={'version':'RECORDED_MARKET_VECTOR_V1','available_at_utc':stamp(observed_at),'cutoff_utc':close,
                'values':{'market_state':btc.get('momentum_stage','UNAVAILABLE'),
                          'btc_structure':btc.get('momentum_stage'),
                          'breadth_above_ema20_pct':100*sum(x['current_price']>x['ema20'] for x in breadth)/len(breadth) if breadth else None,
                          'realized_volatility':btc.get('realized_volatility_pct'),
                          'sell_pressure':None,'macro_state':None,'liquidity_condition':None},
                'missing':['sell_pressure','macro_state','liquidity_condition']}
        variants=cfg['variants'].get(s['strategy_name'],{})
        if s['strategy_name']=='MULTI_MODULE_CONFIRMATION':
            # Preserve identity from existing decision engine; no new parameters.
            from paper_strategy_decision_engine import create_decisions
            decisions=create_decisions([s],set(),cfg)
            variants={x['strategy_variant']:{} for x in decisions}
        if not variants:
            excluded.append({'asset':asset,'family':s['strategy_name'],'reason':'NO_REGISTERED_VARIANTS'});continue
        from paper_strategy_decision_engine import create_decisions
        decisions_by_variant={d['strategy_variant']:d for d in create_decisions([s],set(),cfg)}
        for variant in sorted(variants):
            parent=s.get('parent_setup') or {'strategy_name':s['strategy_name'],'source_modules':sorted(set(s['source_modules'])),'pair':s['pair'],'source_timestamp':s['metadata'].get('source_timestamp'),'setup_episode_id':s.get('setup_episode_id')}
            source_id=digest([IDENTITY_VERSION,asset,pair,s['strategy_name'],sorted(set(s['source_modules'])),stamp(start),parent])
            event=prospective(source_event_id=source_id,asset=asset,pair=pair,strategy_id=variant,
                 strategy_version=cfg['version']+':'+configuration_version[:12],configuration_version=configuration_version,
                 observation_time=observed_at,reference_close=close,reference_price=candle['close'],
                 features=features,regime=regime,
                 provenance={'source_pipeline':'EXISTING_PAPER_SETUP_EXTRACTOR','source_digests':source_digests,
                             'transformation_version':VERSION,'retrieved_at_utc':observed_at,
                             'reference_candle_interval_seconds':3600,'source_timestamp_semantics':'CANDLE_START',
                             'configuration_digest':configuration_version},
                 levels={'target':decisions_by_variant[variant]['target_price'],
                         'invalidation':decisions_by_variant[variant]['stop_price'],
                         'semantics':'REFERENCE_LEVEL_TOUCH_NOT_EXECUTED_ORDER'})
            event['identity_version']=IDENTITY_VERSION
            event['configuration_identity_contract']='RESEARCH_SEMANTICS_V1'
            event['parent_setup']=deepcopy(parent)
            event['strategy_reference_price']=decisions_by_variant[variant]['entry_price']
            event['activation_level']=s.get('metadata',{}).get('breakout_level')
            event['invalidation_level']=decisions_by_variant[variant]['stop_price']
            event['target_level']=decisions_by_variant[variant]['target_price']
            event['theoretical_rr']=None
            event['rr_status']='NOT_AN_EXECUTED_OR_ASSUMED_ACTIVATED_TRADE'
            key=event['signal_id']
            if key in pending and canonical(pending[key])!=canonical(event):
                raise ValueError('DUPLICATE_PAYLOAD_CONFLICT:'+key)
            pending[key]=event
    # Preflight the complete batch before any capture insertion.
    for key,event in sorted(pending.items()):
        if key in existing:
            pending[key]=replay_event(event,existing[key])
    for report in reports.values():registry.source(report)
    registry.source({'config':cfg,'configuration_digest':configuration_version})
    snapshot_existing_definitions(registry,root,observed_at)
    for key,event in sorted(pending.items()):
        registry.register(event)
        captured.append(key)
    # Source-module qualification rules are reused; their individual gate decisions
    # are not all exposed by the extractor, so no fabricated rejection percentages.
    diagnostics={'observation_timestamp_utc':observed_at,'eligible_setups':len(setups),
                 'captured_signal_ids':captured,'measurement_exclusions':excluded,
                 'source_population':{k:len(v.get('assets',v.get('candidates',[]))) for k,v in reports.items()},
                 'gate_rejection_percentages':gates(reports),'gate_coverage_warning':'ROTATION_SOURCE_MAY_BE_TRUNCATED; COMBINATION_SIGNALS_ARE_DEPENDENT',
                 'selection':'ALL_EXISTING_EXTRACTOR_QUALIFYING_SETUPS_NOT_TOP_RANKS'}
    registry.immutable('scan_runs',digest([observed_at,source_digests]),diagnostics)
    return diagnostics
