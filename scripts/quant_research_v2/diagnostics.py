"""Read-only qualification gate accounting mirroring the existing extractor.

Rates use the population actually exposed by each source; rotation dashboard
coverage is explicitly limited and never described as all exchange signals.
"""
def gates(reports):
    rqi={x['asset']:x for x in reports.get('rqi',{}).get('assets',[])}
    def consolidation(x):
        q=rqi.get(x.get('asset'),{})
        return [('range_valid',bool(x.get('range_valid',x.get('range_still_valid')))),
                ('position_zone',q.get('position_zone') in {'LOWER_ZONE','LOWER_MIDDLE'}),
                ('range_quality',q.get('rqi_classification') in {'ACCEPTABLE_RANGE','GOOD_RANGE','EXCELLENT_RANGE'})]
    defs={
      'consolidation':('candidates',consolidation,lambda x:x.get('latest_available_market_price'),lambda x:x.get('freshness_status') or 'FRESH'),
      'early_expansion':('assets',lambda x:[('classification',x.get('classification') in {'PRE_MOVE_BUILDING','PRE_MOVE_STRONG','EARLY_EXPANSION_DEVELOPING'})],lambda x:x.get('current_price'),lambda x:x.get('freshness') or 'FRESH'),
      'momentum':('candidates',lambda x:[('momentum_stage',x.get('momentum_stage') in {'EARLY_MOMENTUM','BREAKOUT_DEVELOPING','BREAKOUT_CONFIRMED'}),('overextension',x.get('overextension_risk')!='HIGH')],lambda x:x.get('current_price'),lambda x:x.get('freshness_status') or 'FRESH'),
      'rotation':('top_candidates',lambda x:[('rotation_review',x.get('candidate_disposition')=='ACTIONABLE_REVIEW' or x.get('user_facing_rotation_state')=='REVIEW_BTC_TO_ALT')],lambda x:x.get('current_price'),lambda x:reports.get('rotation',{}).get('data_freshness','FRESH'))}
    out={}
    for family,(key,fn,price,fresh) in defs.items():
        rows=reports.get(family,{}).get(key,[])
        if family=='rotation' and not rows:rows=reports.get(family,{}).get('candidates',[])
        counter={};passed=0
        for row in rows:
            checks=fn(row)+[('price_present',price(row) is not None),('freshness',fresh(row)=='FRESH')]
            for name,success in checks:
                item=counter.setdefault(name,{'evaluated':0,'rejected':0});item['evaluated']+=1
                if not success:item['rejected']+=1;break
            else:passed+=1
        for item in counter.values():item['rejected_pct_of_evaluated']=100*item['rejected']/item['evaluated']
        out[family]={'source_population':len(rows),'qualified_primary_setups':passed,'gates':counter,
                     'coverage':'EXISTING_SOURCE_ROWS_ONLY','source_truncation_possible':family=='rotation'}
    return out
