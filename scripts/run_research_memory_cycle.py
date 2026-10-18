from __future__ import annotations
import argparse
from pathlib import Path
from ai_chief_strategist_packet import build
from analyze_coin_personality import run as personalities
from analyze_conditional_edge import run as conditional
from build_ai_research_memory_packet import run as packet
from lib.research_memory import capture_current_snapshots,connect,import_paper_outcomes,update_forward_outcomes

def run(as_of=None,db_path=None,use_portfolio=False):
 db=connect(Path(db_path)) if db_path else connect();chief=build('btc','BTC',as_of,None,use_portfolio);ts=chief['generated_at_utc'];run_id=chief['report_date'];inserted=capture_current_snapshots(db,ts,run_id,chief['candidates'],chief['market_state'],use_portfolio);forward=update_forward_outcomes(db,ts);imported=import_paper_outcomes(db);db.close();conditional(db_path);personalities(db_path);packet(db_path);return {'snapshots_inserted':inserted,'outcomes_imported':imported,'forward_rows_updated':forward}
def main():
 p=argparse.ArgumentParser();p.add_argument('--as-of');p.add_argument('--db');p.add_argument('--use-portfolio',action='store_true');a=p.parse_args();print(run(a.as_of,a.db,a.use_portfolio))
if __name__=='__main__':main()
