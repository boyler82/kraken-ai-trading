import hashlib,json
from pathlib import Path
import scripts.run_paper_research_cycle as cycle
def test_dry_run_does_not_create_target_db(tmp_path,monkeypatch):
 monkeypatch.setattr(cycle,'load_reports',lambda:{'consolidation':{'candidates':[]},'momentum':{'candidates':[]},'rqi':{},'personality':{},'early_expansion':{},'relative_strength':{},'capital_flow':{},'rotation':{}});p=tmp_path/'db.sqlite';r=cycle.run('2026-08-10T07:00:00Z',True,db_path=p);assert r['status']=='SUCCESS' and not p.exists()
def test_main_pipeline_failure_is_fail_soft_source_contract():
 text=(Path(__file__).resolve().parents[1]/'scripts/run_complete_daily_research.py').read_text();assert 'PAPER_RESEARCH_UNAVAILABLE' in text and "if not ok:warnings.append" in text
def test_no_real_order_or_private_endpoint():
 root=Path(__file__).resolve().parents[1];text='\n'.join(p.read_text().lower() for p in (root/'scripts').glob('paper_*.py'));assert 'add_order' not in text and 'private endpoint' not in text
def test_production_artifacts_untouched_by_dry_run(tmp_path,monkeypatch):
 root=Path(__file__).resolve().parents[1];protected=list((root/'journal').glob('*.sqlite'))+[root/'scripts/consolidation_range_engine.py'];before={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in protected};monkeypatch.setattr(cycle,'load_reports',lambda:{'consolidation':{'candidates':[]},'momentum':{'candidates':[]},'rqi':{},'personality':{},'early_expansion':{},'relative_strength':{},'capital_flow':{},'rotation':{}});cycle.run('2026-08-10T07:00:00Z',True,db_path=tmp_path/'x.sqlite');assert before=={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
