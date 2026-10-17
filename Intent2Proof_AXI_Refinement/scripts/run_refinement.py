#!/usr/bin/env python3
"""Generate and optionally execute pinned upstream RTL miter/coverage benchmark.
The expected miter FAIL rejects cycle-accurate equivalence; it is NOT proof of
full RTL contract soundness. All statuses are fail-closed.
"""
from __future__ import annotations
import argparse,csv,hashlib,json,shutil,subprocess,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
THIRD=ROOT/'third_party/verilog-axi/rtl'
RTL=ROOT/'rtl'
PIN='516bd5dadc3365b7f9e225d2af8fe0b8d804fe53'
SHA={
 'axil_interconnect.v':'f685b0861d4d7a93a8ce4a938589d57e5fdd186204dea32436828496e1426efe',
 'arbiter.v':'a001507c82843e36e133dea75491fc044f56660fac0aff0127cf3afec7f927e0',
 'priority_encoder.v':'df28220d95b47df349a72803a9751aad331eb8e1435416e8686d00572a974dd5'}
TASKS={
 'miter_single_req':('miter',0,0,'FAIL'),
 'miter_dual_req':('miter',0,1,'FAIL'),
 'miter_no_req_sanity':('miter',1,0,'PASS'),
 'miter_mismatch_cover':('miter',2,1,'PASS'),
 'shared_contention_cover':('shared',0,0,'PASS'),
 'shared_contention_safety':('shared',1,0,'PASS'),
 'shared_route_mutant':('shared',2,0,'FAIL'),
 'shared_shutdown_mutant':('shared',3,0,'FAIL'),
}
SOURCE=('axil_interconnect.v','arbiter.v','priority_encoder.v')
OTHER=('axi_hetero_top.v','axi_read_contract_bridge.v','axi_slow_read_slave.v','axi_read_bridge_miter.v')

def verify_sources():
    hashes={p:hashlib.sha256((THIRD/p).read_bytes()).hexdigest() for p in SOURCE}
    for name, digest in SHA.items():
        if hashes[name] != digest:raise RuntimeError(f'PIN_MISMATCH: {name}: {hashes[name]} expected {digest}')
    # Fix the known port-width issue: do not allow silent implicit resize.
    src=(RTL/'axi_hetero_top.v').read_text()
    if 'wire [3:0] s_rresp;' not in src or 'wire [1:0] s_rresp;' in src:raise RuntimeError('s_rresp width fix missing')
    return hashes

def generated_bench(kind,mode,dual):
    src=(RTL/('axi_refinement_formal_bench.v' if kind=='miter' else 'axi_shared_contention_formal_bench.v')).read_text()
    needle='parameter RUN_MODE=0'
    if src.count(needle)!=1:raise RuntimeError('Unexpected bench parameter declaration')
    src=src.replace(needle,f'parameter RUN_MODE={mode}',1)
    if kind=='miter':
        needle2='parameter DUAL_REQUEST=0'
        if src.count(needle2)!=1:raise RuntimeError('Unexpected DUAL_REQUEST declaration')
        src=src.replace(needle2,f'parameter DUAL_REQUEST={dual}',1)
    return src

def sby_config(bench,work,kind,mode,timeout,depth):
    cover = kind=='miter' and mode==2 or kind=='shared' and mode==0
    selected='cover' if cover else 'prove'
    engine='smtbmc z3' if cover else 'abc pdr'
    filenames=list(SOURCE)+list(OTHER)+[f'{bench.stem}.v']
    entries=[]
    for name in SOURCE:entries.append(f'{name} {THIRD/name}')
    for name in OTHER:entries.append(f'{name} {RTL/name}')
    entries.append(f'bench.v {bench}')
    return '\n'.join([
      '[options]',f'mode {selected}',f'depth {depth}',f'timeout {timeout}','',
      '[engines]',engine,'','[script]',
      'read_verilog -sv '+ ' '.join(SOURCE)+' '+ ' '.join(OTHER),
      'read_verilog -formal -sv bench.v',
      'prep -top '+('axi_refinement_formal_bench' if kind=='miter' else 'axi_shared_contention_formal_bench')+' -flatten',
      '','[files]',*entries,''])

def prepare(work,timeout,depth):
    hashes=verify_sources()
    work.mkdir(parents=True,exist_ok=True)
    tasks=[]
    for name,(kind,mode,dual,expected) in TASKS.items():
        bench=work/(name+'_bench.v');bench.write_text(generated_bench(kind,mode,dual))
        sby=work/(name+'.sby');sby.write_text(sby_config(bench,work,kind,mode,timeout,depth))
        tasks.append({'name':name,'kind':kind,'run_mode':mode,'dual_request':bool(dual),
                      'expected':expected,'bench':bench.name,'sby':sby.name})
    manifest={'experiment':'axi_refinement_and_true_contention','source_repository':'alexforencich/verilog-axi',
        'pinned_commit':PIN,'pinned_source_sha256':hashes,
        'formal_status':'NOT_RUN','contract_refinement':'NOT_QUALIFIED',
        'measurement_warning':'The miter checks cycle-accurate equivalence under matched exogenous inputs; it is not a general quantifier-alternating trace inclusion proof.',
        'tasks':tasks}
    (work/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return tasks

def summary_gate(rows):
    idx={x['name']:x for x in rows}
    expected_match=set(idx)==set(TASKS) and all(x.get('status')==TASKS[x['name']][3] for x in rows if x['name'] in TASKS)
    witness_ok=all((x['status']!='FAIL' or x['has_witness']) for x in rows)
    correct_core=all(idx.get(k,{}).get('status')=='PASS' for k in ['miter_no_req_sanity','miter_mismatch_cover','shared_contention_cover','shared_contention_safety']) and all(idx.get(k,{}).get('has_witness') for k in ['miter_mismatch_cover','shared_contention_cover'])
    miter_fails=all(idx.get(k,{}).get('status')=='FAIL' for k in ['miter_single_req','miter_dual_req'])
    ready=expected_match and witness_ok and correct_core and miter_fails
    return {'harness_result':'EXPECTED_COUNTEREXAMPLE_AND_COVERAGE_OBSERVED' if ready else 'INCOMPLETE_OR_UNEXPECTED',
            'contract_cycle_equivalence':'REJECTED' if ready else 'NOT_ESTABLISHED',
            'contract_trace_inclusion':'NOT_PROVED',
            'formal_change_gate':'REVIEW_REQUIRED_NO_AUTOMATIC_APPROVAL',
            'all_expected_task_statuses':expected_match,'all_fail_witnesses_present':witness_ok,
            'true_contention_cover_succeeded':idx.get('shared_contention_cover',{}).get('status')=='PASS' and bool(idx.get('shared_contention_cover',{}).get('has_witness')),
            'task_count':len(rows)}

def run(work,timeout,depth):
    tasks=prepare(work,timeout,depth)
    if not shutil.which('yosys') or not shutil.which('sby'):
        out={'status':'BLOCKED_MISSING_FORMAL_TOOLS','formal_proofs_executed':0,
             'contract_trace_inclusion':'NOT_PROVED','formal_change_gate':'REVIEW_REQUIRED_NO_AUTOMATIC_APPROVAL'}
        (work/'RUN_STATUS.json').write_text(json.dumps(out,indent=2)+'\n')
        return 3
    rows=[]
    for t in tasks:
        start=time.monotonic();path=work/t['name']
        try:
            proc=subprocess.run(['sby','-f','-d',str(path),str(work/t['sby'])],capture_output=True,text=True,timeout=timeout+45)
            rc=proc.returncode;log=proc.stdout+'\n'+proc.stderr
        except subprocess.TimeoutExpired as exc:rc=124;log=str(exc)
        (work/(t['name']+'.log')).write_text(log)
        status=(path/'status').read_text().strip().split()[0].upper() if (path/'status').exists() else 'MISSING'
        if rc==124:status='TIMEOUT'
        witness=any(path.rglob('*.vcd'))
        aig=path/'model/design_aiger.aig'
        latch=ands='';digest=''
        if aig.exists():
            digest=hashlib.sha256(aig.read_bytes()).hexdigest()
            with aig.open('rb') as f: hdr=f.readline().decode(errors='replace').split()
            if len(hdr)>=6 and hdr[0] in ('aig','aag'):latch,ands=hdr[3],hdr[5]
        row={'name':t['name'],'expected':t['expected'],'status':status,'has_witness':witness,
             'seconds':round(time.monotonic()-start,5),'returncode':rc,'aig_latches':latch,
             'aig_ands':ands,'aig_sha256':digest}
        rows.append(row);print(t['name'],status,'expected',t['expected'],'witness',witness,flush=True)
    with (work/'formal_results.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=rows[0].keys());writer.writeheader();writer.writerows(rows)
    gate=summary_gate(rows)
    (work/'RUN_STATUS.json').write_text(json.dumps({'status':'COMPLETE','gate':gate,'results':rows},indent=2)+'\n')
    manifest=json.loads((work/'manifest.json').read_text())
    manifest['formal_status']='COMPLETED';manifest['contract_refinement']=gate['contract_cycle_equivalence']
    (work/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return 0 if gate['harness_result']=='EXPECTED_COUNTEREXAMPLE_AND_COVERAGE_OBSERVED' else 2

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--work',default=str(ROOT/'results/github_sby'))
    p.add_argument('--timeout',type=int,default=180)
    p.add_argument('--depth',type=int,default=80)
    p.add_argument('--generate-only',action='store_true')
    a=p.parse_args();work=Path(a.work).resolve()
    if a.generate_only:
        t=prepare(work,a.timeout,a.depth)
        print('Generated',len(t),'pinned-RTL tasks (not executed)')
    else:raise SystemExit(run(work,a.timeout,a.depth))
if __name__=='__main__':main()
