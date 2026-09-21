"""Plot same-input, frozen-pose measurements from the reviewed ablation extract."""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

ROOT=Path(__file__).resolve().parents[1]
rows=json.loads((ROOT/'docs/data/three-stage-comparison.json').read_text())['cases']
STAGES=['native','six_category','final']
COLORS=['#b7c3cf','#2469a6','#ab741a']
INK,MUTED,GRID='#162839','#536477','#e4e9ef'
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'text.color':INK,'svg.fonttype':'path'})
fig=plt.figure(figsize=(16,12),facecolor='white')
def text(x,y,s,size=12,color=INK,weight='normal',**kw):
    fig.text(x,y,s,fontsize=size,color=color,weight=weight,**kw)
def rule(y):
    fig.add_artist(Line2D([.045,.965],[y,y],transform=fig.transFigure,color=GRID,lw=1))
text(.045,.956,'KK MODDER BATCHTOOL  /  SAME-INPUT COMPARISON',11,COLORS[1],'bold')
text(.045,.913,'What six categories add.',30,weight='bold')
text(.045,.878,'Native transfer → six-category initialization → final optimized weights',15,MUTED)
text(.045,.85,'Identical fitted geometry, source reference, held-out poses and vertex scope within each comparison.',11,MUTED)
rule(.829)
for col,r in enumerate(rows):
    left=.045+col*.50
    text(left,.795,r['family']+' → KK',20,weight='bold')
    text(left,.769,'Neon Vertex closed jacket' if col==0 else 'Liv skirt outfit · fitted-mesh source reference',11,MUTED)
    for suite,bottom in [('macro',.55),('terminal',.30)]:
        d=r['metrics'][suite];vals=d['heldout_rms'];base=vals['native']
        ax=fig.add_axes([left+.096,bottom,.332,.137])
        ax.set_xlim(0,113);ax.set_ylim(-.55,2.65)
        ax.set_yticks([2,1,0],['Native','Six-category','Final'])
        ax.set_xticks([0,25,50,75,100]);ax.tick_params(length=0,labelsize=10,colors=MUTED)
        ax.grid(axis='x',color=GRID,zorder=0)
        for side in ['top','left','right']:ax.spines[side].set_visible(False)
        ax.spines['bottom'].set_color(GRID)
        for y,stage,color in zip([2,1,0],STAGES,COLORS):
            ratio=vals[stage]/base*100
            ax.barh(y,ratio,height=.43,color=color,zorder=2)
            ax.text(112,y,f'{ratio:.2f}',va='center',ha='right',fontsize=10,color=INK)
        text(left,bottom+.161,f'{suite.title()} response  /  {d["scope_vertices"]:,} vertices  /  {len(d["heldout_poses"])} held-out poses',11,weight='bold')
        text(left,bottom-.037,'RMS: '+' → '.join(f'{vals[s]:.8f}' for s in STAGES),10,MUTED)
        gain=100*(1-vals['final']/base)
        text(left,bottom-.06,f'Final vs native: {gain:.3f}% lower error',11,COLORS[2],'bold')
text(.5,.741,'Relative RMS · native = 100 · lower is better',11,MUTED,ha='center')
rule(.23)
text(.045,.205,'SEMANTIC PROTECTION  /  NATIVE → SIX-CATEGORY → FINAL',11,COLORS[1],'bold')
for col,r in enumerate(rows):
    left=.045+col*.50
    s=r['semantic_metrics']
    text(left,.177,'Wrong-category vertices: '+' → '.join(f'{s[k]["forbidden_body_category_vertices"]:,}' for k in STAGES),14,weight='bold')
    text(left,.151,'Max category-share error: '+' → '.join(f'{s[k]["max_category_share_error"]:.2e}' for k in STAGES),10,MUTED)
    count=s['native_body_dynamic_budget']['forbidden_body_category_vertices']
    text(left,.126,f'With body/dynamic totals already preserved: {count:,} → 0 wrong-category vertices',10,MUTED)
rule(.108)
text(.045,.084,'Native = normalized Blender nearest-face body transfer, without clothing dynamics. Auxiliary baseline preserves body/dynamic totals.',9.5,MUTED)
text(.045,.065,'Wrong-category = source share ≤ 1e-8, transferred share > 1e-5. Six-category includes reviewed finger and bnip policies.',9.5,MUTED)
text(.045,.046,'Different suites are not pooled. MMD retains reviewed cap intersections; this is not a collision-free or cross-method benchmark.',9.5,MUTED)
text(.045,.022,'Measured 21 Sep 2026 · docs/data/three-stage-comparison.json · Native baselines checked against Blender evaluation.',9,MUTED)
for ext in ['svg','png']:
    fig.savefig(ROOT/f'docs/assets/three-stage-comparison.{ext}',dpi=200,facecolor='white')
plt.close(fig)
