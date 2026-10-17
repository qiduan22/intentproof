#!/usr/bin/env python3
"""Plots exclusively from executed architectural results. No full-RTL claims."""
from pathlib import Path
import json,matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[1];fig=ROOT/'figures';fig.mkdir(exist_ok=True)
r=json.loads((ROOT/'results'/'architectural_model.json').read_text())['results']
good=[x for x in r if x['variant']=='none']
mut=[x for x in r if x['variant']!='none']
fig1,ax=plt.subplots(figsize=(7,4.1));ax.plot([x['wait_limit'] for x in good],[x['reachable_states'] for x in good],marker='o',linewidth=2)
ax.set(xlabel='Maximum abstract slave waiting cycles',ylabel='Reachable states',title='Heterogeneous AXI read-path architectural model')
ax.set_xticks([1,2,3,4]);ax.set_ylim(80,180);ax.grid(axis='y',alpha=.28)
for x in good:ax.annotate(str(x['reachable_states']),(x['wait_limit'],x['reachable_states']),xytext=(0,9),textcoords='offset points',ha='center')
fig1.text(.5,.01,'Exhaustive model exploration, not RTL formal proof or solver speedup',ha='center',fontsize=9)
fig1.tight_layout(rect=(0,.05,1,1));fig1.savefig(fig/'fig1_reachable_arch_states.png',dpi=190);plt.close(fig1)
by={}
for x in mut:by.setdefault(x['variant'],[]).append(x['witness']['transitions'])
fig2,ax=plt.subplots(figsize=(7,4.1));names=['ignore_master1','wrong_owner'];bars=ax.bar(['Shutdown ignores master 1','Response delivered to wrong owner'],[by[n][0] for n in names],width=.55)
ax.set(ylabel='Shortest counterexample (transitions)',title='Detected injected control faults — architectural model',ylim=(0,4))
ax.grid(axis='y',alpha=.25)
for b in bars:ax.text(b.get_x()+b.get_width()/2,b.get_height()+.08,str(int(b.get_height())),ha='center')
fig2.text(.5,.02,'Identical counterexample lengths for tested slave-delay bounds 1–4',ha='center',fontsize=9)
fig2.tight_layout(rect=(0,.06,1,1));fig2.savefig(fig/'fig2_arch_fault_witnesses.png',dpi=190);plt.close(fig2)
