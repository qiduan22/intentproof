#!/usr/bin/env python3
from pathlib import Path
import json,matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
FIG=ROOT/'figures';FIG.mkdir(exist_ok=True)
data=json.loads((ROOT/'results/local_smt_checks.json').read_text())['results']
labels=['No requests','Master 0 only','Both masters\n(shared destination)']
order=[data[2],data[0],data[1]]
original=[int(x['actual_accept'],2) for x in order]
candidate=[int(x['candidate_accept'],2) for x in order]
y=np.arange(len(labels)); width=.34
fig,ax=plt.subplots(figsize=(8.5,4.3))
ax.bar(y-width/2,original,width,label='Upstream RTL: registered ARREADY')
ax.bar(y+width/2,candidate,width,label='Candidate: combinational ARREADY')
ax.set_ylim(0,1.4);ax.set_yticks([0,1]);ax.set_yticklabels(['No transfer','Master 0 accepted'])
ax.set_xticks(y);ax.set_xticklabels(labels)
ax.set_title('First sampled cycle after reset: source-grounded handshake model')
ax.set_ylabel('Accepted request (ARVALID & ARREADY)')
ax.legend(loc='upper left',fontsize=9)
for i,(a,b) in enumerate(zip(original,candidate)):
    if a!=b:ax.annotate('DIFF', (i+width/2,b),xytext=(0,10),textcoords='offset points',ha='center',fontsize=9,fontweight='bold')
fig.tight_layout();fig.savefig(FIG/'figure1_handshake_difference.png',dpi=190);plt.close(fig)

fig,ax=plt.subplots(figsize=(8.5,3.65))
xs=[0,1,2]
labels=['Source equations\nanchored to pinned RTL','Local Z3 post-reset\nchecks','Full elaborated-RTL\nSBY miter']
markers=['5 source patterns checked','3/3 expected SAT/UNSAT','Prepared; not run locally']
ax.set_xlim(-.45,2.5);ax.set_ylim(-.5,1.25)
ax.plot(xs,[.5]*3,linewidth=1.6,marker='o',markersize=12)
for i in xs:
    ax.text(i,.78,labels[i],ha='center',va='center',fontsize=10,fontweight='medium')
    ax.text(i,.15,markers[i],ha='center',va='center',fontsize=9)
ax.text(2,-.21,'GitHub Actions required',ha='center',va='center',fontsize=9)
ax.axis('off');ax.set_title('Verification scope: completed evidence versus pending proof',pad=14)
fig.tight_layout();fig.savefig(FIG/'figure2_evidence_boundary.png',dpi=190);plt.close(fig)
print('Rendered:',*[p.name for p in FIG.glob('figure*.png')])
