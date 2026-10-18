"""Small exploratory region maps. OOS never selects bins or winning parameters."""
from collections import defaultdict
from datetime import timedelta
from .schemas import utc
from .evidence import statistics, WARNINGS


def split(rows, train_end, validation_end, oos_end, embargo_hours=72):
    a,b,c=map(utc,(train_end,validation_end,oos_end))
    if not a < b < c or embargo_hours < 72:
        raise ValueError('INVALID_CHRONOLOGICAL_SPLIT_OR_EMBARGO')
    groups=defaultdict(list)
    for r in rows: groups[r['cluster_id']].append(r)
    result={'TRAIN':[], 'VALIDATION':[], 'OOS':[], 'PURGED':[]}
    for group in groups.values():
        start=min(utc(r['observation_timestamp_utc']) for r in group)
        end=max(utc(r['endpoint_utc']) for r in group)
        if end<=a: partition='TRAIN'
        elif start>a+timedelta(hours=embargo_hours) and end<=b: partition='VALIDATION'
        elif start>b+timedelta(hours=embargo_hours) and end<=c: partition='OOS'
        else: partition='PURGED'
        result[partition].extend(group)
    return result


def edges(train, feature, minimum=20):
    """At most three empirical broad bins; derived solely from TRAIN."""
    values=sorted(r['features'][feature] for r in train if isinstance(r['features'].get(feature),(int,float)))
    if len(values)<minimum*2: return []
    bins=min(3,len(values)//minimum)
    return sorted(set(values[int(len(values)*i/bins)] for i in range(1,bins)))


def stability(rows, windows, features=('rs_percentile','volume_z'), minimum=20):
    parts=split(rows,**windows)
    cuts=[edges(parts['TRAIN'],f,minimum) for f in features]
    def cell(r):
        vals=[r['features'].get(f) for f in features]
        if any(v is None for v in vals):return None
        return tuple(sum(v>=e for e in es) for v,es in zip(vals,cuts))
    cells=[]; tested=0
    for i in range(len(cuts[0])+1):
        for j in range(len(cuts[1])+1):
            sub={k:[r for r in v if cell(r)==(i,j)] for k,v in parts.items() if k!='PURGED'}
            tested+=1
            cells.append({'cell':[i,j], 'metrics':{k:statistics(v) for k,v in sub.items()},
                          'status':'INSUFFICIENT_SAMPLE' if len(sub['TRAIN'])<minimum or len({r['cluster_id'] for r in sub['TRAIN']})<minimum else 'EXPLORATORY_ONLY'})
    for c in cells:
        ev=c['metrics']['TRAIN']['mean_return_pct']
        neighbors=[x for x in cells if sum(abs(a-b) for a,b in zip(x['cell'],c['cell']))==1]
        c['isolated_positive_peak']=bool(ev is not None and ev>0 and neighbors and all((x['metrics']['TRAIN']['mean_return_pct'] or 0)<=0 for x in neighbors))
    return {'features':list(features),'train_fitted_edges':cuts,'windows':windows,
            'partition_counts':{k:len(v) for k,v in parts.items()}, 'cells':cells,
            'hypotheses_tested':tested,'warnings':WARNINGS,
            'conclusion':'NO_PROMOTION; DESCRIPTIVE_REGIONS_ONLY; OOS_REPORTED_ONCE_IS_NO_LONGER_UNTOUCHED',
            'missing_features':sum(cell(r) is None for r in rows)}


def research(rows, windows=None):
    if windows is None:
        return {'status':'NOT_EVALUATED_NO_PREDECLARED_WINDOWS','hypotheses_tested':0,
                'complete_outcomes_available':len(rows),'maps':[], 'warnings':WARNINGS,
                'conclusion':'NO_STABILITY_CLAIM; NO_THRESHOLDS_PROMOTED'}
    grouped=defaultdict(list)
    for r in rows:
        grouped[(r['strategy_id'],r['strategy_version'],r['configuration_version'],r['cohort'],r['timing_basis'],r['horizon_hours'])].append(r)
    maps=[{'identity':list(key),**stability(rs,windows)} for key,rs in sorted(grouped.items(),key=lambda x:str(x[0]))]
    return {'status':'EXPLORATORY_ONLY','maps':maps,'hypotheses_tested':sum(m['hypotheses_tested'] for m in maps),'warnings':WARNINGS}


def walk_forward(rows, folds):
    """Predeclared chronological folds; never random shuffles or cross-version pools."""
    return [research(rows, fold) for fold in folds]
