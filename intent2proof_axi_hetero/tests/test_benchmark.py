import importlib.util,json,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def load(name):
    p=ROOT/'scripts'/name
    spec=importlib.util.spec_from_file_location(p.stem,p)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
# The architectural model uses dataclasses; register the module for resolving types.
import sys
spec=importlib.util.spec_from_file_location('architectural_model',ROOT/'scripts'/'architectural_model.py')
a=importlib.util.module_from_spec(spec);sys.modules[spec.name]=a;spec.loader.exec_module(a)
r=load('run_axi_sby.py');g=load('gate_axi.py')
class TestAXI(unittest.TestCase):
 def test_arch_safe(self):
    for n in (1,2,3,4):self.assertEqual(a.explore(n)['verdict'],'EXHAUSTIVE_SAFE')
 def test_mutant_shutdown(self):
    for n in (1,2,3,4):
      x=a.explore(n,'ignore_master1');self.assertEqual(x['verdict'],'VIOLATED');self.assertIn('reconfiguration_with',str(x['witness']['reason']))
 def test_mutant_route(self):
    for n in (1,2,3,4):
      x=a.explore(n,'wrong_owner');self.assertEqual(x['verdict'],'VIOLATED')
 def test_coverage(self):
    for n in (1,2,3,4):self.assertTrue(all(a.explore(n)['cover'].values()))
 def test_manifest_offline(self):
    with tempfile.TemporaryDirectory() as folder:
      w=Path(folder);rows=r.generate(w,'master',60,32,skip_git=True)
      self.assertEqual(len(rows),12)
      self.assertTrue(all(Path(x['sby']).exists() for x in rows))
      self.assertTrue(all('UPSTREAM' not in Path(x['bench']).read_text() for x in rows))
      m=json.loads((w/'manifest.json').read_text())
      self.assertEqual(m['proof_status'],'NOT_RUN')
      self.assertEqual(m['resolved_commit'],'UNFETCHED_OFFLINE')
 def test_sby_aliases(self):
    with tempfile.TemporaryDirectory() as folder:
      w=Path(folder);r.generate(w,'master',60,32,skip_git=True)
      s=(w/'axi_contended_full.sby').read_text()
      self.assertIn('read_verilog -sv axil_interconnect.v arbiter.v',s)
      self.assertIn('bench.v '+str(w/'axi_contended_full_bench.v'),s)
      self.assertIn('arbiter.v '+str(w/'upstream'/'rtl'/'arbiter.v'),s)
 def test_sby_mutants(self):
    x=r.build_bench('mutant_shutdown','contended');y=r.build_bench('mutant_route','separate')
    self.assertIn('.BAD_SHUTDOWN(1)',x)
    self.assertIn('.BAD_ROUTE(1)',y)
    self.assertIn('assert(mon0>0)',x)
 def test_no_old_preprocessor(self):
    self.assertNotIn('preprocess_formal_disabled', (ROOT/'scripts'/'run_axi_sby.py').read_text())
 def test_fail_closed_no_results(self):
    with tempfile.TemporaryDirectory() as folder:
      ok,info=g.assess(folder);self.assertFalse(ok);self.assertEqual(info['decision'],'REVIEW_REQUIRED')
 def test_candidate_never_approved_as_equivalence(self):
    with tempfile.TemporaryDirectory() as folder:
      w=Path(folder);r.generate(w,'master',60,32,skip_git=True)
      x=json.loads((w/'manifest.json').read_text());self.assertEqual(x['abstract_contract_status'],'CANDIDATE_ONLY_NO_TRACE_INCLUSION_PROOF')
 def test_upstream_source_is_not_included(self):
    self.assertFalse((ROOT/'rtl'/'axil_interconnect.v').is_file())
 def test_actual_bad_route_changes_rvalid(self):
    s=(ROOT/'rtl'/'axi_hetero_top.v').read_text()
    self.assertIn('delivered_rvalid = BAD_ROUTE ?',s)
    self.assertIn('interconnect_rready = BAD_ROUTE ?',s)
if __name__=='__main__':unittest.main()
