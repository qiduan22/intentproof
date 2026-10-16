#!/usr/bin/env python3
"""Plot *only verified, actually executed* upstream RTL benchmarks.

No charts are emitted for missing runs, unknown/timeout proofs or failed source
comparisons. This avoids accidental publication of synthetic/placeholder data.
"""
import argparse,json,sys
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def main():
 p=argparse.ArgumentParser();p.add_argument('--work',type=Path,default=Path(__file__).resolve().parent/'results'/'upstream_sby');args=p.parse_args()
 wd=args.work.resolve();result_file=wd/'benchmark_results.json'
 if not result_file.is_file():
  print('NO UPSTREAM RUN: benchmark_results.json absent',file=sys.stderr);return 2
 # Plot only when all strict source-pin, proof-status and witness gates pass.
 verdict_file=wd/'ci_verdict.json'
 if not verdict_file.exists() or not json.loads(verdict_file.read_text()).get('accepted',False):
  print('NO VERIFIED FIGURES: strict pinned-upstream gate not accepted',file=sys.stderr)
  return 2
 rows=json.loads(result_file.read_text());by={(r['variant'],r['case']):r for r in rows}
 variants=sorted(set(r['variant'] for r in rows))
 if not variants:
  print('NO UPSTREAM RUN: zero configurations',file=sys.stderr);return 2
 for variant in variants:
  for case,needed in [('full','PROVED'),('coi','PROVED'),('contract','PROVED'),('mutant','PROPERTY_FAILED'),('cover','COVERED')]:
   row=by.get((variant,case))
   if not row or row['status']!=needed:
    print(f'INCOMPLETE UPSTREAM VERIFICATION: {variant}/{case} = {row["status"] if row else "MISSING"}, expected {needed}',file=sys.stderr)
    return 2
  for case in ['full','coi']:
   if 'approx_sequential_bits' not in by[(variant,case)]:
    print('NO MEASURED YOSYS MODEL SIZE',file=sys.stderr);return 2
 folder=wd/'verified_figures';folder.mkdir(exist_ok=True)
 x=list(range(len(variants)));w=.35
 fig,ax=plt.subplots(figsize=(7.3,3.8))
 for offset,kind,label in [(-w/2,'full','RTL with exposed payload'),(w/2,'coi','Property-only structural COI')]:
  ax.bar([i+offset for i in x],[by[(v,kind)]['approx_sequential_bits'] for v in variants],width=w,label=label)
 ax.set_xticks(x,variants);ax.set_ylabel('Measured Yosys sequential bits')
 ax.set_title('Upstream RTL structural reduction (pinned, proved)');ax.legend(fontsize=8)
 ax.spines[['top','right']].set_visible(False)
 fig.tight_layout();fig.savefig(folder/'upstream_fig1_structural_bits.png',dpi=170);plt.close(fig)
 fig,ax=plt.subplots(figsize=(7.3,3.8))
 for kind in ['full','coi','contract']:
  ax.plot(variants,[by[(v,kind)]['proof_seconds'] for v in variants],marker='o',label=kind)
 ax.set_ylabel('Measured SBY task wall time (seconds)');ax.set_title('Upstream RTL property verification — executed runs only')
 ax.legend();ax.spines[['top','right']].set_visible(False)
 fig.tight_layout();fig.savefig(folder/'upstream_fig2_formal_time.png',dpi=170);plt.close(fig)
 print('Generated genuine upstream figures at',folder);return 0
if __name__=='__main__':sys.exit(main())
