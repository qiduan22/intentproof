#!/usr/bin/env python3
"""Exhaustive ARCHITECTURAL AXI-Lite read-transaction model (NOT RTL elaboration).
Two masters submit address requests through a serial arbiter to either of two
slaves. Independent monitor credits track accepted/read-completed transactions.
The model distinguishes master pending, slave response latency and backpressure.
"""
from collections import deque
from dataclasses import dataclass, asdict
import argparse, csv, json
from pathlib import Path

@dataclass(frozen=True)
class State:
    req0: int = 0             # 0 none, 1 dest0, 2 dest1
    req1: int = 0
    turn: int = 0             # round-robin priority
    phase: int = 0            # 0 no active; 1 downstream wait; 2 response valid
    owner: int = 0
    dest: int = 0
    wait: int = 0
    shutdown: int = 0
    mon0: int = 0             # independent handshake-derived credits
    mon1: int = 0
    dut_busy0: int = 0        # separately-maintained DUT flags
    dut_busy1: int = 0
    reconfig: int = 0


def successors(s, *, wait_limit=2, mutant='none'):
    choices0 = (0,1,2) if not s.req0 and not s.dut_busy0 and not s.shutdown else (0,)
    choices1 = (0,1,2) if not s.req1 and not s.dut_busy1 and not s.shutdown else (0,)
    stops = (0,1) if not s.shutdown else (0,)
    advs = (0,1) if s.phase == 1 and s.wait < wait_limit else (1,)
    drains = (0,1) if s.phase == 2 else (0,)
    for new0 in choices0:
      for new1 in choices1:
       for stop in stops:
        # New requests are inhibited in the same cycle as the shutdown request.
        if stop and (new0 or new1):
            continue
        for adv in advs:
         for drain in drains:
          d=asdict(s);event=[]
          if new0: d['req0']=new0;event.append(f'master0_request_slave{new0-1}')
          if new1: d['req1']=new1;event.append(f'master1_request_slave{new1-1}')
          if stop: d['shutdown']=1;event.append('shutdown_request')
          if s.phase==0:
              waiting=[i for i in (0,1) if d[f'req{i}']>0]
              if waiting:
                  owner= s.turn if s.turn in waiting else waiting[0]
                  target=d[f'req{owner}']-1
                  d.update(phase=1,owner=owner,dest=target,wait=0,turn=1-owner)
                  d[f'req{owner}']=0
                  d[f'mon{owner}']+=1
                  d[f'dut_busy{owner}']=1
                  event.append(f'AR_accept_master{owner}_slave{target}')
          elif s.phase==1:
              if adv:
                  d.update(phase=2,wait=0)
                  event.append(f'slave{s.dest}_RVALID')
              else:
                  d['wait']=s.wait+1
                  event.append('slave_delay')
          elif s.phase==2:
              if drain:
                  owner=s.owner
                  delivery=1-owner if mutant=='wrong_owner' else owner
                  # External handshake monitor counts the actual response owner.
                  d[f'mon{delivery}']-=1
                  # The DUT internally releases the original request owner.
                  d[f'dut_busy{owner}']=0
                  d.update(phase=0,wait=0)
                  event.append(f'R_complete_to_master{delivery}')
              else:event.append('response_backpressure')
          # The DUT decides reconfiguration using its own bookkeeping,
          # while the assertion is evaluated against independent monitors.
          if d['shutdown']:
              if mutant=='ignore_master1':
                  quiescent=(d['req0']==0 and d['dut_busy0']==0)
              else:
                  quiescent=(d['req0']==0 and d['req1']==0
                             and d['dut_busy0']==0 and d['dut_busy1']==0)
              if quiescent and not d['reconfig']:
                  d['reconfig']=1;event.append('reconfiguration_start')
          nxt=State(**d)
          yield nxt, ','.join(event) or 'idle'


def violation(s):
    reasons=[]
    if s.mon0<0 or s.mon1<0:
        reasons.append('response_without_matching_accepted_address')
    if s.reconfig and (s.mon0 or s.mon1 or s.req0 or s.req1 or s.phase):
        reasons.append('reconfiguration_with_outstanding_or_pending_request')
    if s.dut_busy0 != s.mon0 or s.dut_busy1 != s.mon1:
        reasons.append('DUT_busy_disagrees_with_independent_monitor')
    return reasons


def explore(wait_limit, mutant='none', state_limit=250000):
    start=State(); paths={start:None}; prev={}; q=deque([start]); witness=None
    covers={k:False for k in ('simultaneous_requests','slave0_response','slave1_response','backpressure','shutdown_with_outstanding','safe_reconfig')}
    while q:
        s=q.popleft()
        if s.req0 and s.req1:covers['simultaneous_requests']=True
        if s.phase==2 and s.dest==0:covers['slave0_response']=True
        if s.phase==2 and s.dest==1:covers['slave1_response']=True
        if s.shutdown and (s.mon0 or s.mon1):covers['shutdown_with_outstanding']=True
        if s.reconfig and not(s.mon0 or s.mon1 or s.req0 or s.req1):covers['safe_reconfig']=True
        for nxt,ev in successors(s,wait_limit=wait_limit,mutant=mutant):
            if ev=='response_backpressure': covers['backpressure']=True
            if 'master0_request_' in ev and 'master1_request_' in ev: covers['simultaneous_requests']=True
            if nxt not in paths:
                paths[nxt]=len(paths)
                prev[nxt]=(s,ev)
                problems=violation(nxt)
                if problems and witness is None:
                    trace=[];t=nxt
                    while t!=start:
                        parent,event=prev[t]
                        trace.append({'event':event,'state':asdict(t),'violation':violation(t)})
                        t=parent
                    trace.reverse()
                    witness={'reason':problems,'transitions':len(trace),'trace':trace}
                    # stop early on first violation for mutant modes
                    if mutant!='none':
                        return {'wait_limit':wait_limit,'variant':mutant,'reachable_states_before_witness':len(paths), 'verdict':'VIOLATED', 'witness':witness,'cover':covers}
                q.append(nxt)
                if len(paths)>state_limit:
                    return {'wait_limit':wait_limit,'variant':mutant,'reachable_states':len(paths),'verdict':'INCONCLUSIVE_STATE_LIMIT','witness':witness,'cover':covers}
    return {'wait_limit':wait_limit,'variant':mutant,'reachable_states':len(paths),'verdict':'VIOLATED' if witness else 'EXHAUSTIVE_SAFE','witness':witness,'cover':covers}


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',default=str(Path(__file__).resolve().parents[1]/'results'));a=ap.parse_args();out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    results=[]
    for limit in (1,2,3,4):
        for variant in ('none','ignore_master1','wrong_owner'):
            r=explore(limit,variant)
            results.append(r);print(limit,variant,r['verdict'],r.get('reachable_states'),r.get('witness',{}).get('transitions') if r['witness'] else '-',flush=True)
    (out/'architectural_model.json').write_text(json.dumps({'scope':'purpose-built protocol-level transition model, NOT original RTL', 'results':results},indent=2)+'\n')
    with (out/'architectural_model.csv').open('w',newline='') as f:
        cols=['wait_limit','variant','verdict','reachable_states','reachable_states_before_witness','witness_depth']
        w=csv.DictWriter(f,cols);w.writeheader()
        for r in results:
            w.writerow({k:(r.get(k) if k!='witness_depth' else (r['witness']['transitions'] if r['witness'] else '')) for k in cols})
    good=[r for r in results if r['variant']=='none'];bad=[r for r in results if r['variant']!='none']
    assert all(r['verdict']=='EXHAUSTIVE_SAFE' for r in good)
    assert all(r['verdict']=='VIOLATED' for r in bad)
    assert all(all(x for x in r['cover'].values()) for r in good),good
if __name__=='__main__':main()
