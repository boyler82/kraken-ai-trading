from scripts.paper_strategy_decision_engine import create_decisions,episode_key
def setup():return {'asset':'A','pair':'AUSD','strategy_name':'EARLY_EXPANSION','entry_reference_price':100,'setup_score':70,'confidence':60,'source_modules':['EARLY_EXPANSION'],'source_timestamp':'2026-08-10T07:00:00Z','first_eligible_timestamp':'2026-08-10T07:00:00Z','source_packet_date':'2026-08-10','metadata':{}}
def test_parallel_variants_same_entry():
 d=create_decisions([setup()]);assert len(d)==4 and len({x['entry_price'] for x in d})==1 and len({x['first_eligible_timestamp'] for x in d})==1
def test_no_duplicate_episode():
 s=setup();d=create_decisions([s]);assert not create_decisions([s],{(episode_key(s),x['strategy_variant']) for x in d})
def test_standardized_notional_and_costs():assert all(x['notional_usd']==10000 and x['estimated_cost_pct']==.6 for x in create_decisions([setup()]))
def test_no_lookahead_timestamp_preserved():assert create_decisions([setup()])[0]['first_eligible_timestamp']=='2026-08-10T07:00:00Z'
