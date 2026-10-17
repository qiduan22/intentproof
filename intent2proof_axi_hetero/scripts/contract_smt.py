#!/usr/bin/env python3
"""Native Z3 one-step ASSUME/GUARANTEE obligations for architectural read contracts.
NOT proof that Alex Forencich's RTL satisfies the contracts.
"""
import ctypes,ctypes.util,csv,json,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'results';OUT.mkdir(exist_ok=True)

class Z3:
    def __init__(self):
        lib=ctypes.util.find_library('z3')
        if not lib:raise RuntimeError('libz3 missing')
        z=ctypes.CDLL(lib)
        z.Z3_mk_config.restype=ctypes.c_void_p
        z.Z3_mk_context.restype=ctypes.c_void_p
        z.Z3_mk_context.argtypes=[ctypes.c_void_p]
        z.Z3_eval_smtlib2_string.argtypes=[ctypes.c_void_p,ctypes.c_char_p]
        z.Z3_eval_smtlib2_string.restype=ctypes.c_char_p
        z.Z3_del_context.argtypes=[ctypes.c_void_p]
        z.Z3_del_config.argtypes=[ctypes.c_void_p]
        self.z=z
    def run(self,source):
        c=self.z.Z3_mk_config();ctx=self.z.Z3_mk_context(c);t=time.perf_counter()
        try:msg=self.z.Z3_eval_smtlib2_string(ctx,source.encode()).decode().strip()
        finally:
            seconds=time.perf_counter()-t
            self.z.Z3_del_context(ctx);self.z.Z3_del_config(c)
        result=msg.splitlines()[0] if msg else 'no result'
        if result not in ('unsat','sat','unknown'):raise ValueError('Solver error: '+msg)
        return result,seconds


def script(name):
    decl='\n'.join('(declare-fun '+x+' () Int)' for x in ('q0','q1','b0','b1','req0','req1','a0','a1','r0','r1'))
    asm=['(<= 0 q0 1)','(<= 0 q1 1)','(= q0 b0)','(= q1 b1)',
         '(<= 0 req0 1)','(<= 0 req1 1)',
         '(<= 0 a0 1)','(<= 0 a1 1)','(<= 0 r0 1)','(<= 0 r1 1)',
         '(<= (+ a0 a1) 1)','(<= (+ r0 r1) 1)',
         '(=> (= a0 1) (= q0 0))','(=> (= a1 1) (= q1 0))',
         '(=> (= r0 1) (= q0 1))','(=> (= r1 1) (= q1 1))',
         '(=> (= a0 1) (= r0 0))','(=> (= a1 1) (= r1 0))',
         '(=> (= (+ q0 q1) 1) (= (+ a0 a1) 0))']
    if name=='scoreboard_inductive':
        question='(or (not (= (+ q0 a0 (- r0)) (+ b0 a0 (- r0)))) (not (= (+ q1 a1 (- r1)) (+ b1 a1 (- r1)))))'
    elif name=='no_orphan_response':
        question='(or (and (= r0 1) (= q0 0)) (and (= r1 1) (= q1 0)))'
    elif name=='correct_shutdown':
        question='(and (= req0 0) (= req1 0) (= b0 0) (= b1 0) (> (+ q0 q1) 0))'
    elif name=='mutant_shutdown':
        question='(and (= req0 0) (= b0 0) (> (+ q0 q1) 0))'
    elif name=='mutant_response_owner':
        # Deliberately corrupted completion: q0=1 and response delivered to q1.
        question='(and (= q0 1) (= q1 0) (= r0 1))'
        # The bad implementation would decrement q1, producing -1.
    else:raise ValueError(name)
    return '\n'.join(['(set-logic QF_LIA)',decl]+['(assert '+x+')' for x in asm]+['(assert '+question+')','(check-sat)'])+'\n'

if __name__=='__main__':
    solver=Z3();rows=[];p=OUT/'smt';p.mkdir(exist_ok=True)
    for name,expected in [('scoreboard_inductive','unsat'),('no_orphan_response','unsat'),('correct_shutdown','unsat'),('mutant_shutdown','sat'),('mutant_response_owner','sat')]:
        s=script(name);(p/(name+'.smt2')).write_text(s)
        status,sec=solver.run(s)
        rows.append({'obligation':name,'expected':expected,'status':status,'seconds':sec})
        assert status==expected,(name,status,expected)
        print(name,status,round(sec,5),flush=True)
    (OUT/'contract_smt.json').write_text(json.dumps({'scope':'one-step abstract contracts, not original RTL','results':rows},indent=2)+'\n')
    with (OUT/'contract_smt.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,rows[0]);w.writeheader();w.writerows(rows)
