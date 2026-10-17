import sys
import json
import tempfile
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import check_local_protocol as local
import run_sby_protocol_v3 as runner

class ProtocolAwareV3(unittest.TestCase):
    def test_pinned_source_integrity(self):
        self.assertEqual(runner.verify_sources(), runner.SOURCE_HASHES)

    def test_upstream_is_unmodified_and_read_only_miter(self):
        m = (ROOT/'rtl/axi_read_control_miter_v2.v').read_text()
        self.assertIn(".s_axil_awvalid(2'b0)", m)
        self.assertIn(".s_axil_wvalid(2'b0)", m)
        self.assertIn('control_equal=', m)
        self.assertNotIn('real_s_rdata==', m)

    def test_slave_response_requires_previous_ar(self):
        s = (ROOT/'rtl/axi_legal_read_slave_pair.v').read_text()
        self.assertIn('if (arvalid[0] && arready[0])', s)
        self.assertIn('if (pending[0] && !rvalid_reg[0] && allow_respond[0])', s)
        self.assertIn('if (rvalid_reg[0] && rready[0])', s)
        self.assertIn('pending[0] <= 1\'b1;', s)
        self.assertIn('pending[0] <= 1\'b0;', s)
        self.assertIn("reg [1:0] rvalid_reg = 2'b00", s)

    def test_independent_downstream_scoreboard(self):
        b = (ROOT/'rtl/axi_protocol_v3_formal_bench.v').read_text()
        self.assertIn('ds_ar_fire = real_m_arvalid & m_arready', b)
        self.assertIn('ds_r_fire = m_rvalid & real_m_rready', b)
        self.assertIn('assert(!m_rvalid[0] || monitor_pending[0])', b)
        self.assertIn('assert(!m_rvalid[1] || monitor_pending[1])', b)

    def test_actual_downstream_events_required_for_contention_cover(self):
        b = (ROOT/'rtl/axi_protocol_v3_formal_bench.v').read_text()
        self.assertIn('accepted_slave0>=2', b)
        self.assertIn('responded_slave0>=2', b)
        self.assertIn('(&upstream_completed)', b)
        self.assertIn('saw_both_requested', b)

    def test_stall_cover_requires_consecutive_cycles(self):
        b = (ROOT/'rtl/axi_protocol_v3_formal_bench.v').read_text()
        self.assertIn('last_cycle_stall && real_rvalid[0] && !s_rready[0]', b)
        self.assertIn('last_cycle_stall <= real_rvalid[0] && !s_rready[0];', b)

    def test_unmapped_cover_forbids_downstream_accepts(self):
        b = (ROOT/'rtl/axi_protocol_v3_formal_bench.v').read_text()
        self.assertIn('saw_unmapped_decerr && accepted_slave0==0', b)
        self.assertIn('accepted_slave1==0 && upstream_accepted[0]', b)

    def test_task_matrix(self):
        self.assertEqual(len(runner.TASKS), 12)
        self.assertEqual(len(runner.PROOFS), 5)
        self.assertEqual(len(runner.COVERS), 4)
        self.assertEqual(len(runner.MUTANTS), 3)

    def test_sby_generated_and_wired_correctly(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d)
            rows = runner.prepare(out, 600, 120)
            for task in rows:
                sby = (out/task['sby']).read_text()
                bench = (out/task['bench']).read_text()
                self.assertIn(f'bench.v {str((out/task["bench"]).resolve())}', sby)
                self.assertIn('read_verilog -formal -sv bench.v', sby)
                self.assertIn('axi_legal_read_slave_pair.v', sby)
                self.assertIn('prep -top axi_protocol_v3_formal_bench -flatten', sby)
                self.assertNotIn('preprocess_formal_disabled', sby)
                self.assertIn(f'parameter MODE = {task["mode"]},', bench)
                if task['check_kind']==1:
                    self.assertIn('mode cover', sby)
                    self.assertIn('smtbmc z3', sby)
                else:
                    self.assertIn('mode prove', sby)
                    self.assertIn('abc pdr', sby)
            status = json.loads((out/'RUN_STATUS.json').read_text())
            self.assertEqual(status['status'],'GENERATED_ONLY')
            self.assertEqual(status['contract_qualification'],'NOT_QUALIFIED')

    def _ideal_results(self):
        return [{'name': n, 'status': k[-1],
                 'pdr_proved': n in runner.PROOFS,
                 'has_witness': n in runner.COVERS or n in runner.MUTANTS}
                for n,k in runner.TASKS.items()]

    def test_gate_fail_closed_missing_task(self):
        self.assertEqual(runner.gate(self._ideal_results()[:-1])['scope_result'],'NOT_ESTABLISHED')

    def test_gate_fail_closed_unknown(self):
        items = self._ideal_results()
        items[0]['status'] = 'UNKNOWN'
        self.assertEqual(runner.gate(items)['scope_result'],'NOT_ESTABLISHED')

    def test_gate_fail_closed_unproved_pdr(self):
        items = self._ideal_results()
        items[0]['pdr_proved'] = False
        self.assertEqual(runner.gate(items)['scope_result'],'NOT_ESTABLISHED')

    def test_gate_fail_closed_uncovered_contended_traffic(self):
        items = self._ideal_results()
        for x in items:
            if x['name']=='cover_shared_two_legal_completions':
                x['has_witness']=False
        self.assertEqual(runner.gate(items)['scope_result'],'NOT_ESTABLISHED')

    def test_gate_fail_closed_mutant_no_witness(self):
        items = self._ideal_results()
        for x in items:
            if x['name']=='mutant_unsolicited_slave_response':
                x['has_witness']=False
        self.assertEqual(runner.gate(items)['scope_result'],'NOT_ESTABLISHED')

    def test_positive_gate_never_claims_general_refinement(self):
        x = runner.gate(self._ideal_results())
        self.assertEqual(x['scope_result'],'PROVED_UNDER_BENCH_ASSUMPTIONS')
        self.assertEqual(x['independently_composed_trace_inclusion'],'NOT_PROVED')
        self.assertEqual(x['product_change_gate'],'REVIEW_REQUIRED_NO_AUTOMATIC_APPROVAL')

    def test_local_exhaustive_reference_safety(self):
        one, explored1 = local.explore_states(1)
        two, explored2 = local.explore_states(2)
        self.assertEqual((len(one), len(two)), (3,9))
        self.assertEqual((explored1,explored2),(48,2304))

    def test_local_invalid_slave_detected(self):
        next_state, output=local.per_slave_step(local.IDLE,(0,0,0,0),unsolicited=True)
        self.assertEqual(output['protocol_violation'],1)

    def test_local_two_legal_transactions_reachable(self):
        witness=local.shortest_two_completed()
        self.assertEqual(len(witness),6)
        self.assertEqual(sum(r['downstream_ar_accepted'] for r in witness),2)
        self.assertEqual(sum(r['downstream_read_completed'] for r in witness),2)

if __name__ == '__main__':
    unittest.main()
