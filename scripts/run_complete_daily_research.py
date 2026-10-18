from __future__ import annotations
import argparse,subprocess,sys,time
from pathlib import Path
from chatgpt_analysis_export import generate
from ai_chief_strategist_packet import generate as generate_chief
from ai_daily_observations import generate as generate_observations
from daily_decision_brief import generate as generate_decision_brief
from tactical_outcome_tracker import run as run_tactical_outcome_tracker
from run_modular_research_pipeline import run as run_modular
ROOT=Path(__file__).resolve().parents[1]
def generate_chief_artifacts(*args,**kwargs):
    """Keep the packet mapping and its canonical path distinct for their consumers."""
    return generate_chief(*args,**kwargs)
def call(args:list[str])->tuple[bool,str]:
    r=subprocess.run([sys.executable,*args],cwd=ROOT,capture_output=True,text=True);return r.returncode==0,(r.stderr or r.stdout).strip()
def run(objective='btc',current_holding='BTC',as_of=None,no_network=False,reuse=False,verbose=False,skip_existing_research=False,include_full=False,include_raw=False,use_portfolio=False):
    warnings=[];started=time.perf_counter()
    if use_portfolio:
        ok,msg=call(['scripts/import_portfolio_json.py'])
        if not ok:warnings.append(f'PORTFOLIO_CONTEXT_UNAVAILABLE: {msg}')
        held_data=['scripts/held_asset_market_data.py']
        if as_of:held_data += ['--as-of',as_of]
        if no_network or reuse:held_data += ['--no-network']
        ok,msg=call(held_data)
        if not ok:warnings.append(f'HELD_ASSET_DATA_INSUFFICIENT: {msg}')
    # Reuse mode consumes the existing research artifacts and must not mutate legacy state.
    if not skip_existing_research and not reuse:
        ok,msg=call(['scripts/run_research.py']);
        if not ok:warnings.append(f'research: {msg}')
    market=['scripts/run_daily_market_opportunity_scan.py'];rotation=['scripts/run_daily_rotation_analysis.py','--objective',objective,'--current-holding',current_holding]
    if as_of:market+=['--as-of',as_of];rotation+=['--as-of',as_of]
    if no_network:market+=['--no-network']
    if reuse:market+=['--reuse-existing-data'];rotation+=['--reuse-existing-data']
    if use_portfolio:rotation+=['--use-portfolio']
    for name,args in [('market',market)]:
        ok,msg=call(args)
        if not ok:warnings.append(f'{name}: {msg}')
    personality=['scripts/range_personality_engine.py']
    if as_of:personality+=['--as-of',as_of]
    if no_network:personality+=['--no-network']
    if reuse:personality+=['--reuse-existing-data']
    if verbose:personality+=['--verbose']
    ok,msg=call(personality)
    if not ok:warnings.append(f'range_personality: {msg}')
    rqi=['scripts/range_quality_index.py']
    if as_of:rqi+=['--as-of',as_of]
    if reuse:rqi+=['--reuse-existing-data']
    if verbose:rqi+=['--verbose']
    ok,msg=call(rqi)
    if not ok:warnings.append(f'range_quality_index: {msg}')
    ok,msg=call(rotation)
    if not ok:warnings.append(f'rotation: {msg}')
    modular=run_modular(as_of);warnings += [f'{k}: {v}' for k,v in modular['errors'].items()]
    expansion=['scripts/early_expansion_engine.py','--retrospective']
    if as_of:expansion+=['--as-of',as_of]
    if reuse:expansion+=['--reuse-existing-data']
    if verbose:expansion+=['--verbose']
    ok,msg=call(expansion)
    if not ok:warnings.append(f'early_expansion: {msg}')
    # Paper validation is isolated and fail-soft; current-market research remains successful if it fails.
    paper=['scripts/run_paper_research_cycle.py','--reuse-existing-data']
    if as_of:paper+=['--as-of',as_of]
    if verbose:paper+=['--verbose']
    ok,msg=call(paper)
    if not ok:warnings.append(f'PAPER_RESEARCH_UNAVAILABLE: {msg}')
    # Additive and fail-soft: memory consumes canonical outputs and never blocks the daily run.
    memory=['scripts/run_research_memory_cycle.py']
    if as_of:memory+=['--as-of',as_of]
    if use_portfolio:memory+=['--use-portfolio']
    ok,msg=call(memory)
    if not ok:warnings.append(f'RESEARCH_MEMORY_UNAVAILABLE: {msg}')
    # OOS statistics are additive, research-only, and independently fail-soft.
    ok,msg=call(['scripts/analyze_oos_performance.py'])
    if not ok:warnings.append(f'OOS_VALIDATION_UNAVAILABLE: {msg}')
    else:
        ok,msg=call(['scripts/build_ai_research_memory_packet.py'])
        if not ok:warnings.append(f'AI_RESEARCH_MEMORY_PACKET_UNAVAILABLE: {msg}')
    capital=['scripts/capital_efficiency_engine.py']
    if as_of:capital += ['--as-of',as_of]
    if use_portfolio:capital += ['--use-portfolio']
    ok,msg=call(capital)
    if not ok:warnings.append(f'CAPITAL_EFFICIENCY_UNAVAILABLE: {msg}')
    packet=None;latest=full=chief=observations=decision_brief=tactical_outcomes=None
    try:packet,latest,full=generate(objective,current_holding,as_of,True,include_raw,use_portfolio)
    except Exception as exc:warnings.append(f'export: {exc}')
    try:
        # Preliminary packet is the canonical current input for the journal.
        chief,chief_path=generate_chief_artifacts(objective,current_holding,as_of,use_portfolio,not no_network)
        _,observations=generate_observations(chief_path,None,as_of,verbose)
        # Final packet embeds only the compact same-date observation summary.
        chief,_=generate_chief_artifacts(objective,current_holding,as_of,use_portfolio,not no_network)
    except Exception as exc:warnings.append(f'chief_strategist_or_observations: {exc}')
    try:
        if chief is not None:_,tactical_outcomes=run_tactical_outcome_tracker(chief,as_of)
    except Exception as exc:warnings.append(f'TACTICAL_OUTCOME_TRACKER_UNAVAILABLE: {exc}')
    try:
        if chief is not None:_,decision_brief=generate_decision_brief(chief,as_of)
    except Exception as exc:warnings.append(f'DECISION_BRIEF_UNAVAILABLE: {exc}')
    return {'success':chief is not None,'warnings':warnings,'modules':modular,'latest':latest,'full':full,'chief':chief,'daily_observations':observations,'decision_brief':decision_brief,'tactical_outcomes':tactical_outcomes,'freshness':'FRESH' if packet and any(v=='OK' for v in packet['run_status'].values()) else 'UNAVAILABLE','runtime':time.perf_counter()-started}
def main():
    p=argparse.ArgumentParser();p.add_argument('--objective',choices=['btc','usd'],default='btc');p.add_argument('--current-holding',default='BTC');p.add_argument('--as-of');p.add_argument('--no-network',action='store_true');p.add_argument('--reuse-existing-data',action='store_true');p.add_argument('--verbose',action='store_true');p.add_argument('--skip-existing-research',action='store_true');p.add_argument('--include-full-bundle',action='store_true');p.add_argument('--include-raw-features',action='store_true');p.add_argument('--use-portfolio',action='store_true');a=p.parse_args();r=run(a.objective,a.current_holding,a.as_of,a.no_network,a.reuse_existing_data,a.verbose,a.skip_existing_research,a.include_full_bundle,a.include_raw_features,a.use_portfolio);state='SUCCESS_WITH_WARNINGS' if r['success'] and r['warnings'] else 'SUCCESS' if r['success'] else 'FAIL';print(f'DAILY RESEARCH: {state}');print(f"Mode: {'PORTFOLIO' if a.use_portfolio else 'MARKET_ONLY'}");print(f"Modules: {r['modules']['succeeded']}/{r['modules']['total']}");print(f"Freshness: {r['freshness']}");print(f"Chief Strategist packet:\n{r['chief']}");print(f"Daily observations:\n{r['daily_observations']}");print(f"Daily decision brief:\n{r['decision_brief']}");print('Upload this file to ChatGPT.')
if __name__=='__main__':main()
