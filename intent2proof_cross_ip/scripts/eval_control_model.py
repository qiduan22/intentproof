#!/usr/bin/env python3
"""Exhaustive, SOURCE-DERIVED control-equation composition.

Not an upstream RTL proof. Supports a three-FIFO merge/shutdown controller. The
FIFO control equations are transcribed from the pinned sfifo source; BMC and
exhaustive checks here are independent of the Yosys/ABC pipeline.
"""
import collections
import csv
import hashlib
import itertools
import json
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results'/'model'
OUT.mkdir(parents=True,exist_ok=True)
SOURCE_SHA='76a653781f1ecca1c1da92c4e5105ecd5d0f832b13cbfd31300ec88d9947e0c1'
assert hashlib.sha256((ROOT/'rtl'/'sfifo.v').read_bytes()).hexdigest()==SOURCE_SHA

# state: count_a, count_b, count_sink, empty_a, empty_b, empty_sink,
#        round_robin_priority_b, shutdown_latched, independent_pending
INIT=(0,0,0,True,True,True,False,False,0)
EVENTS=list(itertools.product((False,True),repeat=4))

def signals(s,inp,cap,bad=False):
    a,b,c,ea,eb,ec,turn,latch,pending=s
    wa,wb,rd,shutdown=inp
    accepted_a=wa and not shutdown and not latch and a!=cap
    accepted_b=wb and not shutdown and not latch and b!=cap
    p_a=not ea and (eb or not turn)
    p_b=not eb and (ea or turn)
    take_a=p_a and c!=cap
    take_b=p_b and c!=cap
    transfer=take_a or take_b
    delivered=rd and not ec
    start=latch and ea and eb and (bad or ec)
    return {'wa':accepted_a,'wb':accepted_b,'ta':take_a,'tb':take_b,
            'transfer':transfer,'deliver':delivered,'reconfig':start,
            'shutdown':shutdown,'latched':latch,'pending':pending}

def update(s,inp,cap):
    a,b,c,ea,eb,ec,turn,latch,pending=s
    si=signals(s,inp,cap)
    def step(n,e,w,r):
        n2=n+int(w)-int(r)
        # The actual upstream RTL has a separate registered empty flag.
        if w and not r: e2=False
        elif r and not w:e2=(n<=1)
        else:e2=e
        assert 0<=n2<=cap,(n,e,w,r,n2)
        assert e2 == (n2==0), (n,e,w,r,n2,e2)
        return n2,e2
    a2,ea2=step(a,ea,si['wa'],si['ta'])
    b2,eb2=step(b,eb,si['wb'],si['tb'])
    c2,ec2=step(c,ec,si['transfer'],si['deliver'])
    turn2=si['ta'] if si['transfer'] else turn
    return (a2,b2,c2,ea2,eb2,ec2,turn2,latch or si['shutdown'],
            pending+int(si['wa'])+int(si['wb'])-int(si['deliver']))

def explore(cap,bad=False):
    start=time.perf_counter()
    q=collections.deque([INIT]); visited={INIT}; parent={INIT:None};bad_state=None
    cover={'both_ingress_accepted':False,'occupied_shutdown':False,'reconfig_reached':False,'sink_occupied':False,'both_sources_nonempty':False}
    transfers=0
    while q:
        s=q.popleft()
        a,b,c,ea,eb,ec,turn,latch,pending=s
        assert pending==a+b+c,('global conservation',s)
        assert 0<=pending<=3*cap
        assert ea==(a==0) and eb==(b==0) and ec==(c==0)
        if latch and pending>0:cover['occupied_shutdown']=True
        if c>0:cover['sink_occupied']=True
        if a>0 and b>0:cover['both_sources_nonempty']=True
        # Reconfiguration start is a property of the CURRENT combinational state.
        cfg = latch and ea and eb and (bad or ec)
        if cfg:cover['reconfig_reached']=True
        if cfg and pending>0:
            bad_state=s;break
        for inp in EVENTS:
            ev=signals(s,inp,cap,bad)
            if ev['wa'] and ev['wb']:cover['both_ingress_accepted']=True
            assert not(ev['ta'] and ev['tb'])
            if ev['transfer']:transfers+=1
            s2=update(s,inp,cap)
            if s2 not in visited:
                visited.add(s2);parent[s2]=(s,inp);q.append(s2)
    path=[]
    if bad_state is not None:
        c=bad_state
        while parent[c] is not None:
            prev,inp=parent[c];path.append({'inputs':dict(zip(['wr_a','wr_b','rd_sink','shutdown_request'],map(int,inp))),
                                           'after_state':list(c)})
            c=prev
        path.reverse()
    sec=time.perf_counter()-start
    return {'capacity':cap,'variant':'mutant_omits_output_fifo' if bad else 'correct',
            'result':'VIOLATION' if bad_state is not None else 'EXHAUSTIVE_SAFE',
            'reachable_states':len(visited),'evaluated_transfers':transfers,
            'wall_seconds':round(sec,5),'shortest_violation_transitions':len(path) if bad else None,
            'cover':cover,'counterexample':path,
            'scope':'source-derived finite-state control equations; not full RTL elaboration'}

def main():
    results=[]
    for cap in (4,8,16):
        for mutant in (False,True):
            result=explore(cap,mutant)
            results.append(result)
            print(cap, result['variant'],result['result'],result['reachable_states'],'states',result['wall_seconds'],'sec')
            assert (result['result']=='VIOLATION')==mutant
    assert all(all(v for v in r['cover'].values()) for r in results if r['variant']=='correct')
    (OUT/'exhaustive.json').write_text(json.dumps(results,indent=2)+'\n')
    rows=[{k:x[k] for k in ('capacity','variant','result','reachable_states','wall_seconds','shortest_violation_transitions')} for x in results]
    with (OUT/'exhaustive.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,rows[0].keys());writer.writeheader();writer.writerows(rows)
    m={'source_sha':SOURCE_SHA, 'root':str(ROOT),'sampling':'one synchronous clock step per transition',
       'reset':'initial reset; asynchronous reset during execution returns to INIT and cannot increase reachability',
       'input_domain':'arbitrary per-cycle wr_a,wr_b,rd_sink,shutdown_request booleans',
       'all_explored_inputs':len(EVENTS), 'scope':'control equations transcribed from actual upstream RTL plus authored interconnect; not an elaboration proof'}
    (OUT/'assumptions.json').write_text(json.dumps(m,indent=2)+'\n')
if __name__=='__main__':main()
