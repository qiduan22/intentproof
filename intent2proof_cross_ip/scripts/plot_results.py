#!/usr/bin/env python3
import argparse,csv,json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

def local(root):
    figures=root/'figures';figures.mkdir(exist_ok=True)
    a=json.loads((root/'results/model/exhaustive.json').read_text())
    healthy=sorted((x for x in a if x['variant']=='correct'),key=lambda x:x['capacity'])
    bad=sorted((x for x in a if x['variant']!='correct'),key=lambda x:x['capacity'])
    x=[v['capacity'] for v in healthy]
    plt.figure(figsize=(6.6,4.2));plt.plot(x,[v['reachable_states'] for v in healthy],'o-',linewidth=2)
    plt.yscale('log');plt.xticks(x);plt.grid(axis='y',alpha=.28)
    plt.xlabel('FIFO capacity per block');plt.ylabel('Reachable control states (log scale)')
    plt.title('Three-FIFO system: exhaustive control exploration')
    plt.tight_layout();plt.savefig(figures/'fig1_reachable_control_states.png',dpi=190);plt.close()

    fig,ax=plt.subplots(figsize=(7.0,4.1))
    ys=[0,1,2]
    labels=['Accept input B','Shutdown while data moves','Output buffered; unsafe reconfig']
    ax.set_yticks(ys,labels)
    for j in ys:
        ax.plot([j+1,j+1],[j-.23,j+.23],color='#2563a5',linewidth=3)
    ax.axvline(3,color='#d55e3e',linestyle='--',linewidth=2)
    ax.set_xticks([1,2,3],['Initial → 1','Step 1 → 2','At state 2'])
    ax.set_ylim(2.65,-.65);ax.set_xlim(.5,4.7)
    ax.set_title('Mutant: output FIFO omitted from shutdown guard')
    ax.text(3.06,2.18,'reconfig_start = 1\npending = 1',fontsize=9,va='center')
    ax.grid(axis='x',alpha=.2);fig.tight_layout();fig.savefig(figures/'fig2_mutant_shutdown_counterexample.png',dpi=190);plt.close(fig)

    lg=[2,3,4];bw=8
    mon=[l+3 for l in lg];n=[l+1 for l in lg];cap=[1<<l for l in lg]
    # These are explicit RTL register budgets, NOT measured Yosys AIG latches.
    raw=[3*(d*bw+3*ni+1)+2+mi for d,ni,mi in zip(cap,n,mon)]
    coi=[3*(ni+1)+2+mi for ni,mi in zip(n,mon)]
    contract=[3*ni+2+mi for ni,mi in zip(n,mon)]
    plt.figure(figsize=(7.0,4.3));plt.plot(cap,raw,'o-',label='RTL register budget incl. payload')
    plt.plot(cap,coi,'s-',label='Standard COI control-state budget')
    plt.plot(cap,contract,'^-',label='Count-contract control-state budget')
    plt.xticks(cap);plt.yscale('log');plt.xlabel('FIFO capacity per block');plt.ylabel('State bits (model budgets; log scale)')
    plt.title('Expected structural scope (not measured solver speedup)')
    plt.grid(axis='y',alpha=.25);plt.legend(fontsize=8)
    plt.tight_layout();plt.savefig(figures/'fig3_model_bit_budgets.png',dpi=190);plt.close()
    (figures/'scope_note.txt').write_text('Figure 1/2 are measured on source-derived control equations; Figure 3 is a counted theoretical budget from RTL declarations, NOT Yosys/ABC data.\n')

def upstream(work,root):
    p=work/'benchmark.csv'
    if not p.exists():return
    rows=list(csv.DictReader(p.open()));by={}
    for r in rows:
        if r['mode'] in ('full','coi','contract') and r['status']=='PASS':
            by.setdefault(int(r['lg']),{})[r['mode']]=r
    if not by:return
    modes=['full','coi','contract'];x=sorted(by);plt.figure(figsize=(7.0,4.1))
    for m in modes:
        xx=[1<<lg for lg in x if m in by[lg]]
        yy=[float(by[lg][m]['wall_seconds']) for lg in x if m in by[lg]]
        if xx:plt.plot(xx,yy,'o-',label=m)
    plt.xticks([1<<i for i in x]);plt.xlabel('FIFO capacity per block')
    plt.ylabel('Task wall time (s), incl. preprocessing');plt.grid(alpha=.25)
    plt.title('Measured GitHub RTL formal task runtimes (exploratory)')
    plt.legend();plt.tight_layout();plt.savefig(root/'figures'/'fig4_upstream_task_runtime.png',dpi=190);plt.close()

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--work',default='');args=ap.parse_args();root=Path(__file__).resolve().parents[1]
    local(root)
    if args.work:upstream(Path(args.work),root)
if __name__=='__main__':main()
