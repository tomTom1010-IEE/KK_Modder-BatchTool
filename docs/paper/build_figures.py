"""Build paper figures and numeric tables from the public measurement extracts.

Run from any directory with Python, NumPy and Matplotlib installed.
No private character assets or Blender session are required.
"""
from pathlib import Path
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from draw_architecture import draw_architecture

ROOT = Path(__file__).resolve().parent
DATA = ROOT.parent / 'data'
OUT = ROOT / 'figures'
OUT.mkdir(exist_ok=True)
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':8,
    'axes.spines.top':False,'axes.spines.right':False,
    'pdf.fonttype':42,'ps.fonttype':42,'savefig.bbox':'tight'})
colors = ['#9babb7','#668cac','#00857e','#d96c33']
cases = json.loads((DATA/'three-stage-comparison.json').read_text())['cases']
stages = ['native','native_body_dynamic_budget','six_category','final']
names = ['Native','Native + B/D','SBCST init.','SBCST final']

draw_architecture()

fig, axs = plt.subplots(1,2,figsize=(7.1,2.25),gridspec_kw={'wspace':.32})
for ax,case,label in zip(axs,cases,['Jacket','Skirt outfit']):
    vals=[case['semantic_metrics'][s]['forbidden_body_category_vertices'] for s in stages]
    bars=ax.bar(range(4),vals,color=colors,width=.62)
    for bar,v in zip(bars,vals):ax.text(bar.get_x()+bar.get_width()/2,v+max(vals)*.035,str(v),ha='center',fontsize=8)
    ax.set_xticks(range(4),['Native','Native\n+ B/D','Init.','Final'])
    ax.set_ylim(0,max(vals)*1.27);ax.set_title(label,fontsize=9)
    ax.set_ylabel('Wrong-category vertices');ax.grid(axis='y',alpha=.15);ax.set_axisbelow(True)
    ax.text(.98,.91,'100% fewer\nvs. native',transform=ax.transAxes,ha='right',va='top',color=colors[2],fontsize=9,fontweight='bold')
fig.savefig(OUT/'semantic.pdf');plt.close(fig)

fig, axs = plt.subplots(1,4,figsize=(7.1,2.15),gridspec_kw={'wspace':.3})
for ax,(case,suite,title) in zip(axs,[(cases[0],'macro','Jacket / macro'),(cases[0],'terminal','Jacket / terminal'),(cases[1],'macro','Skirt / macro'),(cases[1],'terminal','Skirt / terminal')]):
    v=case['metrics'][suite]['heldout_rms'];vals=[100*v[s]/v['native'] for s in stages]
    ax.bar(range(4),vals,color=colors,width=.68)
    ax.set(ylim=(0,119),xticks=range(4),xticklabels=['N','N+BD','I','F'])
    ax.set_title(title,fontsize=8);ax.axhline(100,color='#666',lw=.5,ls='--');ax.grid(axis='y',alpha=.15);ax.set_axisbelow(True)
    ax.text(.95,.96,f"{100-vals[-1]:.2f}% lower",transform=ax.transAxes,ha='right',va='top',fontsize=7)
axs[0].set_ylabel('RMS (native = 100)')
fig.savefig(OUT/'response.pdf');plt.close(fig)

# Publish values directly from the evidence files; no hand-entered table cells.
rows=[]
for case,label in zip(cases,['Jacket','Skirt outfit']):
    for suite in ('macro','terminal'):
        m=case['metrics'][suite];v=m['heldout_rms']
        rows.append(f"{label} / {suite} & {m['scope_vertices']:,} & {len(m['heldout_poses'])} & " + ' & '.join(f'{1e3*v[s]:.6f}' for s in stages) + f" & {100*(1-v['final']/v['native']):.3f}\\% \\\\")
(ROOT/'response_rows.tex').write_text('\\newcommand{\\ResponseRows}{%\n'+'\n'.join(rows)+'\n}\n')
rows=[]
for case,label in zip(cases,['Jacket','Skirt outfit']):
    for s,name in zip(stages,names):
        m=case['semantic_metrics'][s]
        rows.append(f"{label} & {name} & {m['forbidden_body_category_vertices']:,} & {m['max_category_share_error']:.2e} & {m['max_dynamic_weight_error']:.2e} & {m['pure_dynamic_vertices_polluted']:,} \\\\")
(ROOT/'semantic_rows.tex').write_text('\\newcommand{\\SemanticRows}{%\n'+'\n'.join(rows)+'\n}\n')
print('Generated three vector figures and two tables from public JSON.')
