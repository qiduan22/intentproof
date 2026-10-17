#!/usr/bin/env python3
"""Source-anchored, restricted one-step Z3 snapshots (NOT RTL equivalence)."""
import ctypes, ctypes.util, hashlib, json, re, shutil, subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results/local'
UP=ROOT/'third_party/verilog-axi/rtl/axil_interconnect.v'
V2=ROOT/'rtl/axi_read_control_contract_v2.v'
EARLY=ROOT/'rtl/axi_read_control_contract_v2_early_ready.v'
DROP=ROOT/'rtl/axi_read_control_contract_v2_drop_stalled_response.v'

def source_shape():
    original=UP.read_text();new=V2.read_text()
    patterns=[(original,r'reg\s*\[S_COUNT-1:0\]\s+s_axil_arready_reg\s*=\s*0', 'real registered ARREADY'),
        (original,r'assign\s+s_axil_arready\s*=\s*s_axil_arready_reg\s*;', 'real ready from register'),
        (new,r'assign\s+s_arready\s*=\s*s_arready_reg\s*;', 'v2 ready from register'),
        (new,r's_rvalid_next\s*=\s*s_rvalid_reg\s*&\s*~s_rready\s*;', 'v2 response retention'),
        (EARLY.read_text(),r'assign\s+s_arready\s*=\s*\(state_reg==ST_IDLE\s*&&', 'mutant early ready'),
        (DROP.read_text(),r's_rvalid_next\s*=\s*2\'b00\s*;', 'mutant dropping stalled response')]
    for txt,pat,why in patterns:
        if not re.search(pat,txt):raise RuntimeError('Cannot establish snapshot source shape: '+why)
    return len(patterns)

class Z3:
    def __init__(self):
        lib=ctypes.util.find_library('z3')
        if not lib:
            self.z=None
            self.cli=shutil.which('z3')
            if not self.cli:raise RuntimeError('No libz3 and no z3 executable; no local solver claims possible')
            return
        self.cli=None
        z=ctypes.CDLL(lib)
        z.Z3_mk_config.restype=ctypes.c_void_p
        z.Z3_mk_context.argtypes=[ctypes.c_void_p];z.Z3_mk_context.restype=ctypes.c_void_p
        z.Z3_eval_smtlib2_string.argtypes=[ctypes.c_void_p,ctypes.c_char_p]
        z.Z3_eval_smtlib2_string.restype=ctypes.c_char_p
        z.Z3_del_context.argtypes=[ctypes.c_void_p];z.Z3_del_config.argtypes=[ctypes.c_void_p]
        self.z=z
    def run(self,smt):
        if self.cli:
            p=subprocess.run([self.cli,'-in'],input=smt,text=True,capture_output=True,timeout=20)
            if p.returncode!=0:raise RuntimeError('Z3 CLI error: '+p.stderr)
            raw=p.stdout.strip();status=raw.splitlines()[0] if raw else 'empty'
            if status not in ['sat','unsat','unknown']:raise RuntimeError(raw)
            return status,raw
        z=self.z;config=z.Z3_mk_config();ctx=z.Z3_mk_context(config)
        try:res=z.Z3_eval_smtlib2_string(ctx,smt.encode()).decode(errors='replace').strip()
        finally:z.Z3_del_context(ctx);z.Z3_del_config(config)
        status=res.splitlines()[0] if res else 'empty'
        if status not in ['sat','unsat','unknown']:raise RuntimeError(res)
        return status,res

BASE='''(set-logic QF_BV)
(declare-fun arvalid () (_ BitVec 2))
(define-fun source_ready () (_ BitVec 2) #b00)
(define-fun contract_v2_ready () (_ BitVec 2) #b00)
(define-fun old_ready () (_ BitVec 2)
    (ite (= arvalid #b00) #b00
         (ite (= ((_ extract 0 0) arvalid) #b1) #b01 #b10)))
(define-fun source_accept () (_ BitVec 2) (bvand arvalid source_ready))
(define-fun v2_accept () (_ BitVec 2) (bvand arvalid contract_v2_ready))
(define-fun old_accept () (_ BitVec 2) (bvand arvalid old_ready))
'''

def solve_snapshots():
    shape=source_shape();OUT.mkdir(parents=True,exist_ok=True)
    checker=Z3();out=[]
    tests=[
      ('no_request_fixed','00','v2_accept','unsat'),
      ('master0_fixed','01','v2_accept','unsat'),
      ('both_masters_fixed','11','v2_accept','unsat'),
      ('old_contract_master0_mismatch','01','old_accept','sat'),
      ('old_contract_dual_mismatch','11','old_accept','sat'),
    ]
    for name,req,contract,expected in tests:
        smt=BASE+f'(assert (= arvalid #b{req}))\n(assert (not (= source_accept {contract})))\n(check-sat)\n'
        (OUT/(name+'.smt2')).write_text(smt)
        status,_=checker.run(smt)
        if status!=expected:raise AssertionError((name,expected,status))
        out.append({'scenario':name,'scope':'first post-reset request opportunity',
          'expected':expected,'observed':status})
    # If response was valid and the receiver stalled, the next-cycle
    # ready/valid-based retention must preserve it.
    for name,cmp,expected in [
       ('v2_stalled_response_hold','v2_next_valid','unsat'),
       ('mutant_dropped_stalled_response','mutant_next_valid','sat')]:
        smt='''(set-logic QF_BV)
(declare-fun response_valid () Bool)
(declare-fun receiver_ready () Bool)
(define-fun real_next_valid () Bool (and response_valid (not receiver_ready)))
(define-fun v2_next_valid () Bool (and response_valid (not receiver_ready)))
(define-fun mutant_next_valid () Bool false)
(assert response_valid)
(assert (not receiver_ready))
'''+f'(assert (not (= real_next_valid {cmp})))\n(check-sat)\n'
        (OUT/(name+'.smt2')).write_text(smt)
        status,_=checker.run(smt)
        if status!=expected:raise AssertionError((name,expected,status))
        out.append({'scenario':name,'scope':'single-step held response while stalled',
             'expected':expected,'observed':status})
    data={'study':'SOURCE_GROUNDED_SNAPSHOT_CHECKS_NOT_RTL_EQUIVALENCE',
      'scope':'restricted one-step equations anchored by text-shape checks',
      'source_shape_checks':shape,
      'full_rtl_proof_executed_here':False,
      'upstream_file_sha256':hashlib.sha256(UP.read_bytes()).hexdigest(),
      'results':out}
    (OUT/'local_smt_results.json').write_text(json.dumps(data,indent=2)+'\n')
    return data
if __name__=='__main__':print(json.dumps(solve_snapshots(),indent=2))
