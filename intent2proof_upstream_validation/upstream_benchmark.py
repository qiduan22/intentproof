#!/usr/bin/env python3
"""Pinned-upstream end-to-end ZipCPU/sfifo RTL formal benchmark.

Does not claim success if Git, Yosys, SBY, and formal engines are missing.
Never treats unknown/timeouts/parse failures as proofs.

Experiments:
  full      : preserved RTL data output + control assertions + independent scoreboard
  coi       : same original RTL, property-only top (data not exposed)
  contract  : property-specific reference control circuit checked against original RTL
  mutant    : one deliberately modified *copy* of RTL; negative-control test
  cover     : exercise non-vacuity reachability on original RTL

`contract` is proven equivalence of *sampled control observations* if PASS; no
novel abstraction algorithm or speedup over standard COI is claimed.
"""
from __future__ import annotations
import argparse, csv, hashlib, json, os, re, shutil, subprocess, sys, time
from pathlib import Path

ROOT=Path(__file__).resolve().parent
REPO="https://github.com/ZipCPU/wb2axip.git"
RTL="rtl/sfifo.v"

CONTROL_REF=r'''// Source-derived control-only candidate: equivalence is an obligation, not an assumption.
module sfifo_control_ref #(parameter LGFLEN = 2)(
  input wire i_clk, i_reset, i_wr, i_rd,
  output wire ref_full, ref_empty,
  output reg [LGFLEN:0] ref_fill
);
  reg ref_empty_q;
  initial begin ref_fill = 0; ref_empty_q = 1'b1; end
  assign ref_full = ref_fill[LGFLEN];
  assign ref_empty = ref_empty_q;
  wire take_w = i_wr && !ref_full;
  wire take_r = i_rd && !ref_empty;
  always @(posedge i_clk) begin
    if (i_reset) begin
      ref_fill <= 0;
      ref_empty_q <= 1'b1;
    end else begin
      case ({take_w, take_r})
        2'b01: ref_fill <= ref_fill - 1'b1;
        2'b10: ref_fill <= ref_fill + 1'b1;
        default: begin end
      endcase
      case ({take_w, take_r})
        2'b01: ref_empty_q <= (ref_fill <= 1);
        2'b10: ref_empty_q <= 1'b0;
        default: begin end
      endcase
    end
  end
endmodule
'''

# "front_end" model is a synthesis configuration of source with FORMAL
# *not defined*. Formal collateral conditional on FORMAL is removed so the SBY
# process can attach the independent assertions without vendor's own testbench.
def preprocess_formal_disabled(source: str) -> str:
    """Remove FORMAL-only guarded collateral, preserving active synthesis RTL.

    This small preprocessor is intentionally strict; unsupported directive names
    cause rejection rather than silent reinterpretation. It is NOT a general SV
    macro-expander. Other macro directives remain in the output for Yosys.
    """
    stack=[]; enabled=True; out=[]; num_removed=0
    for ln, line in enumerate(source.splitlines(keepends=True),1):
        m=re.match(r'^\s*`(ifdef|ifndef|else|elsif|endif)\b\s*(\w+)?', line)
        if not m:
            if enabled:out.append(line)
            else:num_removed+=1
            continue
        op,arg=m.group(1),m.group(2)
        # We evaluate only ifdefs whose name is FORMAL; nested conditional
        # structure under a disabled FORMAL branch is tracked but not emitted.
        if op in ('ifdef','ifndef'):
            is_formal=(arg=='FORMAL')
            if is_formal:
                take = (op == 'ifndef')
                stack.append((enabled, is_formal, take, False))
                enabled = enabled and take
            else:
                stack.append((enabled, False, None, False))
                if enabled: out.append(line)
        elif op=='else':
            if not stack: raise ValueError(f'unmatched else line {ln}')
            parent, formal, take, used_else = stack[-1]
            if used_else: raise ValueError(f'duplicate else line {ln}')
            stack[-1] = (parent,formal,take,True)
            if formal:
                enabled = parent and not take
            else:
                enabled = parent
                if enabled: out.append(line)
        elif op=='elsif':
            if not stack:raise ValueError(f'unmatched elsif line {ln}')
            parent, formal, take, used_else = stack[-1]
            if formal: raise ValueError('unsupported `elsif inside `ifdef FORMAL; fail closed')
            enabled=parent
            if enabled:out.append(line)
        else:
            if not stack:raise ValueError(f'unmatched endif line {ln}')
            parent, formal, take, used_else=stack.pop()
            enabled=parent
            if enabled and not formal:out.append(line)
    if stack:raise ValueError('unclosed preprocessor conditionals')
    if num_removed==0:raise ValueError('FORMAL collateral not found; source layout changed')
    result=''.join(out)
    if '`ifdef FORMAL' in result:raise ValueError('nested FORMAL condition remains')
    for required in ['module sfifo', 'wire w_wr', 'wire w_rd', 'o_fill', 'r_empty']:
        if required not in result:raise ValueError(f'expected source element missing: {required}')
    return result

def wrapper(kind: str, lg: int, bw: int) -> str:
    assert kind in ('full','coi','contract','mutant','cover')
    is_full=kind=='full'
    is_contract=kind=='contract'
    is_cover=kind=='cover'
    outport=f',\n  output wire [{bw-1}:0] exposed_data' if is_full else ''
    datawire='' if is_full else f'wire [{bw-1}:0] discarded_data;'
    dataout='exposed_data' if is_full else 'discarded_data'
    additional=''
    if is_contract:
        additional=f'''wire reference_full,reference_empty; wire [{lg}:0] reference_fill;
  sfifo_control_ref #(.LGFLEN({lg})) reference (
    .i_clk(i_clk), .i_reset(i_reset), .i_wr(i_wr), .i_rd(i_rd),
    .ref_full(reference_full), .ref_empty(reference_empty), .ref_fill(reference_fill));
  always @(posedge i_clk) begin
     assert(o_fill == reference_fill);
     assert(o_full == reference_full);
     assert(o_empty == reference_empty);
  end
'''
    if is_cover:
        # Explicit covers are separate obligations; a cover is not a proof.
        additional=f'''always @(posedge i_clk) begin
    cover(reference_fill_for_cover == ({lg+1}'d{1<<lg}));
    cover(reference_fill_for_cover == 1 && i_rd && !o_empty);
  end
  wire [{lg}:0] reference_fill_for_cover = o_fill;
'''
    return f'''// Automatically generated property wrapper, case = {kind}, LGFLEN={lg}, BW={bw}
module intent2proof_bench(
  input wire i_clk, i_reset, i_wr, i_rd,
  input wire [{bw-1}:0] i_data{outport}
);
  localparam integer DEPTH = (1 << {lg});
  wire o_full, o_empty;
  wire [{lg}:0] o_fill;
  {datawire}
  sfifo #(.BW({bw}), .LGFLEN({lg}),
    .OPT_ASYNC_READ(1'b1), .OPT_WRITE_ON_FULL(1'b0),
    .OPT_READ_ON_EMPTY(1'b0)) dut(
     .i_clk(i_clk), .i_reset(i_reset),
     .i_wr(i_wr), .i_data(i_data),
     .o_full(o_full), .o_fill(o_fill),
     .i_rd(i_rd), .o_data({dataout}), .o_empty(o_empty)
   );
  // Independent interface accounting; does not use DUT internal o_fill.
  // The external protocol accepts a write iff i_wr&&!o_full, and a read iff
  // i_rd&&!o_empty, for these explicit parameter choices.
  reg [{lg}:0] external_count;
  initial external_count = 0;
  wire accepted_write = i_wr && !o_full;
  wire accepted_read = i_rd && !o_empty;
  always @(posedge i_clk) begin
    if (i_reset) external_count <= 0;
    else case ({{accepted_write, accepted_read}})
      2'b01: external_count <= external_count - 1'b1;
      2'b10: external_count <= external_count + 1'b1;
      default: begin end
    endcase
  end
  always @(posedge i_clk) begin
    if (!i_reset) begin
      assert(external_count <= DEPTH);
      assert(o_fill == external_count);
      assert(o_full == (external_count == DEPTH));
      assert(o_empty == (external_count == 0));
    end
  end
  {additional}
endmodule
'''

def mutate(source: str) -> str:
    # Deliberate negative control: ignore full flag when accepting a write.
    pat=r'wire\s+w_wr\s*=\s*\(i_wr\s*&&\s*!o_full\)\s*;'
    modified,n=re.subn(pat,'wire w_wr = i_wr; // INTENT2PROOF INJECTED CONTROL BUG',source)
    if n!=1:raise ValueError(f'Expected exactly one write gating expression, got {n}; changed source?')
    return modified

def hash_file(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def cmd(argv, cwd, timeout, log):
    t=time.perf_counter()
    try:
        p=subprocess.run(argv,cwd=str(cwd),text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=timeout)
        status='COMPLETED' if p.returncode==0 else 'NONZERO_EXIT'
        output=p.stdout or '';exit_code=p.returncode
    except subprocess.TimeoutExpired as e:
        status='TIMEOUT';output=(e.stdout or b'').decode(errors='replace') if isinstance(e.stdout,bytes) else (e.stdout or '')
        exit_code=None
    except OSError as e:
        status='ERROR';output=str(e);exit_code=None
    elapsed=time.perf_counter()-t
    log.parent.mkdir(parents=True,exist_ok=True)
    log.write_text(f'$ {" ".join(map(str,argv))}\nSTATUS {status} exit={exit_code} sec={elapsed:.4f}\n\n'+output)
    return {'execution':status,'exit_code':exit_code,'wall_seconds':round(elapsed,4),'log':str(log)}

def git_revision(repo: Path) -> str:
    r=subprocess.run(['git','-C',str(repo),'rev-parse','HEAD'],capture_output=True,text=True,check=True)
    return r.stdout.strip()

def check_clean_source(repo:Path):
    proc=subprocess.run(['git','-C',str(repo),'status','--porcelain','--',RTL],capture_output=True,text=True,check=True)
    if proc.stdout.strip():
        raise ValueError('Source RTL has uncommitted edits; pinning to a commit would be misleading')

def ensure_source(work:Path,revision:str|None,offline:bool):
    repo=work/'upstream'/'wb2axip'
    if not repo.exists():
        if offline: raise RuntimeError('Source unavailable in --offline mode; supply --repo-path or allow git clone')
        repo.parent.mkdir(parents=True,exist_ok=True)
        p=subprocess.run(['git','clone','--filter=blob:none','--depth=1',REPO,str(repo)],timeout=180,check=True)
    if revision:
        if not re.fullmatch(r'[0-9a-fA-F]{40}',revision):raise ValueError('--commit must be 40 hex digits')
        found=git_revision(repo)
        if found.lower()!=revision.lower():
            if offline: raise ValueError(f'Checkout {found} differs from requested {revision}')
            subprocess.run(['git','-C',str(repo),'fetch','origin',revision],timeout=120,check=True)
            subprocess.run(['git','-C',str(repo),'checkout','--detach',revision],timeout=120,check=True)
    commit=git_revision(repo)
    if not (repo/RTL).is_file():raise FileNotFoundError(repo/RTL)
    check_clean_source(repo)
    return repo,commit

def sby_config(kind,variant,bench,base,work,depth,engine):
    """Write SBY tasks with explicit source-file aliases.

    The [script] names MUST match files copied into task/src by [files].
    SBY supports `alias path` syntax; without it the original harness
    could not load source files, even on a fully provisioned machine.
    """
    mode='cover' if kind=='cover' else 'prove'
    srcs='sfifo.v bench.v'+(' ref.v' if kind=='contract' else '')
    body=f'''[options]
mode {mode}
depth {depth}

[engines]
{('smtbmc z3' if kind=='cover' else engine)}

[script]
read -formal -sv {srcs}
prep -top intent2proof_bench -flatten

[files]
sfifo.v {base.resolve()}
bench.v {bench.resolve()}
'''
    if kind=='contract':body+=f'ref.v {(work / "ref.v").resolve()}\n'
    dest=work/f'{variant}_{kind}.sby';dest.write_text(body)
    return dest

def run_yosys_stat(kind,rtl,bench,work,variant):
    name=f'{variant}_{kind}'
    json_out=work/f'{name}.json'
    # Both variants include the same RTL instance and property; difference is
    # whether the datapath output is an observable top-level output.
    script=(f'read_verilog -sv -formal {rtl} {bench}; '
            'hierarchy -check -top intent2proof_bench; '
            'proc; flatten; opt; memory_map; opt_clean -purge; '
            f'write_json {json_out}; stat')
    outcome=cmd(['yosys','-Q','-T','-p',script],work,120,work/f'{name}.yosys.log')
    result={'structural_run':outcome,'structural_json':str(json_out)}
    if outcome['execution']=='COMPLETED' and json_out.exists():
        content=json.loads(json_out.read_text());cells=content['modules']['intent2proof_bench'].get('cells',{})
        seq={'$dff','$adff','$dffe','$sdff','$sdffe','$aldff','$dlatch','$ff','$mem_v2','$mem'}
        bits=0; ccounts={}
        for c in cells.values():
            typ=c['type'];ccounts[typ]=ccounts.get(typ,0)+1
            if typ in seq:
                par=c.get('parameters',{});
                if typ in ('$mem_v2','$mem'):
                    size=int(par.get('SIZE','0'),2);width=int(par.get('WIDTH','0'),2)
                    bits+=size*width
                else: bits+=int(par.get('WIDTH','0'),2)
        result['approx_sequential_bits']=bits
        result['cell_count']=len(cells)
        result['cell_types']=ccounts
    return result

def analyze_status(task_dir:Path,run):
    """Interpret SBY status even when an expected property violation exits 1.

    SBY tasks with a genuine counterexample normally terminate with a nonzero
    process exit code and `status` = FAIL.  It is incorrect to categorize all
    nonzero exits as tool errors before reading the status file.
    """
    if run['execution'] in ('TIMEOUT','ERROR'):
        return 'NOT_PROVED_'+run['execution']
    status_file=task_dir/'status'
    if not status_file.is_file():return 'UNKNOWN_NO_STATUS'
    lines=status_file.read_text().strip().split()
    if not lines:return 'UNKNOWN_EMPTY_STATUS'
    state=lines[0].upper()
    if state=='PASS' and run['execution']=='COMPLETED':
        return 'COVERED' if '_cover' in task_dir.name else 'PROVED'
    if state=='FAIL':return 'PROPERTY_FAILED'
    return 'NOT_PROVED_'+state

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--work',type=Path,default=ROOT/'results'/'upstream_sby')
    p.add_argument('--repo-path',type=Path,help='Use an already cloned wb2axip repository; must include git metadata')
    p.add_argument('--commit',help='Pin to exact 40-character upstream commit SHA. Default: freeze current HEAD in manifest.')
    p.add_argument('--offline',action='store_true')
    p.add_argument('--engine',default='abc pdr')
    p.add_argument('--timeout',type=int,default=180)
    p.add_argument('--depth',type=int,default=30)
    p.add_argument('--only-prepare',action='store_true',help='Generate wrappers and SBY configs; do not execute solvers')
    p.add_argument('--self-test',action='store_true',help='Test local generator without downloading upstream RTL')
    args=p.parse_args()
    if args.self_test:
        test='''module sfifo; wire w_wr = (i_wr && !o_full);\n`ifdef FORMAL\nwire internal_formal;\n`ifdef F_PEEK\nwire hidden;\n`endif\n`endif\nwire w_rd = (i_rd && !o_empty); reg r_empty; reg [2:0] o_fill; endmodule\n'''
        pre=preprocess_formal_disabled(test); assert 'internal_formal' not in pre and 'wire w_wr' in pre
        assert 'INTENT2PROOF' in mutate(pre)
        for k in ['full','coi','contract','mutant','cover']:
            txt=wrapper(k,2,8);assert 'endmodule' in txt
        print('PASS: generator/self-test only; no upstream RTL evaluated');return
    wd=args.work.resolve();wd.mkdir(parents=True,exist_ok=True)
    avail={t:shutil.which(t) for t in ['git','yosys','sby','z3']}
    preflight={'tools':avail,'required_available':all(avail.values()),'runtime':'upstream benchmark','execution_mode':('prepare-only' if args.only_prepare else 'run')}
    (wd/'preflight.json').write_text(json.dumps(preflight,indent=2)+'\n')
    print('Preflight',preflight)
    if not avail['git']:raise RuntimeError('git required')
    if not args.only_prepare and not preflight['required_available']:
        print('FULL-RTL VERIFICATION NOT RUN: missing required tools; see preflight.json',file=sys.stderr)
        return 2
    if args.repo_path:
        repo=args.repo_path.resolve();commit=git_revision(repo)
        if args.commit and commit!=args.commit: raise ValueError('supplied local repository is not at --commit')
        if not (repo/RTL).exists():raise FileNotFoundError(repo/RTL)
        check_clean_source(repo)
    else:
        repo,commit=ensure_source(wd,args.commit,args.offline)
    dest=wd/'source_synthesis_view.v'
    dest.write_text(preprocess_formal_disabled((repo/RTL).read_text()))
    mut=wd/'source_mutant.v';mut.write_text(mutate(dest.read_text()))
    ref=wd/'ref.v';ref.write_text(CONTROL_REF)
    manifest={'repository':REPO,'repository_commit_sha':commit,'source':RTL,
      'source_sha256':hash_file(repo/RTL),'synthesis_view_sha256':hash_file(dest),
      'mutant_sha256':hash_file(mut),'note':'Source synthesis configuration retains data RTL but excludes upstream conditional FORMAL collateral; compare generated file to pinned commit.',
      'source_copy_in_artifact':False}
    (wd/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    rows=[]
    for lg,bw in [(2,8),(3,16),(4,8)]:
        variant=f'sfifo_LG{lg}_BW{bw}'
        for kind in ('full','coi','contract','mutant','cover'):
            bench=wd/f'{variant}_{kind}.v';bench.write_text(wrapper(kind,lg,bw))
            src=mut if kind=='mutant' else dest
            sby=sby_config(kind,variant,bench,src,wd,args.depth,args.engine)
            row={'variant':variant,'case':kind,'upstream_commit':commit,'status':'NOT_RUN','proof_seconds':None,
                 'rtl_sha256':hash_file(src),'bench_sha256':hash_file(bench)}
            if not args.only_prepare:
                if kind in ('full','coi'):
                    row.update(run_yosys_stat(kind,src,bench,wd,variant))
                task_dir=wd/f'{variant}_{kind}_task'
                outcome=cmd(['sby','-f','-d',str(task_dir),str(sby)],wd,args.timeout,wd/f'{variant}_{kind}.sby.log')
                row['status']=analyze_status(task_dir,outcome);row['proof_seconds']=outcome['wall_seconds']
                row['proof_run']=outcome
                if kind=='mutant':
                    # Preserve evidence that a model-checker FAIL produced a
                    # reproducible counterexample rather than only a status flag.
                    witness=[]
                    if task_dir.is_dir():
                        for fp in task_dir.rglob('*'):
                            if fp.is_file() and (
                                fp.suffix.lower() in ('.vcd','.yw','.fst')
                                or fp.name.startswith('trace_tb')
                            ):
                                witness.append(str(fp.relative_to(wd)))
                    row['witness_files']=sorted(witness)
            rows.append(row)
    (wd/'benchmark_results.json').write_text(json.dumps(rows,indent=2)+'\n')
    keys=['variant','case','status','proof_seconds','upstream_commit','rtl_sha256','bench_sha256','approx_sequential_bits','cell_count']
    with (wd/'benchmark_results.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=keys,extrasaction='ignore');w.writeheader();w.writerows(rows)
    print('\nRESULTS (unknown/timeout/missing is not a proof)')
    for r in rows:print(r['variant'],r['case'],r['status'],r['proof_seconds'])
    print('\nPinned SHA',commit)
    return 0
if __name__=='__main__':sys.exit(main() or 0)
