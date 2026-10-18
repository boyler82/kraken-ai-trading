import json,sys,unittest
from pathlib import Path
from tempfile import TemporaryDirectory
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from lib.research_module_contract import make_result,sanitize,validate_result,write_result
from lib.decision_registry import write_record
class ContractTests(unittest.TestCase):
 def test_contract_nan_utc_atomic(self):
  r=make_result('x','1','2026-01-01T00:00Z',freshness='FRESH',summary={'x':float('nan'),'y':float('inf')});self.assertEqual(validate_result(r),[]);self.assertIsNone(r['summary']['x']);self.assertIsNone(r['summary']['y'])
  with TemporaryDirectory() as d:p=Path(d)/'x.json';write_result(p,r);self.assertEqual(json.loads(p.read_text())['module_name'],'x')
