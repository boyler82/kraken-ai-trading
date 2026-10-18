from __future__ import annotations
import ast,hashlib,json,sys
from pathlib import Path
import pandas as pd,pytest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import resolve_range_fixed_5_v2_expired as resolver

def entry():
 return {'asset':'TEST','signal_id':'s','kraken_pair':'TESTUSD','entry_timestamp':'2026-01-01T00:30:00Z','entry_reference_price':100,'target_price':105,'stop_price':98,'expiry_timestamp':'2026-01-01T03:30:00Z','spread_pct':.1,'range_low':90,'range_high':110}
def write(path,rows):pd.DataFrame(rows,columns=['timestamp','open','high','low','close','volume']).to_csv(path,index=False)

def test_missing_interval_is_unresolved(tmp_path):
 write(tmp_path/'TESTUSD_1H.csv',[('2026-01-01T00:00:00Z',100,101,99,100,1),('2026-01-01T02:00:00Z',100,101,97,98,1)])
 result=resolver.preview_entry(entry(),tmp_path);assert result['data_coverage']['status']=='INSUFFICIENT_PUBLIC_MARKET_EVIDENCE';assert result['proposed_exit_reason'] is None

def test_entry_overlap_boundary_touch_requires_exact_evidence(tmp_path):
 write(tmp_path/'TESTUSD_1H.csv',[('2026-01-01T00:00:00Z',100,106,99,100,1),('2026-01-01T01:00:00Z',100,101,99,100,1),('2026-01-01T02:00:00Z',100,101,99,100,1)])
 result=resolver.preview_entry(entry(),tmp_path);assert result['data_coverage']['reason']=='ENTRY_OVERLAP_BOUNDARY_TOUCH_REQUIRES_EXACT_PUBLIC_TRADES'

@pytest.mark.archive
def test_repeated_production_preview_is_deterministic_and_read_only():
 db=resolver.DB_PATH;before=hashlib.sha256(db.read_bytes()).hexdigest();first=resolver.preview();second=resolver.preview();assert first==second and first['observation_count']==0;assert before==hashlib.sha256(db.read_bytes()).hexdigest()
 historical=json.loads((ROOT/'RESEARCH_REPORTS/range_fixed_5_v2_expired_preview_latest.json').read_text())
 assert historical['observation_count']==8 and historical['ready_count']==8 and historical['independent_signal_clusters']==1

@pytest.mark.archive
def test_frozen_hash_mismatch_aborts(monkeypatch):
 original=resolver.load_config();changed={**original,'target_pct':6};monkeypatch.setattr(resolver,'load_config',lambda:changed)
 with pytest.raises(ValueError,match='FROZEN_HASH_MISMATCH'):resolver.verify_frozen()

@pytest.mark.archive
def test_no_private_api_or_trading_capability():
 source=Path(resolver.__file__).read_text().lower();tree=ast.parse(source);assert '/private/' not in source and 'addorder' not in source and 'cancelorder' not in source
 assert resolver.preview()['trading_capability']=='DISABLED'
