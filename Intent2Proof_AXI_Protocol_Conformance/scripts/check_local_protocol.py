#!/usr/bin/env python3
"""Exhaustive *Python specification* checks for the protocol-aware slave policy.

THIS IS NOT RTL VERIFICATION. The script checks the intended control-state
semantics (including a deliberately incorrect response source) independently
of Yosys/SBY. The real RTL proof must be executed on GitHub Actions.
"""
import argparse
import csv
import itertools
import json
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# per-slave state (pending, rvalid, independent monitor pending)
IDLE = (0, 0, 0)


def per_slave_step(state, inputs, unsolicited=False):
    pending, registered_valid, monitor = state
    offer, accept_enable, issue_enable, resp_ready = inputs
    arready = (not pending) and accept_enable
    ar_fire = bool(offer and arready)
    rvalid = bool(registered_valid or (unsolicited and not pending))
    r_fire = bool(rvalid and resp_ready)
    violation = bool(rvalid and not monitor)
    next_pending = pending
    next_registered = registered_valid
    next_monitor = monitor
    if ar_fire:
        next_pending = next_monitor = 1
    if pending and not registered_valid and issue_enable:
        next_registered = 1
    if registered_valid and resp_ready:
        next_pending = next_monitor = next_registered = 0
    return (next_pending, next_registered, next_monitor), {
        'ar_fire': int(ar_fire), 'r_fire': int(r_fire),
        'rvalid': int(rvalid), 'protocol_violation': int(violation),
        'stall': int(rvalid and not resp_ready),
    }


def explore_states(num_slaves):
    start = tuple(IDLE for _ in range(num_slaves))
    todo = deque([start]); seen = {start}; transitions = 0
    while todo:
        curr = todo.popleft()
        for controls in itertools.product((0, 1), repeat=4 * num_slaves):
            next_state = []
            for j in range(num_slaves):
                s, event = per_slave_step(curr[j], controls[4*j:4*j+4])
                assert event['protocol_violation'] == 0, (curr, controls, j)
                assert not (event['r_fire'] and not curr[j][2])
                next_state.append(s)
            transitions += 1
            ns = tuple(next_state)
            if ns not in seen:
                seen.add(ns); todo.append(ns)
    return seen, transitions


def shortest_two_completed():
    # Single slave, two accepted and two completed downstream read transactions.
    # State includes counters capped at two, so BFS returns a minimum witness.
    initial = (IDLE, 0, 0)
    queue = deque([(initial, [])]); visited = {initial}
    while queue:
        (state, ac, co), trace = queue.popleft()
        if ac == 2 and co == 2:
            return trace
        for controls in itertools.product((0, 1), repeat=4):
            ns, event = per_slave_step(state, controls)
            nxt = (ns, min(2, ac + event['ar_fire']), min(2, co + event['r_fire']))
            if nxt not in visited:
                visited.add(nxt)
                frame = {'cycle': len(trace), 'pending_before': state[0],
                         'rvalid_before': state[1], 'monitor_before': state[2],
                         'offer_ar': controls[0], 'accept_enabled': controls[1],
                         'issue_enabled': controls[2], 'rready': controls[3],
                         'downstream_ar_accepted': event['ar_fire'],
                         'downstream_read_completed': event['r_fire'],
                         'accepted_total': nxt[1], 'completed_total': nxt[2]}
                queue.append((nxt, trace + [frame]))
    raise AssertionError('Two complete legal responses unreachable')


def evaluate():
    one, t1 = explore_states(1)
    two, t2 = explore_states(2)
    result_mut = per_slave_step(IDLE, (0, 0, 0, 0), unsolicited=True)[1]
    assert result_mut['protocol_violation'] == 1
    witness = shortest_two_completed()
    return {
        'test_scope': 'Python reference transition system; NOT compiled Verilog',
        'legal_one_slave_reachable_states': len(one),
        'legal_two_slave_reachable_states': len(two),
        'legal_one_slave_explored_input_transitions': t1,
        'legal_two_slave_explored_input_transitions': t2,
        'unsolicited_response_mutation_detected': True,
        'two_transaction_reachability_cycles': len(witness),
    }, witness


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--output', default=str(ROOT/'results/local'))
    args = ap.parse_args()
    output = Path(args.output); output.mkdir(parents=True, exist_ok=True)
    results, witness = evaluate()
    (output/'LOCAL_MODEL_STATUS.json').write_text(json.dumps(results, indent=2)+'\n')
    with (output/'two_transactions_reference_trace.csv').open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(witness[0]))
        writer.writeheader(); writer.writerows(witness)
    print(json.dumps(results, indent=2))

if __name__ == '__main__': main()
