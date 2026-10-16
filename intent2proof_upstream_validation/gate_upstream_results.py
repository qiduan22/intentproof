#!/usr/bin/env python3
"""Fail-closed audit of genuine SBY results; never upgrades bounded/model-only runs.

Exit 0 only when 15 pinned upstream tasks have their specified result, the
full/coi structural measurements exist, and provenance is internally consistent.
A *failed* mutant assertion is expected and is successful fault detection.
"""
from __future__ import annotations
import argparse, json, re, sys
from pathlib import Path

EXPECTED={'full':'PROVED','coi':'PROVED','contract':'PROVED',
          'mutant':'PROPERTY_FAILED','cover':'COVERED'}
CONFIGS={(2,8),(3,16),(4,8)}

def audit(work: Path):
    errors=[]
    rp=work/'benchmark_results.json'
    mp=work/'manifest.json'
    if not rp.exists(): return {'accepted':False,'errors':['Missing measured benchmark_results.json'],'tasks':0}
    if not mp.exists(): return {'accepted':False,'errors':['Missing pinned source manifest.json'],'tasks':0}
    try:rows=json.loads(rp.read_text()); manifest=json.loads(mp.read_text())
    except (OSError,ValueError) as e:return {'accepted':False,'errors':['Invalid JSON: '+str(e)],'tasks':0}
    sha=manifest.get('repository_commit_sha','')
    if not re.fullmatch('[0-9a-f]{40}',sha):errors.append('Git commit not pinned to exact 40-character SHA')
    for key in ('source_sha256','synthesis_view_sha256','mutant_sha256'):
        if not re.fullmatch('[0-9a-f]{64}',manifest.get(key,'')):errors.append('Missing SHA256: '+key)
    if manifest.get('synthesis_view_sha256')==manifest.get('mutant_sha256'):
        errors.append('Mutant is identical to synthesis view')
    if manifest.get('source')!='rtl/sfifo.v':errors.append('Unexpected source path')
    expected={(f'sfifo_LG{lg}_BW{bw}',typ) for lg,bw in CONFIGS for typ in EXPECTED}
    observed={(r.get('variant'),r.get('case')) for r in rows}
    if len(rows)!=len(observed):errors.append('Duplicate task keys')
    for key in sorted(expected-observed):errors.append('Missing task: %s/%s'%key)
    for key in sorted(observed-expected):errors.append('Unexpected task: %s/%s'%key)
    by={(r.get('variant'),r.get('case')):r for r in rows}
    for key in sorted(expected):
        row=by.get(key)
        if not row:continue
        want=EXPECTED[key[1]]
        if row.get('status')!=want:
            errors.append(f'{key[0]}/{key[1]} status={row.get("status")} expected={want}')
        if row.get('upstream_commit')!=sha:errors.append(f'{key}: commit mismatch')
        if not isinstance(row.get('proof_seconds'),(int,float)) or row.get('proof_seconds')<0:
            errors.append(f'{key}: proof timing not measured')
        if key[1] in ('full','coi') and (not isinstance(row.get('approx_sequential_bits'),int)
                                          or row['approx_sequential_bits']<=0):
            errors.append(f'{key}: Yosys sequential bits missing or invalid')
        if key[1]=='mutant' and row.get('status')=='PROPERTY_FAILED' and not row.get('witness_files'):
            errors.append(f'{key}: mutant FAIL lacks saved counterexample witness')
        if key[1]=='mutant' and row.get('rtl_sha256')!=manifest.get('mutant_sha256'):
            errors.append(f'{key}: not using mutant RTL hash')
        if key[1]!='mutant' and row.get('rtl_sha256')!=manifest.get('synthesis_view_sha256'):
            errors.append(f'{key}: not using synthesis RTL hash')
    return {'accepted':not errors,'errors':errors,'tasks':len(rows),
            'source_sha':sha,'scope':'pinned_upstream_sby',
            'interpretation':'model checking for the defined assertions only; not proof of arbitrary properties'}

def main():
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);args=p.parse_args()
    wd=args.work.resolve();wd.mkdir(parents=True,exist_ok=True)
    outcome=audit(wd)
    (wd/'ci_verdict.json').write_text(json.dumps(outcome,indent=2)+'\n')
    print(json.dumps(outcome,indent=2))
    return 0 if outcome['accepted'] else 2
if __name__=='__main__':sys.exit(main())
