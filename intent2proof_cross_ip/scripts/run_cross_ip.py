#!/usr/bin/env python3
"""Generate/run SBY cross-IP benchmark with pinned upstream ZipCPU sfifo.

No implicit claims: generating a task is not a completed proof; timeouts fail closed.
"""
import argparse
import csv
import hashlib
import json
import re
import shutil
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RTL = ROOT / 'rtl'
ORIG_SHA = '76a653781f1ecca1c1da92c4e5105ecd5d0f832b13cbfd31300ec88d9947e0c1'
COMMIT = '2e8d3bc2d26ddc33d1881022a2a2b9d3f0c16b9b'
CONFIGS = [(2,8),(3,8),(4,8)]
MODES = ['full','coi','contract','mutant','cover','unit_contract']
EXPECTED = dict(full='PASS',coi='PASS',contract='PASS',mutant='FAIL',cover='PASS',unit_contract='PASS')


def source_check():
    got=hashlib.sha256((RTL/'sfifo.v').read_bytes()).hexdigest()
    if got!=ORIG_SHA:
        raise ValueError(f'pinned RTL SHA mismatch; expected={ORIG_SHA} found={got}')


def make_system_bench(lg,bw,mode):
    abstract = 1 if mode=='contract' else 0
    mutant = 1 if mode=='mutant' else 0
    expose = mode=='full'
    iscover = mode=='cover'
    dbg = f',\n output wire [{bw-1}:0] debug_a,debug_b,debug_sink' if expose else ''
    dbga = 'assign debug_a=p_a; assign debug_b=p_b; assign debug_sink=p_s;' if expose else ''
    return f'''// Cross-IP control requirements; independent acceptance/completion scoreboard.
// Mode={mode}, LOG2DEPTH={lg}, BW={bw}.
module intent2proof_bench(
  input wire clk, reset, wr_a, wr_b, rd_sink, shutdown_request,
  input wire [{bw-1}:0] data_a,data_b{dbg}
);
  localparam integer LG={lg}, BW={bw}, MW=LG+3, DEPTH=(1<<LG);
  wire [LG:0] fill_a,fill_b,fill_s;
  wire empty_a,empty_b,empty_s,full_a,full_b,full_s;
  wire acc_a,acc_b,delivered,take_a,take_b,write_sink,shutdown_latched,reconfig_start;
  wire [BW-1:0] p_a,p_b,p_s;
  cross_ip_top #(.BW(BW),.LGFLEN(LG),.USE_CONTRACT({abstract}),
        .BAD_SHUTDOWN({mutant})) dut(
     .clk(clk),.reset(reset),.wr_a(wr_a),.wr_b(wr_b),
     .rd_sink(rd_sink),.shutdown_request(shutdown_request),
     .data_a(data_a),.data_b(data_b),
     .payload_a(p_a),.payload_b(p_b),.payload_sink(p_s),
     .fill_a(fill_a),.fill_b(fill_b),.fill_sink(fill_s),
     .empty_a(empty_a),.empty_b(empty_b),.empty_sink(empty_s),
     .full_a(full_a),.full_b(full_b),.full_sink(full_s),
     .accepted_a(acc_a),.accepted_b(acc_b),.delivered(delivered),
     .take_a(take_a),.take_b(take_b),.write_sink(write_sink),
     .shutdown_latched(shutdown_latched),.reconfig_start(reconfig_start));
  {dbga}
  // Independent accepted - completed transaction accounting.
  // No reliance on DUT status flags for this monitor's state updates.
  reg [MW-1:0] pending;
  initial pending=0;
  wire [MW-1:0] sum_fill = {{2'b00,fill_a}}+{{2'b00,fill_b}}+{{2'b00,fill_s}};
  wire [MW-1:0] pending_next = pending + acc_a + acc_b - delivered;
  always @(posedge clk) begin
    if (reset) pending<=0;
    else pending<=pending_next;
  end
  always @(posedge clk) begin
    if (!reset) begin
      {'cover(reconfig_start); cover(shutdown_latched && pending != 0); cover(acc_a && acc_b);' if iscover else ('assert(!reconfig_start || pending == 0);' if mode=='mutant' else '''assert(pending == sum_fill);
      assert(pending <= 3*DEPTH);
      assert(!(take_a && take_b));
      assert(!reconfig_start || pending == 0);
      assert(!shutdown_latched || !(acc_a || acc_b));''')}
    end
  end
endmodule
'''


def make_unit_bench(lg,bw):
    return f'''// Independent unit contract discharge: real ZipCPU RTL versus count summary.
module intent2proof_bench(input wire clk,reset,wr,rd,
                         input wire [{bw-1}:0] data);
  wire full,empty,rf,re;
  wire [{lg}:0] fill,rfill;
  wire [{bw-1}:0] realdata,refdata;
  sfifo #(.BW({bw}),.LGFLEN({lg}),.OPT_ASYNC_READ(1'b1),
    .OPT_WRITE_ON_FULL(1'b0),.OPT_READ_ON_EMPTY(1'b0)) dut(
     .i_clk(clk),.i_reset(reset),.i_wr(wr),.i_data(data),
     .o_full(full),.o_fill(fill),.i_rd(rd),.o_data(realdata),.o_empty(empty));
  fifo_control_contract #(.BW({bw}),.LGFLEN({lg})) reference(
     .i_clk(clk),.i_reset(reset),.i_wr(wr),.i_data(data),
     .o_full(rf),.o_fill(rfill),.i_rd(rd),.o_data(refdata),.o_empty(re));
  always @(posedge clk) begin
    assert(fill == rfill);
    assert(full == rf);
    assert(empty == re);
  end
endmodule
'''


def sby_text(lg,bw,mode,timeout,depth):
    sby_mode='cover' if mode=='cover' else 'prove'
    engine='smtbmc z3' if mode=='cover' else 'abc pdr'
    return f'''[options]
mode {sby_mode}
depth {depth}
timeout {timeout}

[engines]
{engine}

[script]
read_verilog -sv sfifo.v fifo_control_contract.v cross_ip_top.v
read_verilog -formal -sv bench.v
prep -top intent2proof_bench -flatten

[files]
sfifo.v {RTL/'sfifo.v'}
fifo_control_contract.v {RTL/'fifo_control_contract.v'}
cross_ip_top.v {RTL/'cross_ip_top.v'}
bench.v
'''


def create(work,timeout,depth):
    source_check()
    work.mkdir(parents=True,exist_ok=True)
    generated=[]
    for lg,bw in CONFIGS:
        for mode in MODES:
            task=f'cross_LG{lg}_BW{bw}_{mode}'
            b=work / f'{task}_bench.v'; b.write_text(make_unit_bench(lg,bw) if mode=='unit_contract' else make_system_bench(lg,bw,mode))
            s=work / f'{task}.sby'
            # The generated SBY is located in `work`, and staging of bench.v
            # uses [files] alias path to avoid collisions across task modes.
            # Always stage as bench.v in the SBY workspace; explicit source alias.
            s.write_text(sby_text(lg,bw,mode,timeout,depth).replace('\nbench.v\n','\nbench.v '+str(b)+'\n'))
            generated.append({'task':task,'mode':mode,'lg':lg,'bw':bw,'sby':str(s),'expected':EXPECTED[mode]})
    (work/'manifest.json').write_text(json.dumps({
       'source':'ZipCPU/wb2axip rtl/sfifo.v','upstream_sha':COMMIT,'rtl_sha256':ORIG_SHA,
       'units':'three sfifo instances + locally authored merge/shutdown control',
       'scope':'same-clock, control-only; no payload ordering, physical timing or liveness',
       'discharged_contract':'o_fill, o_full, o_empty for source and contract reference; payload intentionally excluded',
       'generated':generated},indent=2)+'\n')
    return generated


def run(work,timeout,depth):
    todo=create(work,timeout,depth)
    if not shutil.which('sby'):
        (work/'RUN_STATUS.json').write_text(json.dumps({'state':'BLOCKED','reason':'SymbiYosys executable is not installed','proofs_executed':0},indent=2)+'\n')
        return 3
    rows=[]
    for a in todo:
        task=a['task']; sby=Path(a['sby']); directory=work/f'{task}_task';
        start=time.perf_counter()
        try:
            cp=subprocess.run(['sby','-f','-d',str(directory),str(sby)],capture_output=True,text=True,timeout=timeout+45)
            stdout=cp.stdout; stderr=cp.stderr; exitcode=cp.returncode; forced_timeout=False
        except subprocess.TimeoutExpired as err:
            stdout=(err.stdout or b''); stderr=(err.stderr or b'')
            if isinstance(stdout,bytes):stdout=stdout.decode(errors='replace')
            if isinstance(stderr,bytes):stderr=stderr.decode(errors='replace')
            exitcode=124;forced_timeout=True
        elapsed=time.perf_counter()-start
        (work/f'{task}.run.log').write_text(stdout+'\nSTDERR\n'+stderr)
        statusfile=directory/'status';raw=statusfile.read_text().strip() if statusfile.exists() else 'MISSING'
        raw='TIMEOUT' if forced_timeout else raw.split()[0].upper()
        aig=directory/'model'/'design_aiger.aig'
        aig_sha=hashlib.sha256(aig.read_bytes()).hexdigest() if aig.exists() else ''
        aiger_regs='';aiger_ands=''
        if aig.exists():
            header=aig.open('rb').readline().decode(errors='replace').split()
            if len(header)>=6 and header[0] in ('aig','aag'):
                aiger_regs=header[3];aiger_ands=header[5]
        rows.append({**{k:a[k] for k in ('task','mode','lg','bw','expected')},'status':raw,
                     'wall_seconds':round(elapsed,5),'exitcode':exitcode,
                     'aiger_latches':aiger_regs,'aiger_ands':aiger_ands,'aiger_sha256':aig_sha})
        print(task,raw,'expected',a['expected'],round(elapsed,2),flush=True)
    with (work/'benchmark.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=rows[0].keys());writer.writeheader();writer.writerows(rows)
    (work/'RUN_STATUS.json').write_text(json.dumps({'state':'EXECUTED','task_count':len(rows),'passing_expectation_count':sum(r['status']==r['expected'] for r in rows),'all_expectations_met':all(r['status']==r['expected'] for r in rows)},indent=2)+'\n')
    return 0 if all(r['status']==r['expected'] for r in rows) else 2


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--work',default=str(ROOT/'results'/'sby'))
    ap.add_argument('--timeout',type=int,default=180);ap.add_argument('--depth',type=int,default=40)
    ap.add_argument('--generate-only',action='store_true');args=ap.parse_args()
    w=Path(args.work).resolve();
    if args.generate_only:
        tasks=create(w,args.timeout,args.depth)
        print('generated',len(tasks),'tasks at',w)
        return
    raise SystemExit(run(w,args.timeout,args.depth))
if __name__=='__main__':main()
