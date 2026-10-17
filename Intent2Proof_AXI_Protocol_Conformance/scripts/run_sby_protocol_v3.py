#!/usr/bin/env python3
"""Pinned real-RTL AXI-Lite protocol-aware control-equivalence experiment.

Requires Yosys, SymbiYosys, ABC, and Z3 for execution.  The offline
--generate-only path never claims proofs.  All expected-failure mutations
must produce real VCD witnesses, and unknown/timeouts fail closed.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import shutil
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
THIRD = ROOT / 'third_party/verilog-axi/rtl'
RTL = ROOT / 'rtl'
PIN = '516bd5dadc3365b7f9e225d2af8fe0b8d804fe53'
SOURCE_HASHES = {
    'axil_interconnect.v': 'f685b0861d4d7a93a8ce4a938589d57e5fdd186204dea32436828496e1426efe',
    'arbiter.v': 'a001507c82843e36e133dea75491fc044f56660fac0aff0127cf3afec7f927e0',
    'priority_encoder.v': 'df28220d95b47df349a72803a9751aad331eb8e1435416e8686d00572a974dd5',
}
SOURCE = tuple(SOURCE_HASHES)
OTHER = (
    'axi_read_control_contract_v2.v',
    'axi_read_control_contract_v2_early_ready.v',
    'axi_read_control_contract_v2_drop_stalled_response.v',
    'axi_read_control_miter_v2.v',
    'axi_legal_read_slave_pair.v',
)
BENCH = RTL / 'axi_protocol_v3_formal_bench.v'
# name: mode, check_kind, contract_kind, slave_kind, expected_status
TASKS = {
    'prove_general_legal': (0, 0, 0, 0, 'PASS'),
    'prove_shared_legal': (1, 0, 0, 0, 'PASS'),
    'prove_distinct_legal': (2, 0, 0, 0, 'PASS'),
    'prove_unmapped_legal': (3, 0, 0, 0, 'PASS'),
    'prove_stall_legal': (4, 0, 0, 0, 'PASS'),
    'cover_shared_two_legal_completions': (5, 1, 0, 0, 'PASS'),
    'cover_legal_response_backpressure': (6, 1, 0, 0, 'PASS'),
    'cover_unmapped_without_slave': (7, 1, 0, 0, 'PASS'),
    'cover_distinct_slave_completions': (8, 1, 0, 0, 'PASS'),
    'mutant_early_ready_legal': (1, 0, 1, 0, 'FAIL'),
    'mutant_dropped_response_legal': (4, 0, 2, 0, 'FAIL'),
    'mutant_unsolicited_slave_response': (4, 2, 0, 1, 'FAIL'),
}
PROOFS = {k for k, (m, check, kind, slave, expect) in TASKS.items()
          if check == 0 and kind == 0 and slave == 0}
COVERS = {k for k, (m, check, kind, slave, expect) in TASKS.items() if check == 1}
MUTANTS = {k for k, (m, check, kind, slave, expect) in TASKS.items() if expect == 'FAIL'}


def sha256(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def verify_sources():
    actual = {name: sha256(THIRD / name) for name in SOURCE}
    for name, expected in SOURCE_HASHES.items():
        if actual[name] != expected:
            raise RuntimeError(f'PIN_MISMATCH {name}: {actual[name]} != {expected}')
    for name in OTHER:
        if not (RTL / name).is_file():
            raise RuntimeError(f'MISSING_RTL {name}')
    source = BENCH.read_text()
    for phrase in ('ds_ar_fire = real_m_arvalid & m_arready;',
                   'ds_r_fire = m_rvalid & real_m_rready;',
                   'assert(!m_rvalid[0] || monitor_pending[0]);',
                   'accepted_slave0>=2', 'responded_slave0>=2',
                   'saw_two_consecutive_stalls', 'cover(saw_unmapped_decerr'):
        if phrase not in source:
            raise RuntimeError(f'BENCH_MISSING_REQUIRED_CHECK {phrase}')
    slave = (RTL / 'axi_legal_read_slave_pair.v').read_text()
    for phrase in ('pending[0] && !rvalid_reg[0] && allow_respond[0]',
                   'rvalid_reg[0] && rready[0]',
                   'assign arready = (~pending)'):
        if phrase not in slave:
            raise RuntimeError(f'SLAVE_MISSING_REQUIRED_MECHANISM {phrase}')
    return actual


def generated_bench(mode, check, contract, slave):
    src = BENCH.read_text()
    for needle, replacement in [
        ('parameter MODE = 0,', f'parameter MODE = {mode},'),
        ('parameter CHECK_KIND = 0,', f'parameter CHECK_KIND = {check},'),
        ('parameter CONTRACT_KIND = 0,', f'parameter CONTRACT_KIND = {contract},'),
        ('parameter SLAVE_KIND = 0', f'parameter SLAVE_KIND = {slave}'),
    ]:
        if src.count(needle) != 1:
            raise RuntimeError(f'BENCH_PARAMETER_SUBSTITUTION_FAILED {needle}')
        src = src.replace(needle, replacement, 1)
    return src


def config_sby(bench, check, timeout, depth):
    cover = check == 1
    files = ([f'{name} {THIRD/name}' for name in SOURCE] +
             [f'{name} {RTL/name}' for name in OTHER] +
             [f'bench.v {bench}'])
    return '\n'.join([
        '[options]', f'mode {"cover" if cover else "prove"}',
        f'depth {depth}', f'timeout {timeout}', '',
        '[engines]', 'smtbmc z3' if cover else 'abc pdr', '',
        '[script]', f'read_verilog -sv {" ".join(SOURCE + OTHER)}',
        'read_verilog -formal -sv bench.v',
        'prep -top axi_protocol_v3_formal_bench -flatten', '',
        '[files]', *files, ''
    ])


def prepare(work: Path, timeout: int, depth: int):
    hashes = verify_sources()
    work.mkdir(parents=True, exist_ok=True)
    rows = []
    for name, (mode, check, contract, slave, expected) in TASKS.items():
        bench = (work / (name + '_bench.v')).resolve()
        bench.write_text(generated_bench(mode, check, contract, slave))
        sby = (work / (name + '.sby')).resolve()
        sby.write_text(config_sby(bench, check, timeout, depth))
        rows.append({'name': name, 'mode': mode, 'check_kind': check,
                     'contract_kind': contract, 'slave_kind': slave,
                     'expected': expected, 'sby': sby.name, 'bench': bench.name})
    manifest = {
        'experiment': 'Intent2Proof_AXI_protocol_aware_slave_v3',
        'source': 'alexforencich/verilog-axi', 'pinned_commit': PIN,
        'upstream_sha256': hashes, 'tool_execution': 'PREPARED_ONLY',
        'assumption_scope': 'read-only; two sources/two destinations; synchronously reset once;'
              ' at most one downstream outstanding per slave; response after AR handshake;'
              ' arbitrary downstream readiness/response delays; single clock;'
              ' abstraction receives the real-instance slave outputs',
        'claim_limitations': [
            'No full AXI4-Lite protocol certification',
            'No write-channel or RDATA equivalence',
            'One outstanding read per destination in the slave environment',
            'No liveness/fairness/response deadline proof',
            'No generic independent closed-system trace inclusion',
            'No automatic abstraction generation',
            'No benchmark speedup claim',
        ],
        'tasks': rows,
    }
    (work / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    (work / 'RUN_STATUS.json').write_text(json.dumps({
        'status': 'GENERATED_ONLY', 'executed_formal_tasks': 0,
        'protocol_legal_miter': 'NOT_PROVED',
        'contract_qualification': 'NOT_QUALIFIED',
        'change_gate': 'REVIEW_REQUIRED'
    }, indent=2) + '\n')
    return rows


def gate(rows):
    by_name = {r.get('name'): r for r in rows}
    complete = len(rows) == len(TASKS) and set(by_name) == set(TASKS)
    expected = complete and all(by_name[k]['status'] == task[-1]
                                for k, task in TASKS.items())
    unbounded = complete and all(by_name[k]['status'] == 'PASS' and
                                 by_name[k].get('pdr_proved') for k in PROOFS)
    covers = complete and all(by_name[k]['status'] == 'PASS' and
                              by_name[k].get('has_witness') for k in COVERS)
    mutants = complete and all(by_name[k]['status'] == 'FAIL' and
                               by_name[k].get('has_witness') for k in MUTANTS)
    qualified_scope = expected and unbounded and covers and mutants
    return {
        'status': 'COMPLETE_EXPECTED_OUTCOMES' if qualified_scope else 'INCOMPLETE_OR_UNEXPECTED',
        'all_tasks_present': complete,
        'all_expected_statuses': expected,
        'unbounded_pdr_proofs': unbounded,
        'legal_transaction_covers_have_witnesses': covers,
        'mutant_failures_have_witnesses': mutants,
        'scope_result': 'PROVED_UNDER_BENCH_ASSUMPTIONS' if qualified_scope else 'NOT_ESTABLISHED',
        'independently_composed_trace_inclusion': 'NOT_PROVED',
        'physical_or_payload_correctness': 'NOT_CHECKED',
        'product_change_gate': 'REVIEW_REQUIRED_NO_AUTOMATIC_APPROVAL',
    }


def read_status(task_dir):
    f = task_dir / 'status'
    if not f.is_file(): return 'MISSING'
    contents = f.read_text().strip().split()
    return contents[0].upper() if contents else 'MISSING'


def run(work, timeout, depth):
    tasks = prepare(work, timeout, depth)
    tools = {name: shutil.which(name) for name in ('yosys', 'sby', 'z3')}
    if not all(tools.values()):
        (work / 'RUN_STATUS.json').write_text(json.dumps({
            'status': 'BLOCKED_MISSING_TOOLS', 'tools': tools,
            'executed_formal_tasks': 0,
            'contract_qualification': 'NOT_QUALIFIED',
            'change_gate': 'REVIEW_REQUIRED',
        }, indent=2) + '\n')
        return 3
    rows = []
    for t in tasks:
        name = t['name']; task_dir = work / name
        started = time.monotonic()
        try:
            proc = subprocess.run(['sby', '-f', '-d', str(task_dir), str(work / t['sby'])],
                                  capture_output=True, text=True, timeout=timeout + 60)
            rc, stdout = proc.returncode, proc.stdout + '\n' + proc.stderr
        except subprocess.TimeoutExpired as exc:
            rc, stdout = 124, str(exc)
        (work / (name + '.log')).write_text(stdout)
        status = read_status(task_dir)
        if rc == 124: status = 'TIMEOUT'
        engine_log = task_dir / 'engine_0/logfile.txt'
        engine_text = engine_log.read_text(errors='replace') if engine_log.is_file() else ''
        pdr_proved = 'Property proved' in engine_text or 'Property proved' in stdout
        has_witness = any(task_dir.rglob('*.vcd'))
        aig = task_dir / 'model/design_aiger.aig'
        latches = and_gates = None
        if aig.is_file():
            with aig.open('rb') as f:
                parts = f.readline().decode(errors='replace').split()
            if len(parts) >= 6 and parts[0] in ('aig', 'aag'):
                latches, and_gates = int(parts[3]), int(parts[5])
        row = {'name': name, 'status': status, 'expected': t['expected'],
               'returncode': rc, 'elapsed_seconds': round(time.monotonic() - started, 4),
               'pdr_proved': bool(pdr_proved), 'has_witness': bool(has_witness),
               'aig_latches': latches, 'aig_and_gates': and_gates,
               'aig_sha256': sha256(aig) if aig.exists() else None}
        print(f'{name}: {status}; expected {t["expected"]}; '
              f'PDR proof={pdr_proved}; witness={has_witness}', flush=True)
        rows.append(row)
    with (work / 'task_results.csv').open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader(); writer.writerows(rows)
    decision = gate(rows)
    (work / 'RUN_STATUS.json').write_text(json.dumps({
        'status': 'EXECUTED', 'gate': decision, 'tasks': rows,
    }, indent=2) + '\n')
    manifest = json.loads((work / 'manifest.json').read_text())
    manifest['tool_execution'] = 'EXECUTED'
    (work / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return 0 if decision['status'] == 'COMPLETE_EXPECTED_OUTCOMES' else 2


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--work', default=str(ROOT / 'results/github_sby'))
    ap.add_argument('--timeout', type=int, default=450)
    ap.add_argument('--depth', type=int, default=100)
    ap.add_argument('--generate-only', action='store_true')
    opts = ap.parse_args()
    if opts.timeout < 1 or opts.depth < 1: ap.error('Positive timeout and depth required')
    work = Path(opts.work).resolve()
    if opts.generate_only:
        print('Generated', len(prepare(work, opts.timeout, opts.depth)),
              'SBY tasks (NOT RUN).')
    else:
        raise SystemExit(run(work, opts.timeout, opts.depth))


if __name__ == '__main__':
    main()
