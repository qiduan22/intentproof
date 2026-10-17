#!/usr/bin/env python3
"""Visualize ONLY executed restricted local SMT snapshots."""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
FIG=ROOT/'figures'
FIG.mkdir(exist_ok=True)
d=json.loads((ROOT/'results/local/local_smt_results.json').read_text())
res={r['scenario']:r['observed'] for r in d['results']}
# Report outcomes only where the mismatch query was executed.
labels=['No requests','Master 0 request','Both masters request']
old=[0,int(res['old_contract_master0_mismatch']=='sat'),int(res['old_contract_dual_mismatch']=='sat')]
new=[int(res['no_request_fixed']=='sat'),int(res['master0_fixed']=='sat'),int(res['both_masters_fixed']=='sat')]
x=np.arange(len(labels));width=.32
fig,ax=plt.subplots(figsize=(8,3.6))
ax.bar(x-width/2,old,width,label='Original candidate (v1)')
ax.bar(x+width/2,new,width,label='Registered-handshake v2')
ax.set_xticks(x,labels);ax.set_yticks([0,1],['No','Yes']);ax.set_ylim(0,1.35)
ax.set_ylabel('Mismatch satisfiable?')
ax.set_title('Source-grounded, first post-reset handshake snapshots')
ax.legend(fontsize=9,loc='upper right')
ax.text(0.5,-0.27,'Only restricted one-step SMT equations; NOT an RTL refinement proof',
        fontsize=9,ha='center',transform=ax.transAxes)
fig.tight_layout();fig.savefig(FIG/'figure1_local_handshake_snapshot.png',dpi=180,bbox_inches='tight');plt.close(fig)
fig,ax=plt.subplots(figsize=(6.6,3.2))
ax.bar(['v2 response hold','Injected response drop'],
       [int(res['v2_stalled_response_hold']=='sat'),int(res['mutant_dropped_stalled_response']=='sat')])
ax.set_yticks([0,1],['No','Yes']);ax.set_ylim(0,1.4)
ax.set_ylabel('Mismatch satisfiable?')
ax.set_title('One-step stalled response retention check')
ax.text(0.5,-0.23,'Single-step SMT model only; full RTL backpressure check pending',
        fontsize=9,ha='center',transform=ax.transAxes)
fig.tight_layout();fig.savefig(FIG/'figure2_local_response_snapshot.png',dpi=180,bbox_inches='tight');plt.close(fig)
print('Generated local-snapshot figures (not full RTL results).')
