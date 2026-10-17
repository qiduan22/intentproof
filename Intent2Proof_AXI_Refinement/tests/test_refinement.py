import sys, unittest, json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import run_refinement as r
import local_source_semantics as local

class TestRefinement(unittest.TestCase):
    def test_source_pin(self):
        self.assertEqual(r.verify_sources(),r.SHA)
    def test_original_register_and_abstract_comb(self):
        info=local.check_source_shape();self.assertEqual(info['source_shape_checks'],5)
    def test_expected_non_equivalence_is_fail(self):
        self.assertEqual(r.TASKS['miter_single_req'][-1],'FAIL')
        self.assertEqual(r.TASKS['miter_dual_req'][-1],'FAIL')
    def test_source_width_corrected(self):
        s=(ROOT/'rtl/axi_hetero_top.v').read_text()
        self.assertIn('wire [3:0] s_rresp;',s)
    def test_sby_paths_present(self):
        tasks=r.prepare(ROOT/'results/prepared_sby',180,80)
        self.assertEqual(len(tasks),8)
        for t in tasks:
            cfg=(ROOT/'results/prepared_sby'/t['sby']).read_text()
            self.assertIn('axil_interconnect.v '+str(r.THIRD/'axil_interconnect.v'),cfg)
            self.assertIn('bench.v '+str(ROOT/'results/prepared_sby'/t['bench']),cfg)
            self.assertIn('prep -top ',cfg)
            self.assertNotIn('preprocess_formal_disabled',cfg)
    def test_tasks_have_expected_cover_modes(self):
        self.assertEqual(r.TASKS['shared_contention_cover'][3],'PASS')
        self.assertEqual(r.TASKS['shared_route_mutant'][3],'FAIL')
        self.assertIn('cover(saw_both_pending && saw_ar0 && saw_ar1 && saw_r0 && saw_r1);',
            (ROOT/'rtl/axi_shared_contention_formal_bench.v').read_text())
    def test_no_false_approval_even_if_expected_results(self):
        rows=[{'name':key,'status':expected,'has_witness':True} for key,(_,_,_,expected) in r.TASKS.items()]
        gate=r.summary_gate(rows)
        self.assertEqual(gate['harness_result'],'EXPECTED_COUNTEREXAMPLE_AND_COVERAGE_OBSERVED')
        self.assertEqual(gate['contract_cycle_equivalence'],'REJECTED')
        self.assertEqual(gate['formal_change_gate'],'REVIEW_REQUIRED_NO_AUTOMATIC_APPROVAL')
        self.assertEqual(gate['contract_trace_inclusion'],'NOT_PROVED')
    def test_missing_witness_rejected(self):
        rows=[{'name':key,'status':expected,'has_witness':expected!='FAIL'} for key,(_,_,_,expected) in r.TASKS.items()]
        gate=r.summary_gate(rows)
        self.assertEqual(gate['harness_result'],'INCOMPLETE_OR_UNEXPECTED')
    def test_misreported_proof_rejected(self):
        rows=[{'name':key,'status':'PASS','has_witness':False} for key in r.TASKS]
        gate=r.summary_gate(rows)
        self.assertEqual(gate['contract_trace_inclusion'],'NOT_PROVED')
        self.assertEqual(gate['formal_change_gate'],'REVIEW_REQUIRED_NO_AUTOMATIC_APPROVAL')
    def test_source_mismatch_rejected(self):
        original=r.SHA['axil_interconnect.v']
        try:
            r.SHA['axil_interconnect.v']='0'*64
            with self.assertRaisesRegex(RuntimeError,'PIN_MISMATCH'):r.verify_sources()
        finally:r.SHA['axil_interconnect.v']=original

if __name__=='__main__':unittest.main()
