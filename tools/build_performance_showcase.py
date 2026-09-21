"""Render the reviewed case-study extract. Requires matplotlib; no Blender access.

Run from any directory: python tools/build_performance_showcase.py
The figure compares each case with its own baseline, not one case with another.
"""
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

ROOT = Path(__file__).resolve().parents[1]
DATA = json.loads((ROOT / 'docs/data/performance-showcase.json').read_text())
INK, MUTED, GRID = '#162839', '#536477', '#e4e9ef'
BLUE, GOLD, BASE = '#2469a6', '#a36b13', '#c5ced8'
plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 11,
                     'text.color': INK, 'axes.labelcolor': MUTED,
                     'xtick.color': MUTED, 'svg.fonttype': 'path'})
fig = plt.figure(figsize=(16, 10.5), facecolor='white')

def text(x, y, s, size=12, color=INK, weight='normal', **kw):
    return fig.text(x, y, s, fontsize=size, color=color, weight=weight, **kw)

def rule(y):
    fig.add_artist(Line2D([.045, .955], [y, y], transform=fig.transFigure,
                          color=GRID, lw=1))

text(.045, .955, 'KK MODDER BATCHTOOL  /  LOCAL CASE STUDIES', 11, BLUE, 'bold')
text(.045, .907, 'Refine motion. Preserve influence.', 29, weight='bold')
text(.045, .872, 'VRC and MMD source rigs → KK  |  Measured optimization outcomes', 14, MUTED)
rule(.846)

vrc = [r for r in DATA['rows'] if r['source_family'] == 'VRC']
mmd = [r for r in DATA['rows'] if r['source_family'] == 'MMD']
text(.045, .789, f"{vrc[1]['reduction_percent']:.2f}%", 33, BLUE, 'bold')
text(.045, .76, 'lower VRC jacket terminal-response RMS', 12)
text(.535, .789, f"{DATA['mmd_writeback']['macro_budget_max_error']:.2e}", 33, GOLD, 'bold')
text(.535, .76, 'maximum MMD macro writeback budget error', 12)
rule(.736)

text(.045, .698, '01  VRC → KK', 17, BLUE, 'bold')
text(.535, .698, '02  MMD → KK', 17, GOLD, 'bold')
text(.045, .674, 'Neon Vertex · jacket and flat shoes', 11, MUTED)
text(.535, .674, 'Liv skirt outfit · frozen fitted-mesh source reference', 11, MUTED)

def panel(left, rows, labels, color):
    # Identical zero-based scale in both panels; gains never use a cropped axis.
    ax = fig.add_axes([left, .327, .418, .304])
    ax.set_xlim(0, 115)
    ax.set_ylim(-.32, 3.15)
    ax.set_yticks([])
    ax.set_xticks([0, 25, 50, 75, 100])
    ax.set_xlabel('Relative error  ·  each baseline = 100  ·  lower is better', fontsize=10, labelpad=10)
    ax.grid(axis='x', color=GRID, lw=.8, zorder=0)
    ax.tick_params(axis='x', length=0, labelsize=10)
    for side in ['top','left','right']: ax.spines[side].set_visible(False)
    ax.spines['bottom'].set_color(GRID)
    for i, (r, label) in enumerate(zip(rows, labels)):
        y = 2.70-i*1.10
        before, after = r['before'], r['after']
        relative = after / before * 100
        gain = (1-after/before)*100
        ax.text(0,y+.28,label,fontsize=11,weight='bold')
        ax.barh(y,100,height=.11,color=BASE,zorder=2)
        ax.barh(y-.16,relative,height=.11,color=color,zorder=2)
        digits = 3 if gain < .1 else 2
        ax.text(114,y-.10,f'−{gain:.{digits}f}%',fontsize=11,color=color,ha='right',weight='bold')
        ax.text(0,y-.40,f'RMS  {before:.8f} → {after:.8f}',fontsize=9.5,color=MUTED)
    if len(rows)==2:
        ax.text(0,.49,'18 macro + 29 terminal poses evaluated',fontsize=11,weight='bold',color=color)
        ax.text(0,.24,'Includes 4 macro / 8 terminal held-out poses.',fontsize=10,color=MUTED)
        ax.text(0,.00,'Small incremental gains; source behavior retained.',fontsize=10,color=MUTED)
    return ax

panel(.045,vrc,['Jacket · macro response | 8,885 vertices',
                'Jacket · terminal response | 1,514 vertices',
                'Flat shoes · separation | field A → refined B'],BLUE)
panel(.535,mmd,['Skirt outfit · macro response | 4,009 vertices',
                'Skirt outfit · terminal response | 986 vertices'],GOLD)

fig.legend(handles=[Line2D([0],[0],color=BASE,lw=6,label='Before'),
                    Line2D([0],[0],color=BLUE,lw=6,label='After · VRC'),
                    Line2D([0],[0],color=GOLD,lw=6,label='After · MMD')],
           loc='center',bbox_to_anchor=(.5,.265),ncol=3,frameon=False,fontsize=10)
rule(.244)
text(.045,.21,'VRC: INDEPENDENT SHOE CHECK',10,BLUE,'bold')
text(.045,.182,'0 detected in-scope intersections',14,weight='bold')
text(.045,.156,'Across four held-out poses; seven standard training poses.',10,MUTED)
text(.535,.21,'MMD: AUTHORED DYNAMICS PRESERVED',10,GOLD,'bold')
text(.535,.182,'0 measured dynamic-weight change',14,weight='bold')
text(.535,.156,'Terminal audit: geometry and exterior weights unchanged.',10,MUTED)
rule(.134)
text(.045,.108,'Local cases, not a cross-method benchmark. RMS is in scene units; scopes and objectives differ. No aggregate score.',10,MUTED)
text(.045,.086,'MMD strict collision checks failed: cap intersections were user-reviewed; six existing non-exempt vertices remain flagged.',10,MUTED)
text(.045,.064,'MMD terminal audit found no new contact vertices outside the cap exemption. Shoe results predate random auxiliary poses.',10,MUTED)
text(.045,.031,'Source: archived validation and writeback reports · docs/data/performance-showcase.json · 21 Sep 2026',9,MUTED)

out=ROOT/'docs/assets'
for ext in ['svg','png']:
    fig.savefig(out/f'performance-showcase.{ext}',dpi=200,facecolor='white')
plt.close(fig)
print('Rendered performance-showcase.svg and performance-showcase.png')
