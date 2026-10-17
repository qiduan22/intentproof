#!/usr/bin/env python3
"""Fail-closed, pinned-RTL AXI read-control contract refinement benchmark.

An SBY PASS on equivalence tasks is necessary to qualify *only* the explicitly
observed read-control relation under the stated assumptions. A generated-only
manifest NEVER claims RTL proof.
"""
from __future__ import annotations
import argparse, csv, hashlib, json, shutil, subprocess, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
RTL=ROOT/'rtl'
THIRD=ROOT/'third_party/verilog-axi/rtl'
PIN='516bd5dadc3365b7f9e225d2af8fe0b8d804fe53'
SOURCE_HASHES={
 'axil_interconnect.v':'f685b0861d4d7a93a8ce4a938589d57e5fdd186204dea32436828496e1426efe',
 'arbiter.v':'a001507c82843e36e133dea75491fc044f56660fac0aff0127cf3afec7f927e0',
 'priority_encoder.v':'df28220d95b47df349a72803a9751aad331eb8e1435416e8686d00572a974dd5'}
SOURCE=tuple(SOURCE_HASHES)
OTHER=(
 'axi_read_control_contract_v2.v',
 'axi_read_control_contract_v2_early_ready.v',
 'axi_read_control_contract_v2_drop_stalled_response.v',
 'axi_read_control_miter_v2.v',
)
# id: (environment mode, contract kind, check kind, desired formal status)
TASKS={
 'prove_unconstrained_read':(0,0,0,'PASS'),
 'prove_master0_destination0':(1,0,0,'PASS'),
 'prove_true_shared_destination':(2,0,0,'PASS'),
 'prove_distinct_destinations':(3,0,0,'PASS'),
 'prove_unmapped_decerr':(4,0,0,'PASS'),
 'prove_response_backpressure':(5,0,0,'PASS'),
 'prove_reset_reentry':(6,0,0,'PASS'),
 'cover_true_contention':(7,0,1,'PASS'),
 'cover_response_stall':(8,0,1,'PASS'),
 'cover_unmapped_error':(9,0,1,'PASS'),
 'mutant_early_ready':(1,1,0,'FAIL'),
 'mutant_dropped_stalled_response':(8,2,0,'FAIL'),
}
PROOFS={k for k,(m,c,check,expected) in TASKS.items() if check==0 and c==0}
COVERS={k for k,(m,c,check,expected) in TASKS.items() if check==1}
MUTANTS={k for k,(m,c,check,expected) in TASKS.items() if c!=0}

def verify_sources():
    actual={name:hashlib.sha256((THIRD/name).read_bytes()).hexdigest() for name in SOURCE}
    for name,expected in SOURCE_HASHES.items():
        if actual[name]!=expected:
            raise RuntimeError(f'PIN_MISMATCH {name}: {actual[name]} expected {expected}')
    main=(RTL/OTHER[0]).read_text()
    checks={
      'registered_ready': 'assign s_arready=s_arready_reg;',
      'registered_output_valid': 'assign s_rvalid=s_rvalid_reg;',
      'arbiter_reused': 'arbiter #(',
      'backpressure_holds': 's_rvalid_next=s_rvalid_reg & ~s_rready;',
      'decode_error': "resp_next=2'b11;",
      'two_dest_address_decode': "wire decoded_dest=(addr_reg[15:8]==8'h01);",
    }
    for name,needle in checks.items():
        if main.count(needle)!=1:
            raise RuntimeError(f'CONTRACT_SHAPE_ERROR {name}: {main.count(needle)} matches')
    old=(RTL/OTHER[1]).read_text()
    if old.count('assign s_arready=(state_reg==ST_IDLE')!=1:
        raise RuntimeError('Early-ready mutant missing exact mutation')
    old2=(RTL/OTHER[2]).read_text()
    if "s_rvalid_next=2'b00;" not in old2:
        raise RuntimeError('Response-loss mutant missing exact mutation')
    if not (THIRD/'arbiter.v').exists():raise RuntimeError('Missing shared arbiter')
    return actual

def generated_bench(mode,contract_kind,check_kind):
    src=(RTL/'axi_refinement_v2_formal_bench.v').read_text()
    substitutions={
      'parameter MODE=0':f'parameter MODE={mode}',
      'parameter CONTRACT_KIND=0':f'parameter CONTRACT_KIND={contract_kind}',
      'parameter CHECK_KIND=0':f'parameter CHECK_KIND={check_kind}',
    }
    for a,b in substitutions.items():
        if src.count(a)!=1:raise RuntimeError(f'Bench template missing exactly once: {a}')
        src=src.replace(a,b,1)
    return src

def config_sby(bench,mode,check_kind,timeout,depth):
    cover=bool(check_kind)
    engine='smtbmc z3' if cover else 'abc pdr'
    files=[]
    for name in SOURCE:files.append(f'{name} {THIRD/name}')
    for name in OTHER:files.append(f'{name} {RTL/name}')
    files.append(f'bench.v {bench}')
    source_line=' '.join((*SOURCE,*OTHER))
    return '\n'.join([
      '[options]',f'mode {"cover" if cover else "prove"}',f'depth {depth}',f'timeout {timeout}',
      '', '[engines]',engine,'','[script]',
      f'read_verilog -sv {source_line}',
      'read_verilog -formal -sv bench.v',
      'prep -top axi_refinement_v2_formal_bench -flatten',
      '','[files]',*files,''])

def prepare(work,timeout,depth):
    hashes=verify_sources()
    work.mkdir(parents=True,exist_ok=True)
    tasks=[]
    for name,(mode,kind,check,expect) in TASKS.items():
        bench=work/(name+'_bench.v');bench.write_text(generated_bench(mode,kind,check))
        cfg=work/(name+'.sby');cfg.write_text(config_sby(bench,mode,check,timeout,depth))
        tasks.append({'name':name,'mode':mode,'contract_kind':kind,
                      'check_kind':'cover' if check else 'unbounded_safety',
                      'expected':expect,'sby':cfg.name,'bench':bench.name})
    manifest={
        'experiment':'axi_read_control_contract_v2_scoped_refinement',
        'source_repository':'alexforencich/verilog-axi', 'pinned_commit':PIN,
        'pinned_source_sha256':hashes,'formal_status':'PREPARED_NOT_EXECUTED',
        'scope':'2 sources, 2 destinations, reads only, fixed 0x0000/0x0100 regions, outputs as documented in README',
        'nonclaims':['AXI write support','RDATA integrity','physical timing','arbitrary multi-clock behavior',
                     'unconstrained environment trace inclusion','automatic contract extraction','automatic LLM translation'],
        'tasks':tasks}
    (work/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    (work/'RUN_STATUS.json').write_text(json.dumps({'status':'GENERATED_ONLY',
        'formal_tasks_executed':0,'contract_refinement':'NOT_PROVED',
        'change_gate':'REVIEW_REQUIRED_NO_AUTOMATIC_APPROVAL'},indent=2)+'\n')
    return tasks

def gate_results(rows):
    idx={x.get('name'):x for x in rows}
    all_present=set(idx)==set(TASKS) and len(rows)==len(TASKS)
    expected=all_present and all(idx[x]['status']==t[3] for x,t in TASKS.items())
    probes=all(idx.get(x,{}).get('status')=='PASS' and idx[x].get('has_witness') for x in COVERS)
    mutant_witness=all(idx.get(x,{}).get('status')=='FAIL' and idx[x].get('has_witness') for x in MUTANTS)
    proofs=all(idx.get(x,{}).get('status')=='PASS' and idx[x].get('engine')=='abc pdr' for x in PROOFS)
    # A single failing miter, uncovered scenario, timeout, or missing evidence blocks qualification.
    qualified=expected and proofs and probes and mutant_witness
    return {
      'harness_execution':'COMPLETE_EXPECTED_OUTCOMES' if qualified else 'INCOMPLETE_OR_UNEXPECTED',
      'scoped_control_cycle_equivalence':'PROVED_UNDER_DECLARED_TEST_ASSUMPTIONS' if qualified else 'NOT_ESTABLISHED',
      'general_trace_inclusion':'NOT_ESTABLISHED',
      'payload_equivalence':'NOT_CHECKED',
      'proof_requires_architecture_and_assumption_review':True,
      'product_change_gate':'REVIEW_REQUIRED_NO_AUTOMATIC_APPROVAL',
      'task_count':len(rows),'all_tasks_present':all_present,
      'expected_task_outcomes':expected,'positive_abc_pdr_proofs':proofs,
      'nonvacuity_covers':probes,'negative_controls':mutant_witness}

def run(work,timeout,depth):
    tasks=prepare(work,timeout,depth)
    if not shutil.which('yosys') or not shutil.which('sby'):
        (work/'RUN_STATUS.json').write_text(json.dumps({'status':'BLOCKED_MISSING_RTL_FORMAL_TOOLS',
         'formal_tasks_executed':0,'contract_refinement':'NOT_PROVED',
         'product_change_gate':'REVIEW_REQUIRED_NO_AUTOMATIC_APPROVAL'},indent=2)+'\n')
        return 3
    rows=[]
    for t in tasks:
        name=t['name'];start=time.monotonic();taskdir=work/name
        try:
            proc=subprocess.run(['sby','-f','-d',str(taskdir),str(work/t['sby'])],
                capture_output=True,text=True,timeout=timeout+60)
            rc=proc.returncode;log=proc.stdout+'\n'+proc.stderr
        except subprocess.TimeoutExpired as exc:
            rc=124;log=str(exc)
        (work/(name+'.log')).write_text(log)
        status=(taskdir/'status').read_text().strip().split()[0].upper() if (taskdir/'status').exists() else 'MISSING'
        if rc==124:status='TIMEOUT'
        aig=taskdir/'model/design_aiger.aig'; latches=ands='';digest=''
        if aig.exists():
            digest=hashlib.sha256(aig.read_bytes()).hexdigest()
            with aig.open('rb') as f:head=f.readline().decode(errors='replace').split()
            if len(head)>=6 and head[0] in ('aag','aig'):latches,ands=head[3],head[5]
        witness=any(taskdir.rglob('*.vcd'))
        row={'name':name,'mode':t['mode'],'expected':t['expected'],'status':status,
             'engine':'smtbmc z3' if t['check_kind']=='cover' else 'abc pdr',
             'has_witness':witness,'seconds':round(time.monotonic()-start,5),
             'returncode':rc,'aig_latches':latches,'aig_ands':ands,'aig_sha256':digest}
        rows.append(row)
        print(name,status,'expected',t['expected'],'witness',witness,flush=True)
    with (work/'formal_results.csv').open('w',newline='') as file:
        writer=csv.DictWriter(file,fieldnames=rows[0].keys());writer.writeheader();writer.writerows(rows)
    gate=gate_results(rows)
    (work/'RUN_STATUS.json').write_text(json.dumps({'status':'EXECUTED','gate':gate,'results':rows},indent=2)+'\n')
    manifest=json.loads((work/'manifest.json').read_text());manifest['formal_status']='EXECUTED'
    manifest['scoped_refinement']=gate['scoped_control_cycle_equivalence']
    (work/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return 0 if gate['harness_execution']=='COMPLETE_EXPECTED_OUTCOMES' else 2

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--work',default=str(ROOT/'results/github_sby'))
    ap.add_argument('--timeout',type=int,default=300)
    ap.add_argument('--depth',type=int,default=80)
    ap.add_argument('--generate-only',action='store_true')
    args=ap.parse_args()
    work=Path(args.work).resolve()
    if args.generate_only:
        prepare(work,args.timeout,args.depth)
        print('Generated',len(TASKS),'SBY tasks. NO formal proofs executed.')
    else:raise SystemExit(run(work,args.timeout,args.depth))
if __name__=='__main__':main()
