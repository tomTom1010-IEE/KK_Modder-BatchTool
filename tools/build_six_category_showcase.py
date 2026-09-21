"""Render the measured semantic-constraint benefit separately from optimization."""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

ROOT=Path(__file__).resolve().parents[1]
cases=json.loads((ROOT/'docs/data/three-stage-comparison.json').read_text())['cases']
BLUE,INK,MUTED,GRID,BASE='#2469a6','#162839','#536477','#e4e9ef','#b7c3cf'
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':12,'text.color':INK,'svg.fonttype':'path'})
fig=plt.figure(figsize=(16,9),facecolor='white')
def text(x,y,s,size=12,color=INK,weight='normal',**kw):
    fig.text(x,y,s,fontsize=size,color=color,weight=weight,**kw)
def rule(y):
    fig.add_artist(Line2D([.045,.955],[y,y],transform=fig.transFigure,color=GRID,lw=1))
text(.045,.95,'KK MODDER BATCHTOOL  /  SIX-CATEGORY CONSTRAINTS',11,BLUE,'bold')
text(.045,.855,'100%',64,BLUE,'bold')
text(.275,.885,'fewer wrong-category vertices',29,weight='bold')
text(.277,.846,'Zero remaining in both measured cases — before response optimization.',13,MUTED)
rule(.805)
for col,c in enumerate(cases):
    left=.045+col*.50
    metrics=c['semantic_metrics']
    n=metrics['native']['forbidden_body_category_vertices']
    s=metrics['six_category']['forbidden_body_category_vertices']
    stronger=metrics['native_body_dynamic_budget']['forbidden_body_category_vertices']
    reduction=100*(n-s)/n
    assert n>0 and s==0 and reduction==100
    text(left,.755,c['family']+' → KK',19,weight='bold')
    text(left,.72,('Neon Vertex closed jacket' if col==0 else 'Liv skirt outfit')+f'  ·  {c["vertices"]:,} vertices',12,MUTED)
    text(left,.655,f'{n:,} → {s}',35,BLUE,'bold')
    text(left+.28,.655,f'−{reduction:.0f}%',26,BLUE,'bold')
    text(left,.62,'Wrong-category vertices',12,MUTED)
    ax=fig.add_axes([left+.093,.40,.31,.16])
    ax.set_xlim(0,n*1.14);ax.set_ylim(-.5,1.5)
    ax.set_yticks([1,0],['Native','Six-category'])
    ax.set_xticks([0,7,14,21,28] if col==0 else [0,500,1000,1500,2000])
    ax.tick_params(length=0,colors=MUTED,labelsize=10)
    ax.grid(axis='x',color=GRID,zorder=0)
    ax.barh(1,n,height=.34,color=BASE,zorder=2)
    ax.plot(0,0,marker='|',markersize=24,markeredgewidth=3,color=BLUE,clip_on=False)
    ax.text(n+n*.03,1,f'{n:,}',va='center',fontsize=12,weight='bold')
    ax.text(n*.035,0,'0  ·  no remaining violations',va='center',fontsize=12,color=BLUE,weight='bold')
    ax.set_xlabel('Number of vertices · lower is better',fontsize=10,color=MUTED,labelpad=9)
    for side in ['top','left','right']:ax.spines[side].set_visible(False)
    ax.spines['bottom'].set_color(GRID)
    text(left,.308,'BEYOND BODY / DYNAMIC TOTALS',10,BLUE,'bold')
    text(left,.272,f'{stronger:,} → 0  |  100% reduction',20,weight='bold')
    text(left,.24,'Even when the native baseline already preserves',11,MUTED)
    text(left,.218,'the total body share and original dynamic weights.',11,MUTED)
rule(.188)
text(.045,.15,'Measured metric: source body-category share ≤ 1e-8, transferred share > 1e-5; each affected vertex counted once.',10,MUTED)
text(.045,.123,'Native: Blender nearest-face body transfer. Six-category: configured initialization, including reviewed finger and bnip policies.',10,MUTED)
text(.045,.096,'Independent count scales; same fitted geometry per case. Local results, not 100% overall accuracy or a collision-free guarantee.',10,MUTED)
text(.045,.051,'Data: docs/data/three-stage-comparison.json  ·  Measured 21 Sep 2026  ·  No response optimization needed for this result.',9.5,MUTED)
for ext in ['png','svg']:
    fig.savefig(ROOT/f'docs/assets/six-category-showcase.{ext}',dpi=200,facecolor='white')
plt.close(fig)
