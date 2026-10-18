from __future__ import annotations
from typing import Any
import pandas as pd
from lib.decision_registry import read_all,write_record
from lib.research_module_contract import make_result,write_result
from weekly_consolidation_common import ROOT,atomic_write
OUT=ROOT/"DAILY_REPORTS/AI_CONFIDENCE";WEIGHTS={"market_regime":15,"relative_strength":15,"momentum":15,"consolidation":15,"btc_rotation":15,"capital_flow":10,"leadership_rotation":10,"validation":5};VERSION="1.0"
def aggregate(registry:dict[str,dict],as_of:Any=None)->dict:
    assets=set()
    for rec in registry.values():
        for key in ('candidates','top_leaders','top_candidates','new_opportunities'):
            for r in rec.get(key,[])[:8]:
                if r.get('asset'):assets.add(str(r['asset']))
    rows=[];confirmations=[];conflicts=[]
    for asset in sorted(assets):
        support=[];oppose=[];unavailable=[];weighted_support=0.;weighted_conflict=0.
        for module,weight in WEIGHTS.items():
            rec=registry.get(module,{})
            if rec.get('status') in {'FAILED','UNAVAILABLE',None}:unavailable.append(module);continue
            pool=[]
            for key in ('candidates','top_leaders','top_candidates') :pool+=rec.get(key,[])
            match=next((r for r in pool if str(r.get('asset'))==asset),None)
            if module in {'market_regime','capital_flow'}:match=rec.get('summary',{})
            if not match:unavailable.append(module);continue
            positive=not any(str(match.get(k,'')).upper() in {'STALE','DETERIORATING','RELATIVE_LAGGARD','FAILED_BREAKOUT','BEAR'} for k in ('freshness','classification','momentum_stage','crypto_regime')) and float(match.get('score',match.get('relative_strength_score',match.get('momentum_breakout_score',50))) or 0)>=40
            discount=.75 if module in {'momentum','consolidation'} else 1
            if positive:support.append(module);weighted_support+=weight*discount
            else:oppose.append(module);weighted_conflict+=weight*discount
        denom=weighted_support+weighted_conflict+sum(WEIGHTS[m] for m in unavailable)
        score=0 if denom==0 else weighted_support/denom*100;sample_quality='LOW';fresh=not any(registry.get(m,{}).get('freshness')=='STALE' for m in support)
        if sample_quality=='LOW':score=min(score,60)
        if not fresh:score=min(score,40)
        band='HIGH' if score>=75 else 'MEDIUM' if score>=50 else 'LOW';row={'asset':asset,'supporting_modules':support,'opposing_modules':oppose,'unavailable_modules':unavailable,'support_count':len(support),'conflict_count':len(oppose),'weighted_support':weighted_support,'weighted_conflict':weighted_conflict,'regime_alignment':'SUPPORTED' if 'market_regime' in support else 'UNKNOWN_OR_CONFLICT','liquidity_quality':'UNKNOWN','freshness_quality':'FRESH' if fresh else 'STALE','sample_quality':sample_quality,'evidence_confidence_score':round(score,4),'confidence_band':band,'evidence_strength':'STRONG' if score>=70 else 'MODERATE' if score>=45 else 'WEAK','agreement_level':'HIGH' if len(support)>=3 and not oppose else 'MIXED' if support and oppose else 'LOW','strongest_support':support[0] if support else None,'strongest_conflict':oppose[0] if oppose else None,'invalidation_condition':'Supporting module evidence weakens or becomes stale','primary_risk':'LOW_SAMPLE_QUALITY','unknowns':['Evidence score is not a probability']}
        rows.append(row)
        if len(support)>=2:confirmations.append({'asset':asset,'modules':support[:4]})
        if support and oppose:conflicts.append({'asset':asset,'support':support[:3],'oppose':oppose[:3]})
    rows=sorted(rows,key=lambda r:(-r['evidence_confidence_score'],r['asset']))[:8]
    return make_result('ai_confidence','1.0.0',as_of,freshness='FRESH',summary={'weights_version':VERSION,'module_weights':WEIGHTS,'candidate_count':len(rows),'probability_claim':False},candidates=rows,confirmations=confirmations[:5],conflicts=conflicts[:5],risks=['LOW_SAMPLE_QUALITY_CAP_APPLIED'],unknowns=['Evidence confidence is not historically calibrated probability'],source_files=[str(ROOT/'DECISION_REGISTRY')])
def run(as_of=None):
    result=aggregate(read_all(),as_of);OUT.mkdir(parents=True,exist_ok=True);base=OUT/f"{result['report_date']}_ai_confidence";write_result(base.with_suffix('.json'),result);atomic_write(base.with_suffix('.csv'),pd.DataFrame([{k:v for k,v in r.items() if not isinstance(v,list)} for r in result['candidates']]).to_csv(index=False));atomic_write(base.with_suffix('.md'),"# AI Confidence Engine\n\nEvidence confidence is not a probability.\n\n"+"\n".join(f"- {r['asset']} | {r['evidence_confidence_score']:.1f} | {r['confidence_band']} | support {r['support_count']} conflict {r['conflict_count']}" for r in result['candidates'])+"\n");
    for ext in ('.json','.csv','.md'):atomic_write(OUT/f"latest_ai_confidence{ext}",base.with_suffix(ext).read_text(),backup=False)
    write_record('ai_confidence',{'module_name':'ai_confidence','status':result['status'],'freshness':result['freshness'],'generated_at_utc':result['generated_at_utc'],'summary':result['summary'],'candidates':result['candidates'][:8],'confirmations':result['confirmations'][:5],'conflicts':result['conflicts'][:5],'risks':result['risks'][:10],'source_file':str(base.with_suffix('.json'))});return result
if __name__=='__main__':print(f"AI confidence assets: {len(run()['candidates'])}")
