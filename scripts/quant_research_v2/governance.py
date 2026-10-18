"""Research ledger only. No production configuration writer or automatic promotion."""
from .schemas import canonical, digest, strict_loads, utc
STATES=('RESEARCH','CHALLENGER','FORWARD_VALIDATION','CANDIDATE_FOR_PROMOTION','CHAMPION','RETIRED')
TRANSITIONS={'RESEARCH':{'CHALLENGER','RETIRED'}, 'CHALLENGER':{'FORWARD_VALIDATION','RETIRED'},
             'FORWARD_VALIDATION':{'CANDIDATE_FOR_PROMOTION','RETIRED'},
             'CANDIDATE_FOR_PROMOTION':{'CHAMPION','RETIRED'}, 'CHAMPION':{'RETIRED'}, 'RETIRED':set()}

def create(registry, spec):
    required={'strategy_id','version','created_at_utc','parameters','parameter_differences','rationale',
              'training_window','validation_window','oos_window','evidence_summary'}
    if not required<=spec.keys(): raise ValueError('INCOMPLETE_VERSION_SPEC')
    utc(spec['created_at_utc'])
    key=spec['strategy_id']+':'+spec['version']
    registry.immutable('versions',key,spec)
    return key

def state(registry,key):
    events=[strict_loads(r[0]) for r in registry.db.execute('SELECT payload FROM governance_events ORDER BY rowid')]
    related=[e for e in events if e['version_id']==key]
    return related[-1] if related else {'status':'RESEARCH'}

def transition(registry,key,status,at,*,requirements=None,evidence=None,owner_approval=None):
    prior=state(registry,key)
    if status not in TRANSITIONS[prior['status']]: raise ValueError('INVALID_GOVERNANCE_TRANSITION')
    record=registry.db.execute('SELECT payload FROM versions WHERE id=?',(key,)).fetchone()
    if not record: raise ValueError('UNKNOWN_VERSION')
    spec=strict_loads(record[0]); when=utc(at)
    if when<utc(spec['created_at_utc']) or (prior.get('at') and when<=utc(prior['at'])): raise ValueError('INVALID_TRANSITION_TIME')
    row={'version_id':key,'status':status,'at':at,'spec_hash':digest(spec),
         'forward_start_timestamp':prior.get('forward_start_timestamp'),
         'evaluation_requirements':prior.get('evaluation_requirements')}
    if status=='FORWARD_VALIDATION':
        if not requirements or not {'end_utc','min_outcomes','min_clusters'}<=requirements.keys():raise ValueError('MISSING_FORWARD_REQUIREMENTS')
        if utc(requirements['end_utc'])<=when or min(requirements['min_outcomes'],requirements['min_clusters'])<1:raise ValueError('INVALID_FORWARD_REQUIREMENTS')
        row.update(forward_start_timestamp=at,evaluation_requirements=requirements)
    if status=='CANDIDATE_FOR_PROMOTION':
        req=prior['evaluation_requirements']
        if not evidence or when<utc(req['end_utc']) or evidence.get('outcomes',0)<req['min_outcomes'] or evidence.get('clusters',0)<req['min_clusters']:
            raise ValueError('FORWARD_EVALUATION_INCOMPLETE')
        row['evidence']=evidence
    if status=='CHAMPION':
        if not owner_approval or owner_approval.get('actor')!='OWNER' or owner_approval.get('spec_hash')!=digest(spec) or not owner_approval.get('approval_reference'):
            raise ValueError('EXPLICIT_OWNER_APPROVAL_REQUIRED')
        row['owner_approval']=owner_approval
    registry.immutable('governance_events',digest(row),row)
    return row


def configuration_signature(root, cfg):
    # root is the observation/data root; executable definitions belong to this
    # installed source release. Legacy stored signatures are never recomputed.
    from .semantic_identity import configuration_identity, load_contract
    return configuration_identity(cfg, load_contract())


def snapshot_existing_definitions(registry, root, at):
    """Record known CURRENT specs without assigning their versions to old signals."""
    from pathlib import Path
    path=Path(root)/'config/paper_strategy_research_v1.json'
    if not path.exists():return []
    cfg=strict_loads(path.read_text())
    configuration_digest=configuration_signature(root,cfg)
    keys=[]
    for family,variants in cfg['variants'].items():
        for name,params in variants.items():
            version=cfg['version']+':'+configuration_digest[:12]
            key=name+':'+version
            if not registry.db.execute('SELECT 1 FROM versions WHERE id=?',(key,)).fetchone():
                create(registry,{'strategy_id':name,'version':version,'created_at_utc':at,
                    'parameters':params,'parameter_differences':{},
                    'rationale':'Current existing definition snapshot only; historical version provenance is not inferred.',
                    'training_window':None,'validation_window':None,'oos_window':None,
                    'evidence_summary':{'family':family,'status':'RESEARCH_NOT_AUTOMATIC_CHAMPION'},
                    'configuration_digest':configuration_digest})
            keys.append(key)
    return keys
