#!/usr/bin/env python3
"""Source-anchored *one-step* SMT check of post-reset AR handshake.

Not a full-RTL proof. Only uses syntax-grounded, independently verified
ready-output equations; full RTL proof is performed by the prepared SBY miter.
"""
from __future__ import annotations
import ctypes, ctypes.util, hashlib, json, re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/'third_party/verilog-axi/rtl/axil_interconnect.v'
ABS=ROOT/'rtl/axi_read_contract_bridge.v'
OUT=ROOT/'results'

# Regexes deliberately strict: fail rather than invent a semantic translation.
def check_source_shape():
    raw=SRC.read_text();abstract=ABS.read_text()
    req=[(raw, r'reg\s*\[\s*S_COUNT\s*-\s*1\s*:\s*0\s*\]\s*s_axil_arready_reg\s*=\s*0', 'upstream registered ARREADY initialized zero'),
         (raw, r'assign\s+s_axil_arready\s*=\s*s_axil_arready_reg\s*;', 'upstream registered ready output'),
         (abstract, r'reg\s*\[1:0\]\s*state\s*=\s*0', 'abstract idle initial state'),
         (abstract, r'wire\s+active\s*=\s*s_arvalid\[0\]\s*\|\|\s*s_arvalid\[1\]', 'abstract active request detector'),
         (abstract, r'assign\s+s_arready\s*=\s*\(state==0\s*&&\s*active\)', 'abstract combinational ready output')]
    for source,pattern,comment in req:
        if not re.search(pattern,source): raise RuntimeError('Source shape changed: '+comment)
    return {'upstream_sha256':hashlib.sha256(SRC.read_bytes()).hexdigest(),
            'candidate_sha256':hashlib.sha256(ABS.read_bytes()).hexdigest(),
            'source_shape_checks':len(req)}

class Z3:
    def __init__(self):
        lib=ctypes.util.find_library('z3')
        if not lib: raise RuntimeError('libz3 unavailable: do not claim a solver result')
        z=ctypes.CDLL(lib)
        z.Z3_mk_config.restype=ctypes.c_void_p
        z.Z3_mk_context.argtypes=[ctypes.c_void_p];z.Z3_mk_context.restype=ctypes.c_void_p
        z.Z3_eval_smtlib2_string.argtypes=[ctypes.c_void_p,ctypes.c_char_p];z.Z3_eval_smtlib2_string.restype=ctypes.c_char_p
        z.Z3_del_context.argtypes=[ctypes.c_void_p];z.Z3_del_config.argtypes=[ctypes.c_void_p]
        self.z=z
    def run(self,source):
        z=self.z;c=z.Z3_mk_config();ctx=z.Z3_mk_context(c)
        try: s=z.Z3_eval_smtlib2_string(ctx,source.encode()).decode(errors='replace').strip()
        finally:z.Z3_del_context(ctx);z.Z3_del_config(c)
        status=s.splitlines()[0] if s else 'empty'
        if status not in ('sat','unsat','unknown'): raise RuntimeError('SMT solver error: '+s)
        return status,s

SMT_BASE='''(set-logic QF_BV)
; This is a source-grounded post-reset snapshot, not an RTL elaboration.
(declare-fun arvalid () (_ BitVec 2))
; Original: registered ARREADY, reset to zero and still zero at first sampled active cycle.
(define-fun real_ready () (_ BitVec 2) #b00)
; Candidate: idle=0; turn=0; combinational ready for request chosen at this cycle.
(define-fun abstract_ready () (_ BitVec 2)
    (ite (= arvalid #b00) #b00
         (ite (= ((_ extract 0 0) arvalid) #b1) #b01 #b10)))
(define-fun real_accept () (_ BitVec 2) (bvand arvalid real_ready))
(define-fun abstract_accept () (_ BitVec 2) (bvand arvalid abstract_ready))
(assert (not (= real_accept abstract_accept)))
'''

def check():
    info=check_source_shape();OUT.mkdir(parents=True,exist_ok=True)
    z=Z3();res=[]
    for label,valid,expect in [('single_master_0', '01','sat'),('two_master_contention','11','sat'),('no_requests','00','unsat')]:
        smt=SMT_BASE+f'(assert (= arvalid #b{valid}))\n(check-sat)\n'
        (OUT/f'{label}.smt2').write_text(smt)
        status,raw=z.run(smt)
        if status!=expect:raise AssertionError((label,expect,status))
        res.append({'scenario':label,'ARVALID':valid,'actual_ready':'00','candidate_ready': '01' if valid in ('01','11') else '00',
            'actual_accept':'00','candidate_accept':'01' if valid in ('01','11') else '00',
            'mismatch_satisfiable':status,'expected':expect})
    data={'experiment':'ONE_STEP_SOURCE_GROUNDED_CHECK_NOT_UPSTREAM_RTL_PROOF','scope':'post-reset ARREADY under explicitly described phase and 2-state inputs',
        'upstream_ref':'516bd5dadc3365b7f9e225d2af8fe0b8d804fe53',**info,'results':res}
    (OUT/'local_smt_checks.json').write_text(json.dumps(data,indent=2)+'\n')
    print(json.dumps(data,indent=2));return data
if __name__=='__main__':check()
