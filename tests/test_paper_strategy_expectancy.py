import pytest
from scripts.paper_strategy_expectancy import metrics,sample_quality,update_stats
from scripts.paper_position_tracker import connect,open_decisions,update_open_trades
def rows(vals):return [{'net_return_pct':x,'holding_hours':24,'mfe_pct':max(x,0),'mae_pct':min(x,0)} for x in vals]
def test_expectancy_math():
 x=metrics(rows([4,4,-2,-2]));assert x['win_rate']==50 and x['average_win_pct']==4 and x['average_loss_pct']==2 and x['payoff_ratio']==2 and x['break_even_win_rate']==pytest.approx(33.3333) and x['expected_value_pct']==1 and x['profit_factor']==2
def test_drawdown_streak():
 x=metrics(rows([1,-2,-3,4]));assert x['maximum_drawdown_pct']==-5 and x['longest_loss_streak']==2
def test_sample_bands():assert [sample_quality(x) for x in (19,20,50,100)]==['INSUFFICIENT','LOW','MEDIUM','HIGHER_CONFIDENCE']
def test_correlated_variant_count_uses_unique_episodes():
 x=metrics(rows([1,2,3]),1,1);assert x['variant_trade_count']==3 and x['unique_setup_episode_count']==1 and x['sample_quality']=='INSUFFICIENT' and x['warnings']==['CORRELATED_VARIANT_SAMPLE']
def test_closed_cycle_repopulates_stats_table(tmp_path):
 db=connect(tmp_path/'stats.sqlite');d={'signal_id':'s','setup_episode_id':'episode','asset':'A','pair':'AUSD','strategy_name':'X','strategy_variant':'V','source_modules':['X'],'source_packet_date':'2026-08-10','first_eligible_timestamp':'2026-08-10T07:00:00+00:00','entry_price':100,'stop_price':98,'target_price':103,'max_hold_hours':24,'setup_score':70,'confidence':50,'estimated_cost_pct':.6,'notional_usd':10000};open_decisions(db,[d],'snapshot');update_open_trades(db,{'A':{'price':103,'high':103,'low':100}},'2026-08-10T08:00:00+00:00');stats=update_stats(db);assert stats and db.execute('select count(*) from paper_strategy_stats').fetchone()[0]==1 and stats[0]['unique_setup_episode_count']==1
