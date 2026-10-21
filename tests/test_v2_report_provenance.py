"""Immutable event facts and append-only report provenance regressions."""
import json
import sqlite3
from copy import deepcopy
from datetime import timedelta
import pytest
from test_v2_parent_identity import prepare, ROOT
from paper_setup_extractor import SOURCES
from quant_research_v2.capture import capture, replay_event
from quant_research_v2.registry import Registry
from quant_research_v2.schemas import canonical, utc


@pytest.mark.parametrize('legacy_hashes', [True, False])
def test_pengu_legacy_report_regeneration_preserves_payload(legacy_hashes):
    old=json.loads((ROOT/'tests/fixtures/v2_identity/oct18_provenance.json').read_text())
    before=canonical(old)
    assert old['signal_id']=='v2p_0373b261890e415cede03754c402b860'
    new=deepcopy(old)
    if legacy_hashes:
        new['provenance']['source_digests']=['regenerated-report-digest']
    else:
        new['provenance'].pop('source_digests')
        new['provenance']['scan_link_contract']='APPEND_ONLY_SCAN_PROVENANCE_V1'
    later=(utc(old['observation_timestamp_utc'])+timedelta(seconds=30)).isoformat()
    new['observation_timestamp_utc']=later
    new['provenance']['retrieved_at_utc']=later
    assert canonical(replay_event(new,old))==before
    assert canonical(old)==before
    new['features']['values']['return_1h']+=1
    with pytest.raises(ValueError,match='IMMUTABLE_PAYLOAD_CONFLICT'):
        replay_event(new,old)
    assert canonical(old)==before

def test_reports_mature_without_mutating_events(tmp_path):
    at=prepare(tmp_path,'12'); registry=Registry(':memory:')
    with registry.db: capture(registry,tmp_path,at,at)
    original=registry.signals()
    assert all('source_digests' not in s['provenance'] for s in original)
    later=(utc(at)+timedelta(seconds=30)).isoformat()
    for path in SOURCES.values():
        p=tmp_path/path.relative_to(ROOT); report=json.loads(p.read_text())
        report['generated_at_utc']=later
        report['retrieval_note']='new scan, same closed candle'
        p.write_text(json.dumps(report))
    with registry.db: capture(registry,tmp_path,later,at)
    assert registry.signals()==original
    scans=registry.db.execute('select payload from scan_runs').fetchall()
    assert len(scans)==2
    assert all(len(json.loads(r[0])['source_digests'])==8 for r in scans)
    with registry.db: capture(registry,tmp_path,later,at)
    assert registry.db.execute('select count(*) from scan_runs').fetchone()[0]==2
    for sql in ['delete from scan_runs','update scan_runs set payload=payload','delete from sources','update sources set payload=payload']:
        with pytest.raises(sqlite3.IntegrityError,match='IMMUTABLE_(SCAN|SOURCE)_PROVENANCE'):
            with registry.db:registry.db.execute(sql)

def test_existing_source_corruption_fails_closed(tmp_path):
    import zlib
    from quant_research_v2.schemas import canonical,digest
    p=tmp_path/'corrupt.sqlite';value={'report':'original'}
    db=sqlite3.connect(p)
    db.execute('create table sources(id text primary key,payload blob not null)')
    db.execute('insert into sources values(?,?)',(digest(value),zlib.compress(canonical({'report':'changed'}).encode())))
    db.commit();db.close()
    registry=Registry(p)
    with pytest.raises(ValueError,match='IMMUTABLE_SOURCE_CONFLICT'),registry.db:
        registry.source(value)
    registry.close()
