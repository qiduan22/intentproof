import sys,unittest,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import run_sby_v2 as runner
import check_local_snapshots as check

class TestAxilRefinementV2(unittest.TestCase):
    def test_pinned_upstream_hashes(self):
        self.assertEqual(runner.verify_sources(),runner.SOURCE_HASHES)
    def test_read_only_scope(self):
        v=(ROOT/'rtl/axi_read_control_miter_v2.v').read_text()
        self.assertIn('.s_axil_awvalid(2\'b0)',v)
        self.assertIn('.s_axil_wvalid(2\'b0)',v)
        self.assertIn('control_equal=',v)
        self.assertNotIn('real_s_rdata==',v)
    def test_v2_ready_is_registered(self):
        s=(ROOT/'rtl/axi_read_control_contract_v2.v').read_text()
        self.assertIn('assign s_arready=s_arready_reg;',s)
        self.assertIn('s_arready_next[selected_slave]=1\'b1;',s)
        self.assertNotIn('assign s_arready=(state_reg==',s)
    def test_arbiter_is_shared_and_pinned(self):
        s=(ROOT/'rtl/axi_read_control_contract_v2.v').read_text()
        self.assertIn('arbiter #(',s)
        self.assertIn('.ARB_BLOCK_ACK(1)',s)
        self.assertIn('grant[3] && s_rvalid_reg[1]',s)
    def test_response_retained_when_stalled(self):
        s=(ROOT/'rtl/axi_read_control_contract_v2.v').read_text()
        self.assertIn('s_rvalid_next=s_rvalid_reg & ~s_rready;',s)
    def test_negative_controls_are_real_mutations(self):
        orig=(ROOT/'rtl/axi_read_control_contract_v2.v').read_text()
        early=(ROOT/'rtl/axi_read_control_contract_v2_early_ready.v').read_text()
        drop=(ROOT/'rtl/axi_read_control_contract_v2_drop_stalled_response.v').read_text()
        self.assertEqual(early.count('assign s_arready=(state_reg==ST_IDLE'),1)
        self.assertEqual(drop.count("s_rvalid_next=2'b00;"),1)
        self.assertIn('module axi_read_control_contract_v2_early_ready',early)
        self.assertIn('module axi_read_control_contract_v2_drop_stalled_response',drop)
        self.assertNotIn("s_rvalid_next=2'b00;",orig)
    def test_task_coverage(self):
        self.assertEqual(len(runner.TASKS),12)
        self.assertEqual(len(runner.PROOFS),7)
        self.assertEqual(len(runner.COVERS),3)
        self.assertEqual(len(runner.MUTANTS),2)
    def test_all_sby_paths(self):
        tasks=runner.prepare(ROOT/'results/prepared_sby',300,80)
        self.assertEqual(len(tasks),12)
        for t in tasks:
            cfg=(ROOT/'results/prepared_sby'/t['sby']).read_text()
            self.assertIn('bench.v '+str((ROOT/'results/prepared_sby'/t['bench']).resolve()),cfg)
            self.assertIn('axil_interconnect.v '+str(runner.THIRD/'axil_interconnect.v'),cfg)
            self.assertIn('read_verilog -formal -sv bench.v',cfg)
            self.assertIn('prep -top axi_refinement_v2_formal_bench -flatten',cfg)
            self.assertNotIn('preprocess_formal_disabled',cfg)
            if t['name'] in runner.COVERS:self.assertIn('mode cover',cfg)
            else:self.assertIn('mode prove',cfg)
    def test_no_status_preapproved(self):
        p=ROOT/'results/prepared_sby/RUN_STATUS.json'
        result=json.loads(p.read_text())
        self.assertEqual(result['formal_tasks_executed'],0)
        self.assertEqual(result['contract_refinement'],'NOT_PROVED')
    def test_gate_fail_closed_on_any_miter_fail(self):
        rows=[{'name':n,'status':v[3],'engine':'abc pdr','has_witness':True} for n,v in runner.TASKS.items()]
        gate=runner.gate_results(rows)
        self.assertEqual(gate['scoped_control_cycle_equivalence'],'PROVED_UNDER_DECLARED_TEST_ASSUMPTIONS')
        self.assertEqual(gate['product_change_gate'],'REVIEW_REQUIRED_NO_AUTOMATIC_APPROVAL')
        rows[0]['status']='FAIL'
        self.assertEqual(runner.gate_results(rows)['scoped_control_cycle_equivalence'],'NOT_ESTABLISHED')
    def test_gate_fails_on_missing_cover_witness(self):
        rows=[{'name':n,'status':v[3],
               'engine':'abc pdr' if n in runner.PROOFS else 'smtbmc z3',
               'has_witness':n not in runner.COVERS or n!='cover_true_contention'} for n,v in runner.TASKS.items()]
        self.assertEqual(runner.gate_results(rows)['scoped_control_cycle_equivalence'],'NOT_ESTABLISHED')
    def test_missing_task_disqualifies(self):
        rows=[{'name':n,'status':v[3],'engine':'abc pdr','has_witness':True} for n,v in list(runner.TASKS.items())[:-1]]
        self.assertFalse(runner.gate_results(rows)['all_tasks_present'])
    def test_hash_tampering_is_detected(self):
        old=runner.SOURCE_HASHES['arbiter.v']
        try:
            runner.SOURCE_HASHES['arbiter.v']='f'*64
            with self.assertRaisesRegex(RuntimeError,'PIN_MISMATCH'):runner.verify_sources()
        finally:runner.SOURCE_HASHES['arbiter.v']=old
    def test_source_anchored_snapshot_checks(self):
        self.assertEqual(check.source_shape(),6)
        d=check.solve_snapshots()
        self.assertEqual(len(d['results']),7)
        self.assertTrue(all(r['expected']==r['observed'] for r in d['results']))

if __name__=='__main__':unittest.main()
