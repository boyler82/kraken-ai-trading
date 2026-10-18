from scripts.paper_position_tracker import connect,open_decisions,update_open_trades
def decision():return {'signal_id':'s1','setup_episode_id':'e1','asset':'A','pair':'AUSD','strategy_name':'X','strategy_variant':'V','source_modules':['X'],'source_packet_date':'2026-08-10','first_eligible_timestamp':'2026-08-10T07:00:00+00:00','entry_price':100,'stop_price':98,'target_price':103,'max_hold_hours':24,'setup_score':70,'confidence':50,'estimated_cost_pct':.6,'notional_usd':10000}
def db(tmp_path):return connect(tmp_path/'p.sqlite')
def test_target_stop_and_cost(tmp_path):
 d=db(tmp_path);open_decisions(d,[decision()],'x');r=update_open_trades(d,{'A':{'price':103,'high':104,'low':100}},'2026-08-10T08:00:00+00:00');t=d.execute('select * from paper_trades').fetchone();assert r['closed'] and t['exit_reason']=='TARGET_HIT' and round(t['net_return_pct'],1)==2.4
def test_stop_hit(tmp_path):
 d=db(tmp_path);open_decisions(d,[decision()],'x');update_open_trades(d,{'A':{'price':97,'high':100,'low':97}},'2026-08-10T08:00:00+00:00');assert d.execute('select exit_reason from paper_trades').fetchone()[0]=='STOP_HIT'
def test_conservative_same_bar(tmp_path):
 d=db(tmp_path);open_decisions(d,[decision()],'x');update_open_trades(d,{'A':{'price':100,'high':104,'low':97}},'2026-08-10T08:00:00+00:00');t=d.execute('select exit_reason from paper_trades').fetchone()[0];e=d.execute('select details_json from paper_trade_events order by id desc').fetchone()[0];assert t=='STOP_FIRST_UNCERTAIN_INTRABAR' and 'INTRABAR_SEQUENCE_UNKNOWN' in e
def test_time_and_structure_and_gap(tmp_path):
 d=db(tmp_path);open_decisions(d,[decision()],'x');assert update_open_trades(d,{},'2026-08-10T08:00:00+00:00')['data_gaps'];update_open_trades(d,{'A':{'price':100,'structure_valid':False}},'2026-08-10T09:00:00+00:00');assert d.execute('select exit_reason from paper_trades').fetchone()[0]=='STRUCTURE_INVALIDATED'
