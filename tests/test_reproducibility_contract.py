import copy
import json
import shutil
import sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from quant_research_v2.semantic_identity import (load_contract, configuration_identity,
                                                measurement_identity, logic_digest)


def definitions():
    return json.loads((ROOT/'config/paper_strategy_research_v1.json').read_text())


def test_reviewed_signal_definitions_and_trading_disabled():
    c = load_contract()
    assert c['observation_identity'] == 'PARENT_SETUP_V2'
    assert json.loads((ROOT/'config/quant_research_v2.json').read_text())['trading_capability'] == 'DISABLED'
    assert configuration_identity(definitions(), c, {}) == configuration_identity(definitions(), c, {})


def test_only_signal_semantics_change_configuration_identity():
    c = load_contract(); cfg = definitions(); original = configuration_identity(cfg, c, {})
    reordered = json.loads(json.dumps(cfg, sort_keys=True))
    assert configuration_identity(reordered, c, {}) == original
    changed = copy.deepcopy(c); changed['measurement']['contract_version'] = 'FUTURE_MEASUREMENT'
    assert configuration_identity(cfg, changed, {}) == original
    assert measurement_identity(changed) != measurement_identity(c)
    assert configuration_identity(cfg, c, {'HOME':'/different','TZ':'UTC','WEEKLY_SCAN_REQUEST_PAUSE':'9'}) == original
    assert configuration_identity(cfg, c, {'CONSOLIDATION_FRESH_HOURS':'9'}) != original
    changed = copy.deepcopy(cfg); changed['variants']['CONSOLIDATION_RANGE']['RANGE_FIXED_5']['target_pct'] = 6
    assert configuration_identity(changed, c, {}) != original
    changed = copy.deepcopy(c); changed['logic']['paper_setup_extractor']['version'] = 'REVIEWED_V2'
    assert configuration_identity(cfg, changed, {}) != original


def test_relocation_unrelated_files_and_source_review(tmp_path):
    c = load_contract()
    paths = ['config/reproducibility_contract_v1.json']
    paths += ['config/'+name for name in c['research_definitions']]
    paths += ['scripts/'+name+'.py' for name in c['logic']]
    for name in paths:
        p = tmp_path/name; p.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(ROOT/name, p)
    assert load_contract(tmp_path) == c
    (tmp_path/'scripts/unrelated_reporter.py').write_text('print("different output")\n')
    (tmp_path/'config/local_schedule.json').write_text('{"at":"tomorrow"}')
    assert load_contract(tmp_path) == c
    p = tmp_path/'scripts/paper_strategy_decision_engine.py'
    p.write_text('# formatting/comment-only edit\n'+p.read_text())
    assert load_contract(tmp_path) == c
    p.write_text(p.read_text().replace("'target_pct':4", "'target_pct':7"))
    with pytest.raises(ValueError, match='UNREVIEWED_SEMANTIC_SOURCE_CHANGE'): load_contract(tmp_path)


def test_ast_digest_tracks_referenced_constants_not_reporters(tmp_path):
    p=tmp_path/'logic.py'
    p.write_text('LIMIT=2\ndef signal(x):\n return x>LIMIT\ndef report():\n return "old"\n')
    first=logic_digest(p,['signal'])
    p.write_text(p.read_text().replace('old','new'))
    assert logic_digest(p,['signal'])==first
    p.write_text(p.read_text().replace('LIMIT=2','LIMIT=3'))
    assert logic_digest(p,['signal'])!=first
