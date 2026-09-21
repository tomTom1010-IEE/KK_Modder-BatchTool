"""Editable scientific overview shared by the paper and GitHub project page.

All meshes, rigs, poses and fields are explanatory vector drawings. They are
not rendered case-study assets, measured weights, or additional experiments.
"""
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Polygon, Circle, Arc

ROOT = Path(__file__).resolve().parent
INK = '#243442'
MUTED = '#576c7e'
LINE = '#8ca0b0'
BLUE = '#487aaf'
TEAL = '#158b84'
PURPLE = '#8271b0'
ORANGE = '#d68b4b'
COLORS = ['#639cca', '#75bcb4', '#badbd7', '#b7a5d5', '#d8cee9', ORANGE]


def draw_architecture():
    plt.rcParams.update({'font.family':['DejaVu Sans','Arial','sans-serif'], 'mathtext.fontset':'dejavusans',
                         'pdf.fonttype':42, 'svg.fonttype':'none',
                         'svg.hashsalt':'sbcst-architecture-v1'})
    fig = plt.figure(figsize=(18,8.5), facecolor='white')
    ax = fig.add_axes([.005,.008,.99,.984])
    ax.set(xlim=(0,1800), ylim=(835,0)); ax.axis('off')

    def text(x,y,s,size=18,color=INK,weight='normal',ha='left',va='center',**kw):
        return ax.text(x,y,s,fontsize=max(14.5,size*.8),color=color,fontweight=weight,
                       ha=ha,va=va,linespacing=1.3,**kw)

    def box(x,y,w,h,fill='white',edge=LINE,r=10,lw=1.3,ls='solid'):
        p=FancyBboxPatch((x,y),w,h,boxstyle=f'round,pad=0,rounding_size={r}',
                        facecolor=fill,edgecolor=edge,linewidth=lw,linestyle=ls)
        ax.add_patch(p); return p

    def arrow(points,color=MUTED,lw=1.4,ls='solid'):
        if len(points)>2:
            xx,yy=zip(*points[:-1]);ax.plot(xx,yy,color=color,lw=lw,ls=ls)
        ax.annotate('',xy=points[-1],xytext=points[-2],
                    arrowprops={'arrowstyle':'-|>','mutation_scale':15,
                                'lw':lw,'color':color,'linestyle':ls})

    def group(x,y,w,h,letter,title,fill,edge):
        box(x,y,w,h,fill,edge,lw=1.3)
        text(x+18,y+29,letter,21,edge,'bold')
        text(x+(64 if len(letter)>1 else 53),y+29,title,21,INK,'bold')
        ax.plot([x+16,x+w-16],[y+53,y+53],color=edge,lw=.65,alpha=.4)

    def bone(points,color=INK,lw=2.4,joints=True):
        xx,yy=zip(*points);ax.plot(xx,yy,color=color,lw=lw,zorder=6,
                                    solid_capstyle='round')
        if joints:
            for x,y in points: ax.add_patch(Circle((x,y),3.8,facecolor='white',edgecolor=color,lw=1.2,zorder=7))

    def garment(cx,top,w,h,fitted=False):
        # Matching 9 x 11 vertex lattices, intentionally different fitted shape.
        points=[]
        for v in np.linspace(0,1,11):
            width=w*(.46-.10*np.sin(np.pi*v)+(.06 if fitted else .01)*v)
            row=[]
            for u in np.linspace(-1,1,9):
                yy=top+h*v + 13*(1-u*u)*(1-v)**5
                xx=cx+width*u+(.06*w*np.sin(np.pi*v) if fitted else 0)
                row.append((xx,yy))
            points.append(row)
        grid=np.array(points)
        for j in range(10):
            for i in range(8):
                shade=(.91-.10*abs((i-3.5)/4), .96-.05*abs((i-3.5)/4), .97)
                ax.add_patch(Polygon([grid[j,i],grid[j,i+1],grid[j+1,i+1],grid[j+1,i]],
                                    closed=True,facecolor=shade,edgecolor='#7599ac',lw=.5,zorder=2))
        # Visible correspondence vertices and a separately colored cloth chain.
        ax.scatter(grid[::2,::2,0].ravel(),grid[::2,::2,1].ravel(),s=3,c=BLUE,zorder=4)
        sy=top+h*.77
        bone([(cx-w*.18,sy),(cx-w*.16,sy+h*.14),(cx-w*.13,sy+h*.28)],ORANGE,1.9)
        return grid

    def rig(cx,cy,scale=1,posed=False,color=BLUE,segments=3):
        # An anatomical skeleton schematic, independent of any rig convention.
        ax.add_patch(Circle((cx,cy-48*scale),12*scale,facecolor='white',edgecolor=color,lw=1.5))
        spine=[(cx,cy+y*scale) for y in np.linspace(-32,30,segments+1)]
        bone(spine,color,2)
        bone([(cx,cy-20*scale),(cx-29*scale,cy-14*scale),(cx-53*scale,cy+((-45 if posed==2 else 18) if posed else -8)*scale)],color,2)
        bone([(cx,cy-20*scale),(cx+29*scale,cy-14*scale),(cx+48*scale,cy+((18 if posed==2 else -45) if posed else -8)*scale)],color,2)
        bone([(cx,cy+30*scale),(cx-19*scale,cy+58*scale),(cx-24*scale,cy+86*scale)],color,2)
        bone([(cx,cy+30*scale),(cx+19*scale,cy+58*scale),(cx+24*scale,cy+86*scale)],color,2)

    def lock(x,y,color=TEAL):
        ax.add_patch(Arc((x+8,y+7),11,15,theta1=180,theta2=360,color=color,lw=1.5))
        box(x,y+7,16,14,'white',color,r=2,lw=1.3)
        ax.add_patch(Circle((x+8,y+13),1.4,facecolor=color,edgecolor='none'))

    # The graph reads left to right; branch colors identify objectives, not stages.
    text(22,25,'SBCST',27,INK,'bold')
    text(190,25,'Preserve semantic allocation. Adapt within-category weights.',21,MUTED)
    group(20,68,290,678,'A','Reviewed inputs','#f2f6fb','#8ca8c7')
    group(353,68,357,678,'B','Semantic contract','#eff8f6','#62aaa3')
    group(755,68,595,316,'C1','Garment response','#f6f3fa','#a495c0')
    group(755,414,595,332,'C2','Footwear separation','#fff8ed','#d7af6c')
    group(1396,68,384,678,'D','Validation & output','#f2f6fb','#8ca8c7')

    # A: paired original/fitted garments and independently structured rigs.
    garment(95,149,108,160,False);garment(232,149,90,160,True)
    arrow([(153,228),(174,228)],BLUE)
    text(95,340,r'$X^{s}$',22,BLUE,ha='center')
    text(232,340,r'$X^{t}$',22,TEAL,ha='center')
    text(95,369,'Original',17,ha='center');text(232,369,'Fitted',17,ha='center')
    text(165,405,'Paired garment vertices',17,MUTED,ha='center')
    ax.plot([40,290],[429,429],color='#bbcad7',lw=.75)
    rig(96,507,.66,False,BLUE,2);rig(232,507,.66,False,TEAL,4)
    text(165,584,'Source / target rigs',17,ha='center')
    text(165,613,'Body topology may differ',15.8,MUTED,ha='center')
    box(38,642,254,84,'white','#c2d0da',r=6,lw=.9)
    text(165,662,'Weights + bone roles',18,weight='bold',ha='center')
    for x,color,label in [(54,BLUE,'Body'),(142,ORANGE,'Dynamic')]:
        ax.add_patch(Circle((x,695),4,facecolor=color,edgecolor='none'))
        text(x+11,695,label,16)
    arrow([(310,354),(353,354)])

    # B: conserved category masses, with free redistribution only inside a class.
    text(375,145,'Per-vertex semantic budgets',18,weight='bold')
    labels=['Torso','L arm','R arm','L leg','R leg','Dynamic']
    for k,(label,color) in enumerate(zip(labels,COLORS)):
        x=376+(k%3)*106;y=178+(k//3)*36
        box(x,y,99,28,color,color,r=4,lw=.6)
        text(x+49.5,y+14,label,15.3,ha='center')
    text(375,262,'Source',16,MUTED);text(375,315,'Target',16,MUTED)
    # Schematic shoulder vertex: torso .35, left-arm .25, dynamics .40.
    start=458; bw=228
    for row,subdiv in [(0,[2,2,3]),(1,[4,4,3])]:
        yy=247+row*53;x=start
        for mass,color,num in zip([.35,.25,.4],[COLORS[0],COLORS[1],ORANGE],subdiv):
            ax.add_patch(Polygon([(x,yy),(x+bw*mass,yy),(x+bw*mass,yy+29),(x,yy+29)],facecolor=color,edgecolor='white',lw=.8))
            for frac in np.linspace(0,1,num+1)[1:-1]:
                ax.plot([x+frac*bw*mass]*2,[yy+3,yy+26],color='white',lw=.8)
            x+=bw*mass
    for boundary in [0,.35,.60,1]:
        ax.plot([start+bw*boundary]*2,[277,298],color=TEAL,lw=.75,ls=':')
    text(532,360,r'$\sum_{j\in\mathcal{C}_r}w_{ij}=b_{ir}$',22,TEAL,ha='center')
    text(532,408,'Redistribute inside each category',16,MUTED,ha='center')
    ax.plot([375,688],[422,422],color='#bbdcd6',lw=.75)
    text(375,450,'Body-following mode review',18,weight='bold')
    # Tiny plots are schematic feature signatures, not measured data curves.
    for x,title,curve in [(385,'Uniform',np.full(20,.48)),(547,'Edge decay',np.exp(-np.linspace(0,3.4,20)))]:
        ax.plot([x,x,x+131],[477,538,538],color=LINE,lw=.8)
        xx=np.linspace(x+5,x+127,20);yy=530-curve*44
        ax.plot(xx,yy,color=TEAL,lw=2)
        text(x+65,562,title,16.5,ha='center')
    text(532,591,'Mixed / unclear: local review',16.3,ORANGE,ha='center')
    box(373,621,317,113,'white','#add5ce',r=6,lw=.9)
    lock(387,638);text(414,644,'Fixed dynamics',16)
    text(414,667,'+ selected fingers',15)
    text(388,693,'Body-supported candidates',16.1)
    text(388,716,'Zero budget blocks leakage',15.7,MUTED)
    arrow([(710,354),(732,354),(732,226),(755,226)],TEAL)
    arrow([(732,354),(732,581),(755,581)],TEAL)

    # C1: framed motion transport followed by a constrained fit and local stage.
    rig(807,181,.54,True,BLUE,2);rig(921,181,.54,True,TEAL,4)
    arrow([(844,199),(883,199)],MUTED)
    text(864,258,'Matched poses',15.8,MUTED,ha='center')
    text(990,152,'Paired-rest motion transport',18.5,weight='bold')
    text(990,190,r'$\Delta q^{t}=A\,\Delta q^{s},\quad\widehat{y}^{0}=x^{t}$',20,PURPLE)
    text(990,228,'Local frames + shape / scale map',16.2,MUTED)
    arrow([(1112,249),(1112,275)],PURPLE)
    box(779,286,245,75,'white','#b6a7cb',r=6)
    text(901,311,'Body-weight QP',17.6,weight='bold',ha='center')
    text(901,339,r'$W^0$: native / mapped',16,MUTED,ha='center')
    box(1066,286,260,75,'white','#b6a7cb',r=6,ls='--')
    text(1196,311,'Terminal refinement',18,weight='bold',ha='center')
    text(1196,339,'Local core + rings',16,MUTED,ha='center')
    arrow([(1024,323),(1066,323)],PURPLE)
    # Reference feeds the QP, not only the optional endpoint stage.
    arrow([(1112,275),(902,275),(902,286)],PURPLE,lw=1)

    # C2: a long toe box with topological field and body reference, not a shoe photo.
    verts=np.array([[789,567],[821,549],[840,489],[882,489],[900,555],
                    [956,570],[999,590],[1008,613],[975,628],[798,626],[780,609]])
    shoe=Polygon(verts,closed=True,facecolor='#e6eef4',edgecolor=BLUE,lw=1.5)
    ax.add_patch(shoe)
    for x in np.arange(797,1005,19):
        line=ax.plot([x,x-19],[482,637],color='#7399b2',lw=.7)[0];line.set_clip_path(shoe)
    for y in np.arange(503,632,18):
        line=ax.plot([778,1013],[y,y+9],color='#7399b2',lw=.7)[0];line.set_clip_path(shoe)
    body=np.array([[822,602],[843,572],[852,505],[870,505],[880,579],[946,596],[956,610],[850,613]])
    ax.add_patch(Polygon(body,closed=True,facecolor='#f5dfc4',edgecolor=ORANGE,lw=1.2,alpha=.95))
    arrow([(990,589),(953,589)],ORANGE,lw=1.8)
    ax.plot([956,956],[578,632],color=ORANGE,lw=1,ls='--')
    text(890,648,'Body / extended shoe',15.5,MUTED,ha='center')
    text(1043,497,'Native foot samples',18.5,weight='bold')
    text(1043,530,'Extend sampling queries',16.2,MUTED)
    text(1043,566,'Mesh-graph field repair',18,weight='bold')
    for k,color in enumerate(['#4479ae','#659cb9','#8ab8c0','#b3ceba','#d6ddbe']):
        x=1060+k*52
        if k: ax.plot([x-43,x-10],[603,603],color=LINE,lw=1.3)
        ax.add_patch(Circle((x,603),9,facecolor=color,edgecolor='white',lw=1))
    text(1043,636,'Local, continuous proportions',15.7,MUTED)
    box(779,669,245,55,'white','#dec397',r=6)
    text(901,697,'Field A: data + graph',17.7,weight='bold',ha='center')
    box(1066,669,260,55,'white','#dec397',r=6,ls='--')
    text(1196,697,'Optional B: gap fit',17.4,weight='bold',ha='center')
    arrow([(1024,697),(1066,697)],ORANGE)

    # Both task objectives feed the same independent acceptance stage.
    arrow([(1350,226),(1396,226)],PURPLE)
    arrow([(1350,581),(1396,581)],ORANGE)

    # D: held-out poses, invariant checks and local contact-review scope.
    text(1419,145,'Held-out pose evaluation',19,weight='bold')
    for cx,posed,col in [(1460,False,BLUE),(1577,True,TEAL),(1694,2,PURPLE)]:rig(cx,205,.53,posed,col,3)
    text(1587,275,'Response / separation metrics',16.8,MUTED,ha='center')
    ax.plot([1419,1757],[298,298],color='#bccbd6',lw=.75)
    text(1419,325,'Verify the transfer contract',18.5,weight='bold')
    for i,label in enumerate(['Budgets + fixed weights','Admitted bones + local scope','Rest geometry unchanged']):
        y=362+35*i
        # An outlined check slot denotes a test, not a claim that every input passes.
        box(1421,y-7,13,13,'white',BLUE,r=1,lw=.8)
        text(1448,y,label,16.7)
    ax.plot([1419,1757],[456,456],color='#bccbd6',lw=.75)
    text(1419,482,'Scoped contact review',18.5,weight='bold')
    # Explicitly designated local exceptions inside an otherwise checked patch.
    grid=np.array([[(1430+i*25+3*np.sin(j),519+j*20) for i in range(6)] for j in range(4)])
    for row in grid:ax.plot(row[:,0],row[:,1],color=LINE,lw=.8)
    for col in grid.transpose(1,0,2):ax.plot(col[:,0],col[:,1],color=LINE,lw=.8)
    for j in range(4):
        for i in range(6):ax.add_patch(Circle(tuple(grid[j,i]),3.2,facecolor=ORANGE if (j<2 and i>3) else BLUE,edgecolor='white',lw=.4))
    box(1516,508,53,42,'none',ORANGE,r=4,lw=1,ls='--')
    text(1590,532,'Review mask',15.8,ORANGE)
    text(1590,560,'Remaining scope',15.8,MUTED)
    text(1419,609,'Review flags stay in the report',16.5,MUTED)
    arrow([(1588,629),(1588,650)],BLUE)
    box(1418,654,339,72,'#e2efef','#579693',r=6,lw=1.1)
    # A small report icon accompanies the persistent result artifacts.
    box(1435,671,30,39,'white',TEAL,r=2,lw=1)
    for y in [681,690,699]:ax.plot([1442,1458],[y,y],color=TEAL,lw=.9)
    text(1482,677,'Result copy + report',18,weight='bold')
    text(1482,704,'Audited weight writeback',16,MUTED)

    # Bottom legend distinguishes assumptions and optional stages from evidence.
    ax.plot([20,1780],[774,774],color='#ccd6dd',lw=.7)
    text(23,805,'Shared invariants',17,TEAL,'bold')
    text(235,805,'Fixed budgets',17)
    text(409,805,'Fixed dynamics',17)
    text(615,805,'Body-supported candidates',17)
    box(948,794,30,21,'white',MUTED,r=3,ls='--',lw=1)
    text(990,805,'Optional stage',17,MUTED)
    text(1778,805,'Meshes and fields are schematic.',16,MUTED,ha='right')

    out=ROOT/'figures';out.mkdir(exist_ok=True)
    assets=ROOT.parent/'assets'
    fig.savefig(out/'pipeline.pdf',bbox_inches='tight',pad_inches=.03,
                metadata={'CreationDate':None,'ModDate':None})
    fig.savefig(out/'pipeline.svg',bbox_inches='tight',pad_inches=.03,
                metadata={'Date':None})
    fig.savefig(assets/'workflow.svg',bbox_inches='tight',pad_inches=.03,
                metadata={'Date':None})
    fig.savefig(assets/'workflow.png',bbox_inches='tight',pad_inches=.03,dpi=150)
    plt.close(fig)
    # Matplotlib's path writer leaves trailing spaces; normalize for clean diffs.
    for path in (out/'pipeline.svg', assets/'workflow.svg'):
        path.write_text('\n'.join(line.rstrip() for line in path.read_text(encoding='utf-8').splitlines())+'\n',encoding='utf-8')


if __name__=='__main__':
    draw_architecture()
    print('Updated vector architecture for paper and project page.')
