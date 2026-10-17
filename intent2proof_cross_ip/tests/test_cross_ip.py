import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def load(filename):
    spec=importlib.util.spec_from_file_location(filename,ROOT/'scripts'/f'{filename}.py')
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod

runner=load('run_cross_ip')
control=load('eval_control_model')

class CrossIPTests(unittest.TestCase):
    def test_pinned_source(self):
        runner.source_check()
    def test_eight_bit_and_sixteen_bit_parameters(self):
        assert 'LGFLEN' in (ROOT/'rtl/sfifo.v').read_text()
        self.assertIn('.LGFLEN(LGFLEN)',(ROOT/'rtl/cross_ip_top.v').read_text())
    def test_full_wrapper_exposes_data(self):
        w=runner.make_system_bench(2,8,'full')
        self.assertIn('output wire [7:0] debug_a,debug_b,debug_sink',w)
        self.assertIn('.BAD_SHUTDOWN(0)',w)
    def test_coi_wrapper_has_no_data_outputs(self):
        w=runner.make_system_bench(2,8,'coi')
        self.assertNotIn('output wire [7:0] debug_a',w)
        self.assertIn('assert(pending == sum_fill)',w)
    def test_contract_wrapper_is_count_only(self):
        w=runner.make_system_bench(3,8,'contract')
        self.assertIn('.USE_CONTRACT(1)',w)
        self.assertIn('assert(!reconfig_start || pending == 0)',w)
    def test_mutant_wrapper_has_same_property_and_mutation(self):
        w=runner.make_system_bench(3,8,'mutant')
        self.assertIn('.BAD_SHUTDOWN(1)',w)
        self.assertIn('assert(!reconfig_start || pending == 0)',w)
    def test_cover_engine_and_aliases(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)
            runner.create(path,20,30)
            cover=(path/'cross_LG2_BW8_cover.sby').read_text()
            self.assertIn('mode cover',cover)
            self.assertIn('smtbmc z3',cover)
            self.assertIn('read_verilog -formal -sv bench.v',cover)
            self.assertIn('bench.v '+str(path/'cross_LG2_BW8_cover_bench.v'),cover)
            self.assertIn('sfifo.v '+str(ROOT/'rtl'/'sfifo.v'),cover)
            manifest=json.loads((path/'manifest.json').read_text())
            self.assertEqual(len(manifest['generated']),18)
    def test_separate_unit_contract_is_not_only_an_assumption(self):
        w=runner.make_unit_bench(2,8)
        self.assertIn('sfifo #',w)
        self.assertIn('fifo_control_contract #',w)
        self.assertIn('assert(fill == rfill)',w)
        self.assertIn('assert(full == rf)',w)
        self.assertIn('assert(empty == re)',w)
    def test_bfs_correct_model_and_nonvacuity(self):
        a=control.explore(4)
        self.assertEqual(a['result'],'EXHAUSTIVE_SAFE')
        self.assertTrue(all(a['cover'].values()))
        self.assertGreater(a['reachable_states'],50)
    def test_bfs_mutant_counterexample(self):
        a=control.explore(4,True)
        self.assertEqual(a['result'],'VIOLATION')
        self.assertEqual(a['shortest_violation_transitions'],2)
        self.assertEqual(a['counterexample'][-1]['after_state'][-1],1)
    def test_gate_missing_result_is_fail_closed(self):
        gate=load('gate_cross_ip')
        with tempfile.TemporaryDirectory() as temp:
            x=gate.check(Path(temp))
            self.assertFalse(x['approved'])
            self.assertGreater(len(x['problems']),0)
    def test_gate_contract_depends_on_unit_obligation(self):
        gate=load('gate_cross_ip')
        import csv
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)
            manifest=runner.create(path,10,20)
            with (path/'benchmark.csv').open('w',newline='') as f:
                w=csv.DictWriter(f,['task','status']);w.writeheader()
                for a in manifest:
                    status=a['expected']
                    if a['mode']=='unit_contract' and a['lg']==2:status='UNKNOWN'
                    w.writerow({'task':a['task'],'status':status})
            result=gate.check(path)
            self.assertFalse(result['approved'])
            self.assertTrue(any('contract discharge missing' in p for p in result['problems']))

if __name__=='__main__':unittest.main()
