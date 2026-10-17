#!/usr/bin/env python3
"""Fail closed on missing/inconclusive/failed real RTL tasks."""
import argparse,csv,json
from pathlib import Path

def assess(folder):
    folder=Path(folder); results=folder/'rtl_results.csv';manifest=folder/'manifest.json'
    if not results.is_file() or not manifest.is_file():
        return False,{'decision':'REVIEW_REQUIRED','reason':'missing required RTL results or manifest'}
    meta=json.loads(manifest.read_text());rows=list(csv.DictReader(results.open()))
    if len(rows)!=len(meta['tasks']):
        return False,{'decision':'REVIEW_REQUIRED','reason':'task inventory incomplete'}
    reasons=[]
    for x in rows:
        if x['status']!=x['expected']:reasons.append(x['name']+': '+x['status']+' expected '+x['expected'])
        if x['expected']=='FAIL' and x['witness']!='True':reasons.append(x['name']+': counterexample missing')
    if meta['resolved_commit']=='UNFETCHED_OFFLINE':reasons.append('upstream not fetched')
    # Even complete candidate-model checks are NOT a trace-inclusion proof.
    return (len(reasons)==0,{'decision':'READY_FOR_REVIEW' if not reasons else 'REVIEW_REQUIRED',
        'reason':'RTL tasks completed; abstract-model trace-inclusion still unproved' if not reasons else '; '.join(reasons),
        'completed_task_count':len(rows),'abstract_contract_status':meta['abstract_contract_status']})

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work',required=True);a=p.parse_args()
    ok,d=assess(a.work);f=Path(a.work)/'gate_result.json';f.parent.mkdir(parents=True,exist_ok=True);f.write_text(json.dumps(d,indent=2)+'\n');print(json.dumps(d,indent=2));raise SystemExit(0 if ok else 2)
