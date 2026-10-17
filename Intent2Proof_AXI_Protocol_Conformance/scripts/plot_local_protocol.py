"""Plot only executed Python reference-model checks; no RTL metric claims."""
from pathlib import Path
import csv
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[1]
figs=ROOT/'figures';figs.mkdir(exist_ok=True)
local=ROOT/'results/local'
r=json.loads((local/'LOCAL_MODEL_STATUS.json').read_text())
with (local/'two_transactions_reference_trace.csv').open() as f: rows=list(csv.DictReader(f))
x=[int(d['cycle']) for d in rows]
a=[int(d['downstream_ar_accepted']) for d in rows]
b=[int(d['downstream_read_completed']) for d in rows]
fig,ax=plt.subplots(figsize=(8.2,3.6))
ax.step(x,a,where='mid',label='Downstream read address accepted',linewidth=2)
ax.step(x,b,where='mid',label='Downstream response completed',linewidth=2,linestyle='--')
ax.set(xlabel='Abstract clock transition',ylabel='Observed handshake (0 / 1)',ylim=(-0.15,1.3),title='Local reference-model witness: two legal read transactions')
ax.set_xticks(x);ax.legend(loc='upper center',bbox_to_anchor=(.5,-.23),ncol=2,fontsize=8)
ax.grid(axis='y',alpha=.3)
fig.tight_layout();fig.savefig(figs/'figure1_reference_two_legal_reads.png',dpi=180,bbox_inches='tight');plt.close(fig)
fig,ax=plt.subplots(figsize=(6.6,3.4))
ax.bar(['One slave','Two independent slaves'],[r['legal_one_slave_reachable_states'],r['legal_two_slave_reachable_states']])
for i,v in enumerate([r['legal_one_slave_reachable_states'],r['legal_two_slave_reachable_states']]):ax.text(i,v+.16,str(v),ha='center')
ax.set(ylabel='Reachable protocol-control states',title='Local reference-model exhaustive state exploration',ylim=(0,11))
ax.grid(axis='y',alpha=.3)
fig.tight_layout();fig.savefig(figs/'figure2_reference_state_space.png',dpi=180);plt.close(fig)
print('Wrote local reference-only figures')
