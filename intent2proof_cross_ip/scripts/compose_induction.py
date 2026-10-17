#!/usr/bin/env python3
"""Contract-composition SMT obligations, checked through native libz3.

Proves one-step inductiveness of global FIFO occupancy conservation, the
local step capacity obligations, and safety of reconfiguration under the
contracts. Checks deliberate bad shutdown as a SAT negative control.
This is an abstract control-contract proof, not a proof of RTL binding.
"""
import csv,json,time
from pathlib import Path
from eval_z3_bmc import Z3,B,Eq,Not,And,Or,Add,I,Zext
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'results'/'composition';OUT.mkdir(parents=True,exist_ok=True)

def create(lg,kind):
    assert kind in ('conservation','capacity','shutdown_safe','shutdown_mutant')
    n=lg+1; mw=lg+3; cap=1<<lg
    ns=['a','b','s'];decl=[]
    for x in ns:decl.append(f'(declare-fun f{x} () (_ BitVec {n}))')
    decl.append(f'(declare-fun pending () (_ BitVec {mw}))')
    for x in ('reqa','reqb','drain','shutdown','latched','priority_b'):decl.append(f'(declare-fun {x} () Bool)')
    f=['fa','fb','fs'];
    full=[Eq(v,B(cap,n)) for v in f];empty=[Eq(v,B(0,n)) for v in f]
    wa=And('reqa',Not('shutdown'),Not('latched'),Not(full[0]))
    wb=And('reqb',Not('shutdown'),Not('latched'),Not(full[1]))
    ta=And(Not(empty[0]),Or(empty[1],Not('priority_b')),Not(full[2]))
    tb=And(Not(empty[1]),Or(empty[0],'priority_b'),Not(full[2]))
    wrsink=Or(ta,tb);deliver=And('drain',Not(empty[2]))
    nextf=[Add(f[j],I(w,B(1,n),B(0,n)), f'(bvneg {I(r,B(1,n),B(0,n))})') for j,(w,r) in enumerate(((wa,ta),(wb,tb),(wrsink,deliver)))]
    npending=Add('pending',I(wa,B(1,mw),B(0,mw)),I(wb,B(1,mw),B(0,mw)),f'(bvneg {I(deliver,B(1,mw),B(0,mw))})')
    asm=[Eq('pending',Add(*(Zext(v,2) for v in f)))]
    asm += [f'(bvule {v} {B(cap,n)})' for v in f]
    if kind=='conservation':violation=Not(Eq(npending,Add(*(Zext(x,2) for x in nextf))))
    elif kind=='capacity':violation=Or(*(Not(f'(bvule {v} {B(cap,n)})') for v in nextf))
    elif kind=='shutdown_safe':violation=And('latched',*empty,Not(Eq('pending',B(0,mw))))
    else:violation=And('latched',empty[0],empty[1],Not(Eq('pending',B(0,mw))))
    code='\n'.join(['(set-logic QF_BV)']+decl+[f'(assert {s})' for s in asm]+['(assert '+violation+')','(check-sat)'])+'\n'
    return code

def main():
    z=Z3();rows=[]
    for lg in (2,3,4):
        for kind in ('conservation','capacity','shutdown_safe','shutdown_mutant'):
            s=create(lg,kind);result,seconds=z.run(s)
            expected='sat' if kind=='shutdown_mutant' else 'unsat'
            assert result==expected,(lg,kind,result)
            key=f'D{1<<lg}_{kind}'
            (OUT/f'{key}.smt2').write_text(s)
            rows.append({'capacity':1<<lg,'obligation':kind,'solver_status':result,'expected':expected,'seconds':round(seconds,6),'smt_bytes':len(s)})
            print(key,result,round(seconds,5),flush=True)
    with (OUT/'composition.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,rows[0]);w.writeheader();w.writerows(rows)
    (OUT/'composition.json').write_text(json.dumps({'scope':'contract-level, source-derived control relations + custom arbiter/shutdown equations; not verified against integration RTL yet','rows':rows},indent=2)+'\n')
if __name__=='__main__':main()
