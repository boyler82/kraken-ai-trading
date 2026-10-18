from __future__ import annotations
import argparse,json
from collections import Counter
from pathlib import Path
from lib.research_memory import ROOT,STATS,atomic_json,connect,metrics,sample_quality
from find_historical_analogs import find

OUT=ROOT/'DAILY_REPORTS/CHATGPT_EXPORT/latest_ai_research_memory_packet.json';MAX_BYTES=150_000
def _json(path):
 try:return json.loads(path.read_text()) if path.exists() else {}
 except Exception:return {}
def build(db):
 snaps=db.execute('SELECT count(*),min(timestamp_utc),max(timestamp_utc) FROM research_market_snapshots').fetchone();unique=db.execute('SELECT count(DISTINCT setup_episode_id) FROM research_setup_outcomes').fetchone()[0]
 regimes=[x[0] for x in db.execute('SELECT DISTINCT market_regime FROM research_market_snapshots WHERE market_regime IS NOT NULL')]
 groups={}
 for r in map(dict,db.execute('SELECT * FROM research_setup_outcomes')):groups.setdefault((r['strategy_family'],r['strategy_variant']),[]).append(r)
 strategies=[]
 for key,rows in groups.items():m=metrics(rows);strategies.append({'strategy_family':key[0],'strategy_variant':key[1],**m,'sample_quality':sample_quality(m['unique_episode_count'])})
 strategies=sorted(strategies,key=lambda x:(-x['unique_episode_count'],x['strategy_family'],x['strategy_variant']))[:10]
 cells=[dict(x) for x in db.execute('SELECT * FROM research_conditional_stats WHERE unique_episode_count>=30 ORDER BY expected_value_pct DESC')]
 def compact(x):return {'conditions':json.loads(x['values_json']),'N':x['unique_episode_count'],'EV':x['expected_value_pct'],'PF':x['profit_factor'],'win_rate':x['win_rate'],'sample_quality':x['sample_quality'],'label':x['research_label']}
 edges=[compact(x) for x in cells if (x['expected_value_pct'] or 0)>0 and (x['profit_factor'] or 0)>1][:10];anti=[compact(x) for x in reversed(cells) if (x['expected_value_pct'] or 0)<0 and (x['profit_factor'] or 99)<1][:10]
 chief=ROOT/'DAILY_REPORTS/CHATGPT_EXPORT/latest_ai_chief_strategist_packet.json';current=[]
 try:candidates=json.loads(chief.read_text()).get('candidates',[])[:10]
 except Exception:candidates=[]
 for c in candidates:
  a=find(db,asset=c.get('asset'));current.append({'asset':c.get('asset'),'historical_analog_count':a['number_of_valid_analogs'],'analog_12h_return':a.get('median_forward_return_12h'),'analog_24h_return':a.get('median_forward_return_24h'),'analog_48h_return':a.get('median_forward_return_48h'),'analog_mfe':a.get('median_mfe_24h'),'analog_mae':a.get('median_mae_24h'),'conditional_strategy_context':[],'sample_quality':a.get('sample_quality')})
 fast=json.loads((STATS/'latest_fast_range_candidates.json').read_text()).get('candidates',[])[:5] if (STATS/'latest_fast_range_candidates.json').exists() else []
 counts=Counter(x[0] for x in db.execute('SELECT market_regime FROM research_market_snapshots WHERE market_regime IS NOT NULL'));warnings=['MULTIPLE_TESTING_RISK','DATA_SNOOPING_RISK','CORRELATED_VARIANT_SAMPLE']
 if counts and max(counts.values())/sum(counts.values())>.8:warnings.append('REGIME_IMBALANCE')
 if unique<10:warnings.append('INSUFFICIENT_SAMPLE')
 oos_data=_json(STATS/'latest_oos_strategy_validation.json')
 oos_summary=[]
 # Compact by evidence volume, never by OOS performance (no OOS winner search).
 oos_rows=sorted(oos_data.get('strategies',[]),key=lambda x:(-x.get('FORWARD_OOS',{}).get('unique_episode_count',0),str(x.get('strategy_family')),str(x.get('strategy_variant'))))
 for row in oos_rows[:5]:
  dev=row.get('DEVELOPMENT',{});oos=row.get('FORWARD_OOS',{})
  oos_summary.append({'strategy':row.get('strategy_variant') or row.get('strategy_family'),'development_n':dev.get('unique_episode_count',0),'development_ev':dev.get('expected_value_pct'),'development_pf':dev.get('profit_factor'),'oos_n':oos.get('unique_episode_count',0),'oos_ev':oos.get('expected_value_pct'),'oos_pf':oos.get('profit_factor'),'oos_ev_ci_lower':oos.get('ev_ci_lower_pct'),'oos_ev_ci_upper':oos.get('ev_ci_upper_pct'),'oos_status':row.get('oos_status'),'negative_expectancy_status':row.get('negative_expectancy_status')})
 statistical_warnings=oos_data.get('warnings',[]) or ['OOS_VALIDATION_UNAVAILABLE']
 return {'status':'AVAILABLE','purpose':'RESEARCH_ONLY','market_memory_summary':{'total_snapshots':snaps[0],'completed_unique_episodes':unique,'date_range':[snaps[1],snaps[2]],'market_regimes_observed':regimes},'strategy_memory':strategies,'conditional_edges':edges,'anti_edges':anti,'current_candidate_memory':current,'fast_range_memory':fast,'oos_summary':oos_summary,'research_memory_statistical_warnings':statistical_warnings,'warnings':warnings}
def compact_for_chief(packet):
 r={'status':packet.get('status','RESEARCH_MEMORY_UNAVAILABLE'),'sample':{'unique_episodes':packet.get('market_memory_summary',{}).get('completed_unique_episodes',0),'snapshots':packet.get('market_memory_summary',{}).get('total_snapshots',0)},'strategy_context':packet.get('strategy_memory',[])[:5],'conditional_edge_observations':packet.get('conditional_edges',[])[:5],'current_candidate_analogs':packet.get('current_candidate_memory',[])[:10],'fast_range_candidates':packet.get('fast_range_memory',[])[:5],'oos_summary':packet.get('oos_summary',[])[:5],'research_memory_statistical_warnings':packet.get('research_memory_statistical_warnings',[]),'warnings':packet.get('warnings',[])}
 while len(json.dumps(r).encode())>15_000 and r['current_candidate_analogs']:r['current_candidate_analogs'].pop()
 return r
def run(db_path=None):
 db=connect(Path(db_path)) if db_path else connect();p=build(db);db.close();
 if len(json.dumps(p).encode())>MAX_BYTES:raise ValueError('AI Research Memory packet exceeds 150 KB')
 atomic_json(OUT,p);return p
def main():
 p=argparse.ArgumentParser();p.add_argument('--db');a=p.parse_args();r=run(a.db);print(OUT);print(f"Bytes: {len(json.dumps(r).encode())}")
if __name__=='__main__':main()
