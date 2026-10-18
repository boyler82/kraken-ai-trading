from __future__ import annotations
import argparse
from lib.research_memory import STATS,atomic_json,conditional_analysis,connect

def run(db_path=None):
 db=connect(db_path) if db_path else connect();rows=conditional_analysis(db);db.close()
 payload={'status':'OK','purpose':'RESEARCH_ONLY','analysis_levels':{'level_1':'single dimensions','level_2':'approved two-factor combinations with N>=10'},'cells':rows,'warnings':['MULTIPLE_TESTING_RISK','DATA_SNOOPING_RISK','CORRELATED_VARIANT_SAMPLE','POTENTIAL_EDGE_ONLY']}
 atomic_json(STATS/'latest_conditional_edges.json',payload);return payload
def main():
 p=argparse.ArgumentParser();p.add_argument('--db');a=p.parse_args();r=run(a.db);print(f"Conditional cells: {len(r['cells'])}")
if __name__=='__main__':main()
