#!/usr/bin/env python3
"""Native libz3 bounded model checks of the cross-IP source-derived control system.

'augmented' retains source pointer bookkeeping; 'coi' retains the separate
empty flags, 'contract' uses only count summaries. NOT Yosys SBY timings.
"""
import ctypes,ctypes.util,csv,json,time,statistics
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results'/'model';OUT.mkdir(parents=True,exist_ok=True)

class Z3:
    def __init__(self):
        path=ctypes.util.find_library('z3')
        if not path:raise RuntimeError('native libz3 unavailable')
        self.path=path;self.z=ctypes.CDLL(path)
        self.z.Z3_mk_config.restype=ctypes.c_void_p
        self.z.Z3_mk_context.argtypes=[ctypes.c_void_p];self.z.Z3_mk_context.restype=ctypes.c_void_p
        self.z.Z3_eval_smtlib2_string.argtypes=[ctypes.c_void_p,ctypes.c_char_p];self.z.Z3_eval_smtlib2_string.restype=ctypes.c_char_p
        self.z.Z3_del_context.argtypes=[ctypes.c_void_p];self.z.Z3_del_config.argtypes=[ctypes.c_void_p]
    def run(self,s):
        cfg=self.z.Z3_mk_config();ctx=self.z.Z3_mk_context(cfg)
        t=time.perf_counter()
        try:msg=self.z.Z3_eval_smtlib2_string(ctx,s.encode()).decode(errors='replace').strip()
        finally:
            elapsed=time.perf_counter()-t
            self.z.Z3_del_context(ctx);self.z.Z3_del_config(cfg)
        outcome=msg.splitlines()[0]
        if outcome not in ('sat','unsat','unknown'):raise RuntimeError(msg[:1000])
        return outcome,elapsed

B=lambda n,w:f'(_ bv{n} {w})'
Eq=lambda a,b:f'(= {a} {b})'
Not=lambda a:f'(not {a})'
def And(*terms):return '(and '+' '.join(terms)+')'
def Or(*terms):return '(or '+' '.join(terms)+')'
def Add(*terms):return '(bvadd '+' '.join(terms)+')'
def I(p,y,n):return f'(ite {p} {y} {n})'
def Zext(v,bits):return f'((_ zero_extend {bits}) {v})'

def script(lg,mode='coi',mutant=False,k=12):
    assert mode in ('augmented','coi','contract')
    n=lg+1;monw=lg+3;cap=1<<lg
    count=('fa','fb','fs'); empty=('ea','eb','es'); ptr=('wpa','rpa','wpb','rpb','wps','rps')
    v=lambda key,t:f'{key}_{t}'
    o=['(set-logic QF_BV)','(set-option :timeout 4000)']
    for t in range(k+1):
        for item in count:o.append(f'(declare-fun {v(item,t)} () (_ BitVec {n}))')
        for item,width in [('pending',monw)]:o.append(f'(declare-fun {v(item,t)} () (_ BitVec {width}))')
        for item in ('priority_b','shutdown_latched'):o.append(f'(declare-fun {v(item,t)} () Bool)')
        if mode!='contract':
            for item in empty:o.append(f'(declare-fun {v(item,t)} () Bool)')
        if mode=='augmented':
            for item in ptr:o.append(f'(declare-fun {v(item,t)} () (_ BitVec {n}))')
        if t<k:
            for item in ('wr_a','wr_b','rd_sink','shutdown_request'):
                o.append(f'(declare-fun {v(item,t)} () Bool)')
    for item in count:o.append('(assert '+Eq(v(item,0),B(0,n))+')')
    o.append('(assert '+Eq(v('pending',0),B(0,monw))+')')
    for item in ('priority_b','shutdown_latched'):o.append('(assert (not '+v(item,0)+'))')
    if mode!='contract':
        for item in empty:o.append('(assert '+v(item,0)+')')
    if mode=='augmented':
        for item in ptr:o.append('(assert '+Eq(v(item,0),B(0,n))+')')
    badexpr=[]
    for t in range(k+1):
        f=[v(x,t) for x in count]
        emp=[v(x,t) if mode!='contract' else Eq(f[j],B(0,n)) for j,x in enumerate(empty)]
        pri=v('priority_b',t);latch=v('shutdown_latched',t);pending=v('pending',t)
        full=[Eq(f[j],B(cap,n)) for j in range(3)]
        summed=Add(*(Zext(x,2) for x in f))
        start=And(latch,emp[0],emp[1]) if mutant else And(latch,*emp)
        badexpr += [Not(Eq(pending,summed)),And(start,Not(Eq(pending,B(0,monw))))]
        if mode!='contract': badexpr += [Not(Eq(emp[j],Eq(f[j],B(0,n)))) for j in range(3)]
        if mode=='augmented':
            for j in range(3):badexpr.append(Not(Eq(f[j],f'(bvsub {v(ptr[j*2],t)} {v(ptr[j*2+1],t)})')))
        if t==k:continue
        wa,wb,rd,shut=[v(x,t) for x in ('wr_a','wr_b','rd_sink','shutdown_request')]
        a=And(wa,Not(shut),Not(latch),Not(full[0]))
        b=And(wb,Not(shut),Not(latch),Not(full[1]))
        ta=And(Not(emp[0]),Or(emp[1],Not(pri)),Not(full[2]))
        tb=And(Not(emp[1]),Or(emp[0],pri),Not(full[2]))
        transfer=Or(ta,tb);delivered=And(rd,Not(emp[2]))
        badexpr.append(And(ta,tb))
        writes=[a,b,transfer];reads=[ta,tb,delivered]
        for j in range(3):
            # arithmetic has finite-width bitvector semantics as upstream RTL
            newer=Add(f[j],I(writes[j],B(1,n),B(0,n)),f'(bvneg {I(reads[j],B(1,n),B(0,n))})')
            o.append('(assert '+Eq(v(count[j],t+1),newer)+')')
            if mode!='contract':
                # Upstream r_empty update: set false for write-only, when read-only
                # set (old occupancy <=1), otherwise hold.
                ex=I(And(writes[j],Not(reads[j])),'false',
                     I(And(reads[j],Not(writes[j])),
                       f'(bvule {f[j]} {B(1,n)})',emp[j]))
                o.append('(assert '+Eq(v(empty[j],t+1),ex)+')')
            if mode=='augmented':
                for pitem,enable in [(ptr[j*2],writes[j]),(ptr[j*2+1],reads[j])]:
                    o.append('(assert '+Eq(v(pitem,t+1),Add(v(pitem,t),I(enable,B(1,n),B(0,n))))+')')
        pending_new=Add(pending, I(a,B(1,monw),B(0,monw)),I(b,B(1,monw),B(0,monw)),f'(bvneg {I(delivered,B(1,monw),B(0,monw))})')
        o.append('(assert '+Eq(v('pending',t+1),pending_new)+')')
        o.append('(assert '+Eq(v('priority_b',t+1),I(transfer,ta,pri))+')')
        o.append('(assert '+Eq(v('shutdown_latched',t+1),Or(latch,shut))+')')
    o.append('(assert '+Or(*badexpr)+')')
    o.append('(check-sat)')
    return '\n'.join(o)+'\n'

def main():
    z=Z3();rows=[]
    for lg in (2,3,4):
        for k in (6,10):
            if k==10 and lg!=2: continue  # bounded 10-step solver stress case at depth 4 only
            for mode in ('augmented','coi','contract'):
                for mutant in (False,True):
                    source=script(lg,mode,mutant,k)
                    result,sec=z.run(source)
                    expected='sat' if mutant and k>=4 else 'unsat'
                    if result not in (expected,'unknown'):
                        raise AssertionError((lg,k,mode,mutant,result,expected))
                    rows.append({'depth':1<<lg,'bmc_bound':k,'encoding':mode,'variant':'mutant' if mutant else 'correct',
                                 'outcome':result,'seconds':round(sec,6),'smt_bytes':len(source),'smt_assertions':source.count('(assert ')})
                    print('D',1<<lg,'k',k,mode,'mut' if mutant else 'correct',result,round(sec,4),flush=True)
                    if lg==2 and k in (6,10):
                        (OUT/f'D{1<<lg}_{mode}_{"mutant" if mutant else "correct"}_k{k}.smt2').write_text(source)
    with (OUT/'z3_bmc.csv').open('w',newline='') as f:
        wr=csv.DictWriter(f,rows[0].keys());wr.writeheader();wr.writerows(rows)
    result={'library':z.path,'solver_scope':'source-derived control transition systems (not Yosys RTL proof)',
            'sample_size':len(rows),'summary':{str(m): {'k6_seconds':statistics.median(x['seconds'] for x in rows if x['encoding']==m and x['variant']=='correct' and x['bmc_bound']==6), 'k10_statuses': [x['outcome'] for x in rows if x['encoding']==m and x['variant']=='correct' and x['bmc_bound']==10]} for m in ('augmented','coi','contract')},
            'unknown_count':sum(x['outcome']=='unknown' for x in rows),'unexpected_outcomes':0}
    (OUT/'z3_summary.json').write_text(json.dumps(result,indent=2)+'\n')
if __name__=='__main__':main()
