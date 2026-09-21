"""Persistent scene UI for the reviewed flat-shoe workflow. No JSON required."""
import json
from datetime import datetime
from pathlib import Path
from .ui_messages import format_message as _fmt
import bpy
from mathutils import Vector
from . import weights_features as wf, weights_optimization as kin
from . import shoe_workflow as engine, shoe_presets, vrc_bone_rules as vr
from .workflow import target_region
from .workflow_presets import discover_roots
from .region_patterns import suggest_pattern


def mesh_poll(self,obj):return obj.type=='MESH'
def invalidate(self,context):
    p=getattr(context.scene,'kkvrc_shoes',None)
    if p:p.scan_stamp=''


class KKVRC_ShoeBone(bpy.types.PropertyGroup):
    name:bpy.props.StringProperty()
    role:bpy.props.EnumProperty(name='Ownership',items=[('REVIEW','Unassigned',''),('BODY','Body bone',''),('DYNAMIC','Lace dynamic bone','')],default='REVIEW')
    side:bpy.props.EnumProperty(name='Side',items=[('NONE','Unassigned',''),('L','Left',''),('R','Right','')],default='NONE')
    enabled:bpy.props.BoolProperty(name='Include in sampling',default=False)


class KKVRC_ShoeRoot(bpy.types.PropertyGroup):
    name:bpy.props.StringProperty()
    members:bpy.props.StringProperty()
    side:bpy.props.EnumProperty(name='Side',items=[('NONE','Unassigned',''),('L','Left',''),('R','Right','')],default='NONE')
    suggestion:bpy.props.StringProperty()
    details:bpy.props.StringProperty()
    mode:bpy.props.EnumProperty(name='Body-follow mode',items=[('REVIEW','Needs review',''),('EDGE_GRADIENT','Boundary gradient',''),('UNIFORM','Uniform follow',''),('ZERO','Dynamic only',''),('MANUAL','Analyzed per vertex','Enter the analysis conclusion; unknown modes are not supported automatically')],default='REVIEW')
    reviewed:bpy.props.BoolProperty(name='Region and shares reviewed',default=False)
    note:bpy.props.StringProperty(name='Analysis conclusion')


class KKVRC_ShoeSide(bpy.types.PropertyGroup):
    name:bpy.props.StringProperty()
    foot:bpy.props.StringProperty(name='Ankle motion bone')
    toes:bpy.props.StringProperty(name='Forefoot motion bone')
    forward:bpy.props.FloatVectorProperty(name='Forward direction (world)',size=3,default=(0,-1,0))
    up:bpy.props.FloatVectorProperty(name='Up direction (world)',size=3,default=(0,0,1))


class KKVRC_ShoeSettings(bpy.types.PropertyGroup):
    source:bpy.props.PointerProperty(name='Original shoes (complete source weights)',type=bpy.types.Object,poll=mesh_poll,update=invalidate)
    target:bpy.props.PointerProperty(name='Fitted shoes',type=bpy.types.Object,poll=mesh_poll,update=invalidate)
    body:bpy.props.PointerProperty(name='Target body',type=bpy.types.Object,poll=mesh_poll,update=invalidate)
    source_bones:bpy.props.CollectionProperty(type=KKVRC_ShoeBone)
    target_bones:bpy.props.CollectionProperty(type=KKVRC_ShoeBone)
    roots:bpy.props.CollectionProperty(type=KKVRC_ShoeRoot)
    sides:bpy.props.CollectionProperty(type=KKVRC_ShoeSide)
    source_index:bpy.props.IntProperty()
    target_index:bpy.props.IntProperty()
    root_index:bpy.props.IntProperty()
    scan_stamp:bpy.props.StringProperty()
    roots_signature:bpy.props.StringProperty()
    manual_direction:bpy.props.BoolProperty(name='Manually set foot bones and directions',default=False)
    edit_pose_preset:bpy.props.BoolProperty(name='Edit pose preset',default=False)
    advanced_parameters:bpy.props.BoolProperty(name='Advanced sampling and optimization',default=False)
    show_config_files:bpy.props.BoolProperty(name='Configuration files and naming',default=False)
    show_bones:bpy.props.BoolProperty(name='Show body and candidate bones',default=False)
    spatial_reviewed:bpy.props.BoolProperty(name='Use target foot distribution and preserve source body/dynamic shares',default=False)
    extend_toe:bpy.props.BoolProperty(name='Extend long toe caps',default=True)
    smoothing:bpy.props.FloatProperty(name='Continuity smoothing strength',default=.7,min=0,max=10)
    candidate_rings:bpy.props.IntProperty(name='Candidate topology expansion rings',default=2,min=0,max=8)
    minimum_sample_mass:bpy.props.FloatProperty(name='Minimum trusted sample mass',default=.01,min=.00001,max=1)
    prior:bpy.props.FloatProperty(name='Regularization toward A',default=.1,min=.0001,max=10)
    optimize_gap:bpy.props.BoolProperty(name='Include gap optimization B in one-click runs',default=True)
    random_enabled:bpy.props.BoolProperty(name='Low-weight random auxiliary poses',default=True)
    random_count:bpy.props.IntProperty(name='Random pose count',default=6,min=0,max=64)
    random_weight:bpy.props.FloatProperty(name='Auxiliary pose weight',default=.15,min=.001,max=.99)
    seed:bpy.props.IntProperty(name='Random seed',default=20260919,min=0)
    directory:bpy.props.StringProperty(name='Output directory',subtype='DIR_PATH')
    prefix:bpy.props.StringProperty(name='Copy name prefix',default='Shoes.Flat')
    last_directory:bpy.props.StringProperty(subtype='DIR_PATH')
    status:bpy.props.StringProperty(default='Select objects and scan')
    report:bpy.props.StringProperty()
    baseline:bpy.props.PointerProperty(type=bpy.types.Object)
    optimized:bpy.props.PointerProperty(type=bpy.types.Object)


class KKVRC_UL_shoe_bones(bpy.types.UIList):
    def draw_item(self,context,layout,data,item,icon,active_data,active_propname,index):
        row=layout.row(align=True);row.label(text=item.name)
        if self.list_id=='target':row.prop(item,'enabled',text='')
        else:row.prop(item,'role',text='')
        row.prop(item,'side',text='')


class KKVRC_UL_shoe_roots(bpy.types.UIList):
    def draw_item(self,context,layout,data,item,icon,active_data,active_propname,index):
        row=layout.row(align=True);row.label(text=item.name);row.label(text=item.suggestion)
        row.prop(item,'reviewed',text='')


def objects(p):
    if not all([p.source,p.target,p.body]):raise ValueError('Select the original shoes, fitted shoes, and target body')
    if len({p.source,p.target,p.body})!=3:raise ValueError('The three inputs must be different objects')
    if bpy.context.mode!='OBJECT':raise ValueError('Switch to Object Mode first')
    sr,tr,br=[kin._rig(o) for o in [p.source,p.target,p.body]]
    if tr!=br or sr==tr:raise ValueError('Fitted shoes and body must share the target rig; original shoes require a separate source rig')
    if wf.topology(p.source)!=wf.topology(p.target):raise ValueError('Original and fitted shoe topology does not match')
    return sr,tr


def role_signature(p):
    return json.dumps([(x.name,x.role,x.side) for x in p.source_bones])


def scan_roots(p):
    sr,_=objects(p);roles={x.name:x.role for x in p.source_bones}
    weighted={n for r in wf.read_weights(p.source) for n in r}
    parents={b.name:b.parent.name if b.parent else None for b in sr.data.bones}
    known={n for n,v in vr.VRC_WEIGHT_POLICIES.items() if v.source_role=='BODY'}
    discovered=discover_roots(parents,roles,weighted,known)
    p.roots.clear();rows=wf.read_weights(p.source);edges=[tuple(e.vertices) for e in p.source.data.edges]
    body={n for n,r in roles.items() if r=='BODY'};dyn=weighted-body
    entries={x.name:x for x in p.source_bones}
    for root,members in discovered.items():
        members=[n for n in members if n not in body]
        if not members:continue
        r=p.roots.add();r.name=root;r.members=json.dumps(members)
        side_set={entries[n].side for n in members};r.side=next(iter(side_set)) if len(side_set)==1 else 'NONE'
        ids=[i for i,row in enumerate(rows) if any(row.get(n,0)>1e-8 for n in members)]
        report=suggest_pattern(rows,edges,body,dyn,ids)
        r.suggestion=report['mode'];r.details=report.get('reason','')
        r.mode=report['mode'] if report['mode'] in {'UNIFORM','EDGE_GRADIENT'} else 'REVIEW'
        if ids and all(sum(rows[i].get(n,0) for n in body)==0 for i in ids):r.mode='ZERO';r.suggestion='ZERO'
    p.roots_signature=role_signature(p)


def infer_directions(p):
    _,rig=objects(p)
    values=[]
    for side in p.sides:
        foot=rig.data.bones.get(side.foot);toes=rig.data.bones.get(side.toes)
        if not foot or not toes:raise ValueError('Foot motion bones not recognized; set them manually')
        forward=rig.matrix_world.to_3x3()@(toes.head_local-foot.head_local)
        shin=rig.data.bones.get('cf_j_leg03_'+side.name)
        if not shin:raise ValueError('Lower-leg reference bone not recognized; set directions manually')
        up=rig.matrix_world.to_3x3()@(shin.head_local-foot.head_local)
        if up.length<1e-8:raise ValueError('Lower-leg reference is too short; set directions manually')
        up.normalize();forward-=up*forward.dot(up)
        if forward.length<1e-8:raise ValueError('Cannot infer direction from joints; set it manually')
        values.append((side,forward.normalized(),up))
    for side,forward,up in values:side.forward=forward;side.up=up


def scan(p):
    sr,tr=objects(p);p.source_bones.clear();p.target_bones.clear();p.sides.clear()
    for side in ['L','R']:
        s=p.sides.add();s.name=side
        if f'cf_j_foot_{side}' in tr.data.bones:s.foot=f'cf_j_foot_{side}'
        if f'cf_j_toes_{side}' in tr.data.bones:s.toes=f'cf_j_toes_{side}'
    for n in sorted({n for r in wf.read_weights(p.source) for n in r}):
        x=p.source_bones.add();x.name=n;policy=vr.VRC_WEIGHT_POLICIES.get(n)
        if policy and policy.source_role=='BODY' and policy.budget_region in {'LEG_L','LEG_R'}:
            x.role='BODY';x.side=policy.budget_region[-1]
        else:
            bone=sr.data.bones.get(n)
            while bone:
                known=vr.VRC_WEIGHT_POLICIES.get(bone.name)
                if known and known.source_role=='BODY':
                    if known.budget_region in {'LEG_L','LEG_R'}:x.side=known.budget_region[-1]
                    break
                bone=bone.parent
            # Unknown bones remain REVIEW until explicitly classified by the user.
    for n in sorted(wf.body_weight_support(p.body,p.target)):
        x=p.target_bones.add();x.name=n;r=target_region(n)
        if r in {'LEG_L','LEG_R'}:x.side=r[-1]
        # Conservative KK lower-leg suggestions, verified against actual support.
        x.enabled=x.side!='NONE' and any(n.startswith(a) for a in ['cf_j_foot_','cf_j_toes_','cf_s_leg','cf_s_knee','cf_d_knee'])
    scan_roots(p);p.scan_stamp=wf.stamp(p.source);p.spatial_reviewed=False
    p.status=_fmt('Scan complete: {v0} source groups, {v1} lace regions awaiting review', v0=len(p.source_bones), v1=len(p.roots))
    if not p.manual_direction:
        try:infer_directions(p)
        except ValueError as exc:p.manual_direction=True;p.status+='；'+str(exc)


def config(p):
    sr,tr=objects(p)
    if not p.scan_stamp or wf.stamp(p.source)!=p.scan_stamp:raise ValueError('Source shoes or inputs changed; rescan')
    if p.roots_signature!=role_signature(p):raise ValueError('Source ownership changed; refresh dynamic regions')
    if not p.spatial_reviewed:raise ValueError('Confirm use of the target foot spatial distribution')
    used={n for r in wf.read_weights(p.source) for n in r}
    if used!={x.name for x in p.source_bones}:raise ValueError('Source bone list is stale')
    if any(x.role=='REVIEW' or x.side=='NONE' for x in p.source_bones):raise ValueError('Some source bone roles or sides remain unassigned')
    review={};covered=set()
    for r in p.roots:
        if not r.reviewed or r.mode=='REVIEW' or r.side=='NONE':raise ValueError('Review each lace root region: '+r.name)
        if r.mode=='MANUAL' and not r.note.strip():raise ValueError('Analyze this region per vertex and enter a conclusion: '+r.name)
        members=json.loads(r.members)
        if covered.intersection(members):raise ValueError('Dynamic root regions overlap')
        covered.update(members)
        if any(x.role!='DYNAMIC' or x.side!=r.side for x in p.source_bones if x.name in members):raise ValueError('Root region conflicts with bone roles: '+r.name)
        review[r.name]={'mode':r.mode,'members':members,'note':r.note}
    if covered!={x.name for x in p.source_bones if x.role=='DYNAMIC'}:raise ValueError('Some dynamic bones are outside reviewed regions')
    sides=[];support=wf.body_weight_support(p.body,p.target)
    for s in p.sides:
        sb=[x.name for x in p.source_bones if x.side==s.name and x.role=='BODY']
        dy=[x.name for x in p.source_bones if x.side==s.name and x.role=='DYNAMIC']
        if not sb and not dy:continue
        tb=[x.name for x in p.target_bones if x.side==s.name and x.enabled]
        if not sb:raise ValueError('The shoe workflow requires body reference vertices on each side')
        if not tb or set(tb)-support:raise ValueError('Target candidates must have positive weights on the current body')
        if s.foot not in tr.data.bones or s.toes not in tr.data.bones:raise ValueError('Select ankle and forefoot motion bones')
        sides.append({'name':s.name,'source_body':sb,'dynamic':dy,'target_body':tb,
                      'foot':s.foot,'toes':s.toes,'forward':list(s.forward),'up':list(s.up)})
    preset={'id':'FLAT_SHOE_V1','random_enabled':p.random_enabled,'random_count':p.random_count,'random_weight':p.random_weight,'seed':p.seed}
    c={'source':p.source.name,'target':p.target.name,'body':p.body.name,'prefix':p.prefix,
       'sides':sides,'reviewed_dynamic_policy':{'target_spatial_distribution':True,'regions':review},
       'extend_toe':p.extend_toe,'smoothing':p.smoothing,'candidate_rings':p.candidate_rings,
       'minimum_sample_mass':p.minimum_sample_mass,'prior':p.prior,'optimize_gap':p.optimize_gap,'pose_preset':preset}
    resolved=shoe_presets.resolve(c)
    if any(x['bone'] not in tr.pose.bones for pose in resolved['poses'] for x in pose['controls']):raise ValueError('Pose control bone does not exist')
    return c


def load_config(p,c,trust_review=False):
    p.source=bpy.data.objects.get(c['source']);p.target=bpy.data.objects.get(c['target']);p.body=bpy.data.objects.get(c['body'])
    scan(p)
    for x in p.source_bones:
        for side in c['sides']:
            if x.name in side['source_body']:x.role='BODY';x.side=side['name']
            elif x.name in side['dynamic']:x.role='DYNAMIC';x.side=side['name']
    scan_roots(p)
    for r in p.roots:
        r.reviewed=trust_review
        reviewed=c.get('reviewed_dynamic_policy',{})
        entry=reviewed.get('regions',{}).get(r.name,{}) if isinstance(reviewed,dict) else {}
        if entry:
            r.mode=entry.get('mode',r.mode);r.note=entry.get('note','')
        elif trust_review and r.mode=='REVIEW':
            r.mode='MANUAL'
            key=r.name.split('_')[1] if '_' in r.name else r.name
            r.note=reviewed.get(key,'Checked against the accepted configuration; preserve original per-vertex mixed shares') if isinstance(reviewed,dict) else str(reviewed)
    for x in p.target_bones:
        x.enabled=False
        for side in c['sides']:
            if x.name in side['target_body']:x.enabled=True;x.side=side['name']
    for s in p.sides:
        entry=next((x for x in c['sides'] if x['name']==s.name),None)
        if entry:
            for key in ['foot','toes','forward','up']:setattr(s,key,entry[key])
    for key in ['prefix','extend_toe','smoothing','candidate_rings','minimum_sample_mass','prior','optimize_gap']:
        if key in c:setattr(p,key,c[key])
    for key in ['random_enabled','random_count','random_weight','seed']:
        if key in c.get('pose_preset',{}):setattr(p,key,c['pose_preset'][key])
    p.spatial_reviewed=trust_review


def show(p,obj):
    if obj is None:raise ValueError('This result has not been generated')
    for other in [p.target,p.baseline,p.optimized]:
        if other:other.hide_set(other!=obj)
    bpy.ops.object.select_all(action='DESELECT');obj.hide_set(False);obj.select_set(True)
    bpy.context.view_layer.objects.active=obj


class KKVRC_OT_shoe_action(bpy.types.Operator):
    bl_idname='kkvrc.shoe_action';bl_label='Shoe weight workflow'
    action:bpy.props.StringProperty()
    index:bpy.props.IntProperty(default=-1)
    def execute(self,context):
        p=context.scene.kkvrc_shoes
        try:
            if context.mode!='OBJECT':bpy.ops.object.mode_set(mode='OBJECT')
            if self.action=='SCAN':scan(p)
            elif self.action=='ROOTS':scan_roots(p);p.status='Regions refreshed; review each entry'
            elif self.action=='CLASSIFY_ROOT':
                r=p.roots[p.root_index]
                if r.side=='NONE':raise ValueError('Assign a side to this root region first')
                for x in p.source_bones:
                    if x.name in json.loads(r.members):x.role='DYNAMIC';x.side=r.side
                p.roots_signature=role_signature(p);r.reviewed=False
                p.status='Root chain marked as dynamic; review its mode'
            elif self.action=='DIRECTION':
                infer_directions(p)
                p.status='Foot directions inferred from the target rig'
            elif self.action=='SELECT_ROOT':
                r=p.roots[p.root_index];members=set(json.loads(r.members));rows=wf.read_weights(p.source)
                show(p,p.target)
                for v in p.target.data.vertices:v.select=any(rows[v.index].get(n,0)>1e-8 for n in members)
                bpy.ops.object.mode_set(mode='EDIT')
            elif self.action=='CHECK':
                c=config(p);poses=shoe_presets.resolve(c)['poses']
                p.status=_fmt('Checks passed: {v0} training / {v1} validation poses', v0=sum((not x['validation'] for x in poses)), v1=sum((x['validation'] for x in poses)))
            elif self.action in {'A','ALL','B'}:
                c=config(p)
                if self.action=='B':
                    if not p.last_directory:raise ValueError('Generate A first')
                    c['optimize_gap']=True;directory=Path(p.last_directory)
                    report=engine.resume_gap(p.source,p.target,p.body,c,directory)
                else:
                    if not p.directory:raise ValueError('Choose an output directory')
                    p.baseline=None;p.optimized=None;p.report=''
                    directory=Path(bpy.path.abspath(p.directory))/datetime.now().strftime('shoe-%Y%m%d-%H%M%S-%f')
                    p.last_directory=str(directory)
                    report=engine.run(p.source,p.target,p.body,c,directory,field_only=self.action=='A')
                p.baseline=bpy.data.objects.get(report['baseline']);p.optimized=bpy.data.objects.get(report.get('optimized') or '')
                p.report=json.dumps(report,ensure_ascii=False)
                show(p,p.optimized or p.baseline)
                p.status='A generated; ready to optimize B' if self.action=='A' else ('B passed numerical validation' if report.get('accepted') else 'Keeping A; B was disabled or failed validation. See the report')
            elif self.action=='SHOW_A':show(p,p.baseline)
            elif self.action=='SHOW_B':show(p,p.optimized)
            elif self.action=='SHOW_ORIGINAL':show(p,p.target)
            elif self.action=='REPORT':
                if not p.last_directory:raise ValueError('No result report yet')
                bpy.ops.wm.path_open(filepath=p.last_directory)
            return {'FINISHED'}
        except Exception as e:
            p.status=str(e);self.report({'ERROR'},str(e));return {'CANCELLED'}


class KKVRC_OT_shoe_json(bpy.types.Operator):
    bl_idname='kkvrc.shoe_json';bl_label='Shoe configuration file'
    filepath:bpy.props.StringProperty(subtype='FILE_PATH')
    filter_glob:bpy.props.StringProperty(default='*.json',options={'HIDDEN'})
    export:bpy.props.BoolProperty(default=False)
    def invoke(self,context,event):
        context.window_manager.fileselect_add(self);return {'RUNNING_MODAL'}
    def execute(self,context):
        p=context.scene.kkvrc_shoes
        try:
            if context.mode!='OBJECT':bpy.ops.object.mode_set(mode='OBJECT')
            if self.export:
                Path(self.filepath).write_text(json.dumps(config(p),ensure_ascii=False,indent=2),encoding='utf-8')
                p.status='Configuration exported'
            else:
                c=json.loads(Path(self.filepath).read_text(encoding='utf-8-sig'));load_config(p,c)
                p.directory=str(Path(self.filepath).parent);p.status='Configuration loaded; review dynamic regions and spatial policy'
            return {'FINISHED'}
        except Exception as e:p.status=str(e);self.report({'ERROR'},str(e));return {'CANCELLED'}


def button(layout,text,action,enabled=True):
    row=layout.row();row.enabled=enabled;row.operator('kkvrc.shoe_action',text=text).action=action


class KKVRC_PT_shoe_panel(bpy.types.Panel):
    bl_label='Complex Flat-Shoe Weight Transfer';bl_idname='KKVRC_PT_shoe_panel'
    bl_order=1
    bl_space_type='VIEW_3D';bl_region_type='UI';bl_category='KK/VRC Tools'
    def draw(self,context):
        p=context.scene.kkvrc_shoes;layout=self.layout
        box=layout.box();box.label(text='1 · Inputs and scan')
        for key in ['source','target','body']:box.prop(p,key)
        button(box,'Scan bones and lace root regions','SCAN')
        box=layout.box();box.label(text='2 · Review body and lace regions')
        box.prop(p,'show_bones')
        if p.show_bones:
            box.label(text='Source bones: manually assign roles and sides for unknown entries')
            box.template_list('KKVRC_UL_shoe_bones','source',p,'source_bones',p,'source_index',rows=5)
            button(box,'Refresh dynamic regions after editing roles','ROOTS')
            box.label(text='Target candidates: only bones with positive body weights')
            box.template_list('KKVRC_UL_shoe_bones','target',p,'target_bones',p,'target_index',rows=5)
        box.template_list('KKVRC_UL_shoe_roots','',p,'roots',p,'root_index',rows=4)
        if p.roots and 0<=p.root_index<len(p.roots):
            r=p.roots[p.root_index];box.label(text=r.name);box.prop(r,'side')
            row=box.row(align=True);button(row,'Mark this root chain as dynamic','CLASSIFY_ROOT');button(row,'Show mesh region','SELECT_ROOT')
            box.prop(r,'mode');box.label(text=r.details[:60])
            if r.mode=='MANUAL':box.prop(r,'note')
            box.prop(r,'reviewed')
        box.prop(p,'spatial_reviewed')
        box=layout.box();box.label(text='3 · Directions, extension, and continuity')
        box.prop(p,'manual_direction')
        if p.manual_direction:
            rig=next((m.object for m in p.target.modifiers if m.type=='ARMATURE'),None) if p.target else None
            for s in p.sides:
                col=box.box();col.label(text='Left foot' if s.name=='L' else 'Right foot')
                for key in ['foot','toes']:
                    if rig:col.prop_search(s,key,rig.data,'bones')
                    else:col.prop(s,key)
                col.prop(s,'forward');col.prop(s,'up')
            button(box,'Infer foot directions from motion joints','DIRECTION')
        box.prop(p,'advanced_parameters')
        if p.advanced_parameters:
            for key in ['extend_toe','smoothing','candidate_rings','minimum_sample_mass']:box.prop(p,key)
        box=layout.box();box.label(text='4 · Flat-shoe pose presets and optimization')
        box.label(text='7 standard training poses × 1.0; 4 held-out validation poses')
        box.prop(p,'edit_pose_preset')
        if p.edit_pose_preset:
            box.prop(p,'random_enabled');col=box.column();col.enabled=p.random_enabled
            for key in ['random_count','random_weight','seed']:col.prop(p,key)
            box.label(text='Random: ankle ±15°, forefoot -8 to 12°, tilt ±6°')
            weight=min(p.random_weight,1.4/max(p.random_count,1))
            box.label(text=_fmt('Effective random weight: {v0:.3f} per pose; total capped at 1.4', v0=weight))
        box.prop(p,'optimize_gap')
        if p.advanced_parameters:box.prop(p,'prior')
        box=layout.box();box.label(text='5 · Run and results')
        box.prop(p,'directory');button(box,'Check configuration','CHECK')
        checkpoint=bool(p.last_directory and (Path(p.last_directory)/'field-context.json').exists())
        row=box.row(align=True);button(row,'Build A: sampling and continuity','A');button(row,'Optimize B from A','B',bool(p.baseline and checkpoint))
        button(box,'Run all (preserve original shoes)','ALL')
        box.label(text=p.status[:85])
        if p.baseline:box.label(text='A：'+p.baseline.name)
        if p.optimized:box.label(text='B：'+p.optimized.name)
        if p.report:
            try:
                r=json.loads(p.report)
                if 'baseline_validation' in r:
                    a=r['baseline_validation']['distance_rms'];b=r['optimized_validation']['distance_rms']
                    box.label(text=_fmt('Gap RMS: A {v0:.6g} / B {v1:.6g}', v0=a, v1=b))
            except (ValueError,KeyError):pass
        row=box.row(align=True)
        button(row,'Original shoes','SHOW_ORIGINAL',bool(p.target));button(row,'A','SHOW_A',bool(p.baseline));button(row,'B','SHOW_B',bool(p.optimized))
        button(box,'Open run report directory','REPORT',bool(p.last_directory))
        layout.prop(p,'show_config_files')
        if p.show_config_files:
            layout.prop(p,'prefix')
            row=layout.row(align=True);row.operator('kkvrc.shoe_json',text='Import configuration (optional)').export=False
            row.operator('kkvrc.shoe_json',text='Export configuration').export=True
        layout.label(text='Flat shoes only; save the blend file to retain model results')


CLASSES=(KKVRC_ShoeBone,KKVRC_ShoeRoot,KKVRC_ShoeSide,KKVRC_ShoeSettings,
         KKVRC_UL_shoe_bones,KKVRC_UL_shoe_roots,KKVRC_OT_shoe_action,KKVRC_OT_shoe_json,KKVRC_PT_shoe_panel)
