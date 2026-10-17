#!/usr/bin/env python3
"""Generate/execute true upstream AXI-Lite RTL SymbiYosys tasks.
No model-only result is promoted to a real-RTL proof. No hidden pass on timeout.
"""
from pathlib import Path
import argparse,csv,hashlib,json,os,shutil,subprocess,time
ROOT=Path(__file__).resolve().parents[1]
RTL=ROOT/'rtl'
TASK_MODES=('full','coi','contract_candidate','mutant_shutdown','mutant_route','cover')
TRAFFIC={'contended':0,'separate':1}
EXPECT={'full':'PASS','coi':'PASS','contract_candidate':'PASS','mutant_shutdown':'FAIL','mutant_route':'FAIL','cover':'PASS'}
SOURCE=['axil_interconnect.v','arbiter.v','priority_encoder.v']


def pull_upstream(work,ref):
    dst=work/'upstream'
    if dst.exists() and (dst/'.git').exists():
        if ref!='master':
            subprocess.run(['git','-C',str(dst),'checkout','--detach',ref],check=True,capture_output=True,text=True)
    else:
        subprocess.run(['git','clone','--quiet','https://github.com/alexforencich/verilog-axi.git',str(dst)],check=True)
        if ref!='master':subprocess.run(['git','-C',str(dst),'checkout','--detach',ref],check=True)
    commit=subprocess.check_output(['git','-C',str(dst),'rev-parse','HEAD'],text=True).strip()
    for f in SOURCE:
        if not (dst/'rtl'/f).exists(): raise RuntimeError('missing required pinned upstream source '+f)
    return dst/'rtl',commit


def build_bench(mode,traffic):
    contract=int(mode=='contract_candidate');bad=int(mode=='mutant_shutdown');bad_route=int(mode=='mutant_route')
    iscover=mode=='cover'; expose=mode=='full'
    mapping = 'assume(request_target == 2\'b10);' if traffic=='separate' else ''
    outputs = 'output wire [63:0] debug_response' if expose else 'output wire proof_marker'
    assign_debug = 'assign debug_response = upstream_rdata;' if expose else 'assign proof_marker = reconfig_start;'
    assertion = ('''
       cover(reconfig_start && saw_response && saw_shutdown_pending);
    ''' if iscover else '''
       assert(mon0 <= 1 && mon1 <= 1);
       assert(internal_busy[0] == (mon0 != 0));
       assert(internal_busy[1] == (mon1 != 0));
       if (upstream_r_complete[0]) begin
           assert(mon0>0);
           assert(upstream_rdata[23:16] == {7'b0,request_dest[0]});
       end
       if (upstream_r_complete[1]) begin
           assert(mon1>0);
           assert(upstream_rdata[55:48] == {7'b0,request_dest[1]});
       end
       assert(!(reconfig_start &&
                (mon0 != 0 || mon1 != 0 || |waiting_ar)));
    ''')
    return f'''// Independently authored formal monitor for a REAL AXI-Lite interconnect.
// Task={mode} destination policy={traffic}; upstream interconnect is obtained by Git.
module intent2proof_axi_bench(input wire clk, input wire rst,
 input wire [1:0] generate_read,request_target,consume_read,slave_stall,
 input wire shutdown_request, {outputs});
 wire [1:0] upstream_ar_accept, upstream_r_complete, waiting_ar,
            internal_busy,request_dest,upstream_rvalid;
 wire [63:0] upstream_rdata;
 wire shutdown_latched,reconfig_start;
 axi_hetero_top #(.BAD_SHUTDOWN({bad}),.BAD_ROUTE({bad_route}),
                   .USE_CONTRACT({contract})) dut(
   .clk(clk),.rst(rst),.generate_read(generate_read),
   .request_target(request_target),.consume_read(consume_read),
   .slave_stall(slave_stall),.shutdown_request(shutdown_request),
   .upstream_ar_accept(upstream_ar_accept),
   .upstream_r_complete(upstream_r_complete),
   .waiting_ar(waiting_ar),.internal_busy(internal_busy),
   .request_dest(request_dest),.upstream_rvalid(upstream_rvalid),
   .upstream_rdata(upstream_rdata),
   .shutdown_latched(shutdown_latched),.reconfig_start(reconfig_start));
 {assign_debug}
 reg [1:0] mon0=0,mon1=0;
 reg seen_response=0,saw_response=0,saw_shutdown_pending=0;
 reg past_valid=0;
 always @(posedge clk) begin
   past_valid <= 1'b1;
   if (!past_valid) assume(rst);
   else assume(!rst);
   {mapping}
   if (rst) begin
      mon0<=0;mon1<=0;
      seen_response<=0;saw_response<=0;saw_shutdown_pending<=0;
   end else begin
      // handshake-only accounting, separate from DUT busy and FIFO flags
      case ({{upstream_ar_accept[0],upstream_r_complete[0]}})
        2'b10: mon0<=mon0+1'b1;
        2'b01: mon0<=mon0-1'b1;
        default: mon0<=mon0;
      endcase
      case ({{upstream_ar_accept[1],upstream_r_complete[1]}})
        2'b10: mon1<=mon1+1'b1;
        2'b01: mon1<=mon1-1'b1;
        default: mon1<=mon1;
      endcase
      if(|upstream_r_complete) begin saw_response<=1;seen_response<=1;end
      if(shutdown_latched && ((mon0!=0)||(mon1!=0)))
           saw_shutdown_pending<=1;
      {assertion}
   end
 end
endmodule
'''


def sby_text(srcdir,bench,mode,timeout,depth):
    selected='cover' if mode=='cover' else 'prove'
    engine='smtbmc z3' if mode=='cover' else 'abc pdr'
    file_entries='\n'.join(f'{p} {RTL/p}' for p in ('axi_hetero_top.v','axi_slow_read_slave.v','axi_read_contract_bridge.v'))
    upstream_entries='\n'.join(f'{p} {srcdir/p}' for p in SOURCE)
    return f'''[options]
mode {selected}
depth {depth}
timeout {timeout}

[engines]
{engine}

[script]
read_verilog -sv axil_interconnect.v arbiter.v priority_encoder.v axi_hetero_top.v axi_slow_read_slave.v axi_read_contract_bridge.v
read_verilog -formal -sv bench.v
prep -top intent2proof_axi_bench -flatten

[files]
{upstream_entries}
{file_entries}
bench.v {bench}
'''


def generate(work,ref,timeout,depth,skip_git=False):
    work.mkdir(parents=True,exist_ok=True)
    if skip_git:
        src=work/'upstream'/'rtl';commit='UNFETCHED_OFFLINE'
        src.mkdir(parents=True,exist_ok=True)
    else: src,commit=pull_upstream(work,ref)
    tasks=[]
    for traffic in TRAFFIC:
      for mode in TASK_MODES:
        tag=f'axi_{traffic}_{mode}'
        bench=work/f'{tag}_bench.v';bench.write_text(build_bench(mode,traffic))
        sby=work/f'{tag}.sby';sby.write_text(sby_text(src,bench,mode,timeout,depth))
        tasks.append({'name':tag,'traffic':traffic,'mode':mode,'expected':EXPECT[mode],
                      'bench':str(bench),'sby':str(sby)})
    hashes={p:hashlib.sha256((src/p).read_bytes()).hexdigest() if (src/p).is_file() else None for p in SOURCE}
    manifest={'external_repository':'https://github.com/alexforencich/verilog-axi',
              'requested_ref':ref,'resolved_commit':commit,'upstream_source_sha256':hashes,
              'source_status':'UPSTREAM_FETCHED' if not skip_git else 'NOT_AVAILABLE',
              'proof_status':'NOT_RUN','abstract_contract_status':'CANDIDATE_ONLY_NO_TRACE_INCLUSION_PROOF',
              'system':'2 read masters + shared upstream interconnect + 2 locally authored responding slaves + shutdown controller',
              'tasks':tasks}
    (work/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return tasks


def run(work,ref,timeout,depth):
    if not shutil.which('sby') or not shutil.which('yosys'):
        work.mkdir(parents=True,exist_ok=True)
        (work/'RUN_STATUS.json').write_text(json.dumps({'status':'BLOCKED_MISSING_FORMAL_TOOLS','proofs_executed':0},indent=2)+'\n');return 3
    try:tasks=generate(work,ref,timeout,depth)
    except Exception as e:
        work.mkdir(parents=True,exist_ok=True)
        (work/'RUN_STATUS.json').write_text(json.dumps({'status':'BLOCKED_UPSTREAM_FETCH_OR_PREP','error':str(e),'proofs_executed':0},indent=2)+'\n');return 4
    rows=[]
    for t in tasks:
       path=work/t['name'];start=time.perf_counter()
       try:
         p=subprocess.run(['sby','-f','-d',str(path),t['sby']],capture_output=True,text=True,timeout=timeout+45)
         ret=p.returncode;log=p.stdout+'\n'+p.stderr
       except subprocess.TimeoutExpired as e:
         ret=124;log='TIMEOUT: '+str(e)
       (work/(t['name']+'.log')).write_text(log)
       raw=(path/'status').read_text().strip().split()[0].upper() if (path/'status').is_file() else 'MISSING'
       if ret==124:raw='TIMEOUT'
       aig=path/'model'/'design_aiger.aig';bits='';gates='';digest=''
       if aig.is_file():
         digest=hashlib.sha256(aig.read_bytes()).hexdigest()
         with aig.open('rb') as fp: header=fp.readline().decode(errors='replace').split()
         if len(header)>=6 and header[0] in ('aig','aag'): bits=header[3];gates=header[5]
       witness=bool(list(path.rglob('*.vcd')))
       rows.append({'name':t['name'],'traffic':t['traffic'],'mode':t['mode'],
         'expected':t['expected'],'status':raw,'witness':witness,'seconds':round(time.perf_counter()-start,5),
         'returncode':ret,'aig_latches':bits,'aig_ands':gates,'aig_sha256':digest})
       print(t['name'],raw,'witness',witness,flush=True)
    with (work/'rtl_results.csv').open('w',newline='') as f:
       w=csv.DictWriter(f,rows[0].keys());w.writeheader();w.writerows(rows)
    (work/'RUN_STATUS.json').write_text(json.dumps({'status':'COMPLETED_WITH_EXPECTATION_CHECK',
       'task_count':len(rows),'results':rows},indent=2)+'\n')
    return 0 if all(r['status']==r['expected'] and (r['witness'] if r['expected']=='FAIL' else True) for r in rows) else 2


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--work',default=str(ROOT/'results'/'upstream_sby'))
    ap.add_argument('--ref',default='master',help='Use a full git commit SHA to pin a rerun; master records resolved SHA')
    ap.add_argument('--timeout',type=int,default=180);ap.add_argument('--depth',type=int,default=60)
    ap.add_argument('--generate-only',action='store_true');ap.add_argument('--offline-stub',action='store_true')
    a=ap.parse_args();work=Path(a.work).resolve()
    if a.generate_only:
        generate(work,a.ref,a.timeout,a.depth,skip_git=a.offline_stub)
        print('Prepared 12 tasks, upstream availability:',not a.offline_stub)
    else:raise SystemExit(run(work,a.ref,a.timeout,a.depth))
if __name__=='__main__':main()
