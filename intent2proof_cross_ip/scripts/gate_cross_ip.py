#!/usr/bin/env python3
"""Fail-closed machine-readable gate for REAL upstream SBY tasks.

An expected mutation failure is evidence only if the other obligations pass.
CI green is never itself proof of an unreported obligation.
"""
import argparse,csv,json,hashlib,sys
from pathlib import Path

def check(work):
    manifest=work/'manifest.json';result=work/'benchmark.csv'
    problems=[]
    if not manifest.exists():problems.append('missing manifest.json')
    if not result.exists():problems.append('missing benchmark.csv')
    if problems:return {'approved':False,'problems':problems,'checked':0}
    m=json.loads(manifest.read_text())
    with result.open() as f:
        rows=list(csv.DictReader(f))
    seen={r['task']:r for r in rows};expected={x['task']:x for x in m['generated']}
    if len(seen)!=len(rows):problems.append('duplicate benchmark rows')
    if set(seen)!=set(expected):problems.append('missing/unexpected task rows')
    for k,x in expected.items():
        row=seen.get(k)
        if not row:continue
        if row['status']!=x['expected']:
            problems.append(f"{k}: expected {x['expected']}, got {row['status']}")
        if x['mode']=='contract':
            peer=f"cross_LG{x['lg']}_BW{x['bw']}_unit_contract"
            if peer not in seen or seen[peer]['status']!='PASS':
                problems.append(f'{k}: upstream FIFO control-contract discharge missing')
        if x['mode']=='mutant' and row['status']=='FAIL':
            taskdir=work/f'{k}_task'
            # A verification failure should carry concrete trace evidence.
            if not list(taskdir.rglob('*.vcd')):
                problems.append(f'{k}: mutation failed but no .vcd witness was saved')
    return {'approved':not problems,'problems':problems,'checked':len(rows),
            'source_sha':m['rtl_sha256'],
            'scope':'RTL control properties only; no data-order equivalence or timing signoff'}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--work',required=True);args=ap.parse_args()
    w=Path(args.work).resolve();v=check(w);w.mkdir(exist_ok=True,parents=True)
    (w/'gate_result.json').write_text(json.dumps(v,indent=2)+'\n')
    print(json.dumps(v,indent=2));return 0 if v['approved'] else 2
if __name__=='__main__':sys.exit(main())
