from __future__ import annotations
import hashlib,json,sys
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import forward_validation_board as board
from strategy_evidence_audit import structure

def audit_row(name,digest,alias=None):
 return {'strategy_name':name,'strategy_family':'F','execution_definition_hash':digest,'alias_group':alias,'statistics':{'ev_pct':2},'cluster_aware_ci':{'lower_pct':1,'upper_pct':3},'major_warnings':[]}

@pytest.fixture(autouse=True)
def isolated_audit(tmp_path,monkeypatch):
 audit=tmp_path/'audit.json';audit.write_text(json.dumps({'strategies':[audit_row('S','a'*64)]}))
 for name,path in [('AUDIT_PATH',audit),('REGISTRY',tmp_path/'registry.json'),('BOARD_JSON',tmp_path/'board.json'),('BOARD_MD',tmp_path/'board.md')]:monkeypatch.setattr(board,name,path)


def spec():
 return {'signal_family':'F','entry_rule':'FIXED','entry_price_semantics':'NEXT_OBSERVATION','target':5,'stop':2,'max_hold_or_expiry':72,'exit_logic':'FIRST_HIT_OR_EXPIRY','fees':.4,'slippage':.2,'spread_semantics':'OBSERVED','universe_rules':'FROZEN','timeframe':'1H','regime_filters':None,'execution_assumptions':'PAPER','paper_only':True,'real_orders':False}

def registry(tmp_path):
 p=tmp_path/'registry.json';p.write_text(json.dumps({'entries':[{'strategy_name':'S','aliases':[],'execution_definition_hash':'a'*64,'alias_group':None,'governance_state':'CANDIDATE_FOR_FREEZE','frozen_at':None,'activated_at':None,'frozen_strategy_spec_hash':None,'forward_experiment_name':None,'validation_notes':[]}]}));return p

def test_aliases_counted_once():
 entries=board.initial_entries({'strategies':[audit_row('ONE','a'*64,'G'),audit_row('TWO','a'*64,'G')]})
 assert len(entries)==1 and entries[0]['aliases']==['TWO']

def test_deterministic_freeze_manifest_and_activated_immutability(tmp_path,monkeypatch):
 reg=registry(tmp_path);sp=tmp_path/'spec.json';sp.write_text(json.dumps(spec()));monkeypatch.setattr(board,'MANIFEST_DIR',tmp_path/'manifests')
 first=board.freeze('S',sp,reg);second=board.freeze('S',sp,reg)
 assert first['frozen_strategy_spec_hash']==second['frozen_strategy_spec_hash']
 data=json.loads(reg.read_text());data['entries'][0]['activated_at']='2026-01-01T00:00:00Z';reg.write_text(json.dumps(data));changed=spec();changed['target']=6;sp.write_text(json.dumps(changed))
 with pytest.raises(ValueError,match='immutable'):board.freeze('S',sp,reg)

def test_simultaneous_signals_raw_n_exceeds_clusters():
 rows=[{'setup_episode_id':str(i),'asset':str(i),'entry_timestamp':'t','market_data_timestamp':'t','cluster_timestamp':'t','net_return_pct':i} for i in range(8)]
 result=structure(rows);assert result['raw_episode_n']==8 and result['unique_signal_observation_clusters']==1

def test_insufficient_forward_evidence_and_no_historical_auto_promotion():
 entry=board.blank(audit_row('HIGH_HISTORICAL_EV','b'*64));entry['governance_state']='COLLECTING';policy=json.loads(board.GATES_PATH.read_text());board.apply_evaluation_state(entry,policy)
 assert entry['governance_state']=='COLLECTING' and entry['evidence_result']=='NOT_EVALUATED'

def test_evaluation_ready_does_not_auto_validate():
 entry=board.blank(audit_row('S','c'*64));entry.update(governance_state='COLLECTING',completed_outcomes=50,independent_signal_clusters=20,unique_market_data_timestamps=20,unique_assets=5,regime_coverage=['BEAR','BULL'],single_timestamp_ev_delta_pct=.1,single_asset_ev_delta_pct=.1,forward_clustered_ci_95=[.1,1])
 board.apply_evaluation_state(entry,json.loads(board.GATES_PATH.read_text()));assert entry['governance_state']=='EVALUATION_READY' and entry['evidence_result']=='PASS_FORWARD_EVIDENCE'

def test_v2_unchanged_no_private_api_trading_disabled_and_strict_json():
 paths=[ROOT/'config/range_fixed_5_forward_v2.json',ROOT/'config/range_fixed_5_forward_v2_phase4.json'];before=[hashlib.sha256(x.read_bytes()).hexdigest() for x in paths]
 board.refresh(registry_path=board.REGISTRY,audit_path=board.AUDIT_PATH);assert before==[hashlib.sha256(x.read_bytes()).hexdigest() for x in paths]
 source=Path(board.__file__).read_text().lower();assert '/private/' not in source and 'addorder' not in source and 'cancelorder' not in source
 payload=json.loads(board.REGISTRY.read_text(),parse_constant=lambda x:(_ for _ in()).throw(ValueError(x)));assert payload['trading_capability']=='DISABLED' and all(x['trading_capability']=='DISABLED' for x in payload['entries'])
