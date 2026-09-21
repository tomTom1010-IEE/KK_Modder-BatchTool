"""User-facing six-budget workflow; numerical work stays in the shared APIs."""
import json, os, shutil, subprocess, uuid, math
from pathlib import Path
from .ui_messages import format_message as _fmt
import bpy
import bmesh
import numpy as np
from . import weights_features as wf, weight_features as core
from . import weights_optimization as optimization, optimizer_validation
from . import vrc_bone_rules as vr, bone_rules, weights_body
from .workflow_regions import resolve_regions
from .workflow_presets import discover_roots, motion_templates
from .region_patterns import suggest_pattern
from .optimizer_profiles import TERMINAL
from . import mmd_weight_profiles
from mathutils import Vector, Matrix

REGIONS=[(x,x,'') for x in ('TORSO','ARM_L','ARM_R','LEG_L','LEG_R')]
FINGERS=[(x,x,'') for x in ('NONE','THUMB_L','THUMB_R','INDEX_L','INDEX_R','MIDDLE_L','MIDDLE_R','RING_L','RING_R','LITTLE_L','LITTLE_R')]
SEMANTICS=[('NONE','Unassigned','')]+[(x,x,'') for x in sorted(set(vr.VRC_MOTION_SEMANTICS.values()))]
_jobs={}
_pose_preview={}

def mesh_poll(self,obj):return obj.type=='MESH'

def invalidate_region(self,context):self.reviewed_stamp=''

def region_reviewed_get(self):return bool(self.reviewed_stamp)

def region_reviewed_set(self,value):
    p=self.id_data.kkvrc_weight_workflow
    if not value:
        self.reviewed_stamp='';p.status=self.name+': approval revoked.';return
    try:confirm_region(p,self)
    except (ValueError,TypeError,KeyError) as exc:
        self.reviewed_stamp='';p.status='Review failed: '+str(exc)

class KKVRC_WFBone(bpy.types.PropertyGroup):
    name:bpy.props.StringProperty()
    recognition:bpy.props.StringProperty(name='Recognition source')
    role:bpy.props.EnumProperty(name='Source bone role',items=[('REVIEW','Unassigned',''),('BODY','Body bone',''),('DYNAMIC','Dynamic bone',''),('IGNORE','Ignore','Only explicitly non-deforming groups may be ignored')],default='REVIEW')
    region:bpy.props.EnumProperty(name='Six-class region',items=REGIONS)
    weight_target:bpy.props.StringProperty(name='Target weight bone')
    pose_target:bpy.props.StringProperty(name='Corresponding motion bone')
    anchor:bpy.props.StringProperty(name='Source reference bone (optional)')
    finger:bpy.props.EnumProperty(name='Finger assignment',items=FINGERS)
    enabled:bpy.props.BoolProperty(name='Enable this finger (all joints must agree)',default=False)
    semantic:bpy.props.EnumProperty(name='Motion semantic',items=SEMANTICS)

class KKVRC_WFTarget(bpy.types.PropertyGroup):
    name:bpy.props.StringProperty()
    region:bpy.props.EnumProperty(name='Target region',items=REGIONS)
    reviewed:bpy.props.BoolProperty(name='Region assignment reviewed',default=False)
    finger:bpy.props.EnumProperty(name='Finger assignment',items=FINGERS)
    local:bpy.props.BoolProperty(name='Allow terminal refinement',default=False)

class KKVRC_WFRegion(bpy.types.PropertyGroup):
    name:bpy.props.StringProperty(name='Region name',default='Influence region')
    root:bpy.props.StringProperty(name='Source dynamic chain root',update=invalidate_region)
    mode:bpy.props.EnumProperty(name='Body-follow mode',items=[('REVIEW','Unrecognized / needs review','Requires per-vertex agent analysis or manual handling'),('UNIFORM','Uniform body follow','Preserve original shares and initialize with semantic mapping'),('EDGE_GRADIENT','Graded boundary attachment','Preserve original shares and allow trusted native sampling')],default='REVIEW',update=invalidate_region)
    vertices:bpy.props.StringProperty(default='',update=invalidate_region)
    topology:bpy.props.StringProperty(default='',update=invalidate_region)
    discovered:bpy.props.BoolProperty(default=False)
    suggestion:bpy.props.StringProperty(default='REVIEW')
    statistics:bpy.props.StringProperty(default='')
    reviewed_stamp:bpy.props.StringProperty(default='')
    reviewed:bpy.props.BoolProperty(name='Region mode reviewed',description='Approve this row; changing mode or scope invalidates approval. Source weights and roles are checked again before execution',get=region_reviewed_get,set=region_reviewed_set)
    show_statistics:bpy.props.BoolProperty(name='Show statistics',default=False)

class KKVRC_WFMotionPart(bpy.types.PropertyGroup):
    name:bpy.props.StringProperty(name='Target rotation-sharing bone')
    factor:bpy.props.FloatProperty(name='Rotation share',default=1,min=0,max=1)

class KKVRC_WFMotion(bpy.types.PropertyGroup):
    name:bpy.props.StringProperty(name='Pose name',default='Pose')
    source:bpy.props.StringProperty(name='Source motion bone')
    target:bpy.props.StringProperty(name='Target motion bone')
    axis:bpy.props.FloatVectorProperty(name='World rotation axis',size=3,default=(0,1,0))
    angle:bpy.props.FloatProperty(name='Training angle (degrees)',default=30,min=1,max=120)
    endpoint:bpy.props.BoolProperty(name='Use for terminal refinement',default=False)
    target_parts:bpy.props.CollectionProperty(type=KKVRC_WFMotionPart)
    separate_axis:bpy.props.BoolProperty(name='Use a separate target world axis',default=False)
    target_axis:bpy.props.FloatVectorProperty(name='Target world rotation axis',size=3,default=(0,1,0))
    preset_id:bpy.props.StringProperty()
    extra_angle:bpy.props.FloatProperty(name='Additional training angle (0 disables)',default=0,min=0,max=120)

class KKVRC_WorkflowProperties(bpy.types.PropertyGroup):
    source_profile:bpy.props.EnumProperty(name='Source rig profile',items=[('VRC','VRC','Existing VRC profile'),('MMD','Generic MMD','Use the maintained MMD convention profile'),('MMD_LIV','MMD · R4 Liv','Generic profile and existing R4 Liv research')],default='VRC')
    mmd_profile_path:bpy.props.StringProperty(name='MMD model profile (optional)',subtype='FILE_PATH')
    profile_digest:bpy.props.StringProperty()
    source_sampling:bpy.props.EnumProperty(name='Source pose sampling',items=[('FK','Standard FK/LBS','Source constraints are not supported'),('EVALUATED','Evaluate source constraints','Explicit contract; every pose must pass actual LBS validation')],default='FK')
    reference_mode:bpy.props.EnumProperty(name='Source reference mode',items=[('ORIGINAL','Original unfitted reference','Original garment with complete source weights and reliable vertex correspondence'),('FITTED','Current fitted mesh reference','Use the fitted mesh with original untransferred weights; freeze the current source motion baseline')],default='ORIGINAL')
    reference:bpy.props.PointerProperty(type=bpy.types.Object)
    reference_stamp:bpy.props.StringProperty()
    reference_structure:bpy.props.StringProperty()
    collision_policy:bpy.props.EnumProperty(name='Post-optimization collision policy',items=[('REVIEW','Save a copy and select vertices for review','Save after non-collision checks pass; the user decides whether to keep or revert'),('STRICT','Strict collision-free validation','Do not write results if collision validation fails')],default='REVIEW')
    exclude_bnip:bpy.props.BoolProperty(name='Exclude bnip and redistribute to same-side bust',default=False)
    beginner_motion:bpy.props.EnumProperty(name='Motion scope',items=[('AUTO','Automatic','Choose from recognized body-bone semantics'),('UPPER','Upper body',''),('LOWER','Lower body',''),('FULL','Full body','')],default='AUTO')
    beginner_fingers:bpy.props.BoolProperty(name='Preserve original finger influence',default=True,description='Preserve only existing finger shares; do not sample new finger influence')
    beginner_terminal:bpy.props.BoolProperty(name='Continue with terminal refinement in the specified region',default=False)
    beginner_profile:bpy.props.StringProperty()
    beginner_settings:bpy.props.StringProperty()
    beginner_summary:bpy.props.StringProperty()
    source:bpy.props.PointerProperty(name='Original garment (complete weights)',type=bpy.types.Object,poll=mesh_poll)
    target:bpy.props.PointerProperty(name='Fitted garment',type=bpy.types.Object,poll=mesh_poll)
    body:bpy.props.PointerProperty(name='Target body',type=bpy.types.Object,poll=mesh_poll)
    bones:bpy.props.CollectionProperty(type=KKVRC_WFBone)
    bone_index:bpy.props.IntProperty()
    targets:bpy.props.CollectionProperty(type=KKVRC_WFTarget)
    target_index:bpy.props.IntProperty()
    regions:bpy.props.CollectionProperty(type=KKVRC_WFRegion)
    region_index:bpy.props.IntProperty()
    motions:bpy.props.CollectionProperty(type=KKVRC_WFMotion)
    motion_index:bpy.props.IntProperty()
    motion_preset:bpy.props.EnumProperty(name='Pose preset',items=[('UPPER','Upper body','Arm raise, elbow bend, and torso'),('LOWER','Lower body','Hip, knee, and torso'),('FULL','Full body','Upper- and lower-body poses'),('WRIST','Wrist refinement','Twist, bend, and side tilt on both sides')],default='UPPER')
    motion_advanced:bpy.props.BoolProperty(name='Advanced pose settings',default=False)
    confidence:bpy.props.FloatProperty(name='Body sampling confidence',default=1,min=0,max=1)
    initial_mode:bpy.props.EnumProperty(name='Initialization source',items=[('NATIVE','Blender nearest face interpolated','Use native POLYINTERP_NEAREST only'),('EXISTING','Existing target distribution','Read reviewed target body weights using corresponding vertices'),('MAP','Semantic mapping only','No spatial transfer')],default='NATIVE')
    output:bpy.props.StringProperty(name='Run output directory',subtype='DIR_PATH')
    python:bpy.props.StringProperty(name='External Python',subtype='FILE_PATH',default='python')
    dependencies:bpy.props.StringProperty(name='Dependencies directory (optional)',subtype='DIR_PATH')
    preset:bpy.props.StringProperty(name='Configuration file',subtype='FILE_PATH')
    contacts:bpy.props.BoolProperty(name='Enable collision-constraint iterations',default=False)
    local_vertices:bpy.props.StringProperty(default='')
    local_topology:bpy.props.StringProperty(default='')
    rings:bpy.props.IntProperty(name='Terminal transition rings',default=2,min=0,max=6)
    small_angle:bpy.props.FloatProperty(name='Terminal small angle (degrees)',default=8,min=1,max=20)
    initial:bpy.props.PointerProperty(name='Six-class initialization copy',type=bpy.types.Object)
    macro:bpy.props.PointerProperty(name='Main optimization copy',type=bpy.types.Object)
    final:bpy.props.PointerProperty(name='Terminal optimization copy',type=bpy.types.Object)
    run:bpy.props.StringProperty()
    fingerprint:bpy.props.StringProperty()
    status:bpy.props.StringProperty(default='Select the three input objects, then scan bones.')
    advanced:bpy.props.BoolProperty(name='Runtime and configuration files',default=False)
    edit_pose_preset:bpy.props.BoolProperty(name='Edit pose preset',default=False)
    advanced_solver:bpy.props.BoolProperty(name='Advanced solver settings',default=False)
    show_review_bones:bpy.props.BoolProperty(name='Show body and candidate bones',default=False)
    show_source_details:bpy.props.BoolProperty(name='Selected source bone: mapping and advanced settings',default=False)
    show_target_details:bpy.props.BoolProperty(name='Selected target bone: advanced settings',default=False)

class KKVRC_UL_wf(bpy.types.UIList):
    def draw_item(self,context,layout,data,item,icon,active_data,active_propname,index):
        layout.label(text=item.name)
        if hasattr(item,'mode'):
            layout.label(text={'REVIEW':'Needs review','UNIFORM':'Uniform','EDGE_GRADIENT':'Gradient'}[item.mode])
            row=layout.row(align=True);row.enabled=item.mode!='REVIEW' or bool(item.reviewed_stamp)
            row.prop(item,'reviewed',text='')
        elif hasattr(item,'role'):
            layout.prop(item,'role',text='')
            row=layout.row(align=True);row.enabled=item.role=='BODY';row.prop(item,'region',text='')
        elif hasattr(item,'reviewed'):
            layout.prop(item,'reviewed',text='');layout.prop(item,'region',text='')
        elif hasattr(item,'endpoint'):layout.label(text='Terminal' if item.endpoint else 'Main')

def rig(obj):
    if not obj or obj.type!='MESH':raise ValueError('Select the original garment, fitted garment, and target body first')
    mods=[m for m in obj.modifiers if m.type=='ARMATURE' and m.object]
    if len(mods)!=1:raise ValueError(obj.name+': requires exactly one valid Armature modifier')
    return mods[0].object

def inputs(p):
    sr,tr,br=rig(p.source),rig(p.target),rig(p.body)
    if len({p.source,p.target,p.body})!=3 or sr==tr or tr!=br:
        raise ValueError('Source garment requires a separate rig; target body and fitted garment must share the target rig')
    if p.source.mode!='OBJECT' or p.target.mode!='OBJECT' or p.body.mode!='OBJECT':raise ValueError('Leave Edit/Weight Paint Mode on input meshes before solving')
    if wf.topology(p.source)!=wf.topology(p.target):raise ValueError('Source and target garment vertex topology does not match')
    return sr,tr

def finger_name(name):
    for side in ('L','R'):
        if not name.endswith(('.'+side,'_'+side)):continue
        for base in ('thumb','index','middle','ring','little'):
            if base in name.lower():return base.upper()+'_'+side
    return 'NONE'

def target_region(name):
    rule=bone_rules.KK_STANDARD_BODY_BONES.get(name)
    if not rule:return None
    tags=rule.regions
    if tags & {bone_rules.REGION_ARM,bone_rules.REGION_HAND}:return 'ARM_'+rule.side if rule.side else None
    if bone_rules.REGION_LEG in tags:return 'LEG_'+rule.side if rule.side else None
    if tags & {bone_rules.REGION_TORSO,bone_rules.REGION_BREAST,bone_rules.REGION_BUTT,bone_rules.REGION_LOWER_BODY}:return 'TORSO'
    if any(s in name for s in ('head','neck','face')):return 'TORSO'
    return None

def dump_settings(p):
    fields={'bones':['name','role','region','weight_target','pose_target','anchor','finger','enabled','semantic','recognition'],
            'targets':['name','region','reviewed','finger','local'],
            'regions':['name','root','mode','vertices','topology','discovered','suggestion','statistics','reviewed_stamp'],
            'motions':['name','source','target','axis','angle','endpoint','target_axis','separate_axis','preset_id','extra_angle']}
    out={k:[{f:list(getattr(x,f)) if f in {'axis','target_axis'} else getattr(x,f) for f in fs} for x in getattr(p,k)] for k,fs in fields.items()}
    for item,x in zip(out['motions'],p.motions):item['target_parts']=[{'name':part.name,'factor':part.factor} for part in x.target_parts]
    out.update(schema=1,source=p.source.name if p.source else None,target=p.target.name if p.target else None,body=p.body.name if p.body else None,
               confidence=p.confidence,initial_mode=p.initial_mode,local_vertices=p.local_vertices,local_topology=p.local_topology,rings=p.rings,small_angle=p.small_angle,contacts=p.contacts)
    for key in ['source_profile','mmd_profile_path','profile_digest','source_sampling','reference_mode','collision_policy','exclude_bnip']:out[key]=getattr(p,key)
    return out

def fingerprint(p,full=False):
    data=dump_settings(p)
    if not full:
        for key in ['motions','local_vertices','local_topology','rings','small_angle','contacts']:data.pop(key)
        for row in data['targets']:row.pop('local')
    return core.digest(data)

def config(p):
    sr,tr=inputs(p);rows=wf.read_weights(p.source)
    if p.source_profile!='VRC':
        _,_,current=mmd_weight_profiles.load(p.source_profile,bpy.path.abspath(p.mmd_profile_path) if p.mmd_profile_path else '')
        if p.profile_digest!=current:raise ValueError('MMD profile changed; save the configuration, then rescan and review')
    roles={x.name:x.role for x in p.bones}
    used={n for row in rows for n in row}
    if used-set(roles) or any(roles[n]=='REVIEW' for n in used):raise ValueError('Some source roles are unconfirmed; review the bone list')
    support=wf.body_weight_support(p.body,p.target)
    targets={x.name:x for x in p.targets}
    if support-set(targets) or any(not targets[n].reviewed for n in support):raise ValueError('Some target body six-class assignments remain unconfirmed')
    source_regions={x.name:x.region for x in p.bones if x.role=='BODY'}
    target_regions={n:targets[n].region for n in support}
    bodymap={};dynamicmap={};bonemap={};anchors={};sf={};tf={n:targets[n].finger for n in support if targets[n].finger!='NONE'};enabled=set();disabled={}
    finger_switches={}
    for x in p.bones:
        if x.role=='BODY' and x.finger!='NONE':finger_switches.setdefault(x.finger,set()).add(x.enabled)
    if any(len(values)>1 for values in finger_switches.values()):raise ValueError('All joints of a finger must share the same enabled state')
    for x in p.bones:
        if x.role=='BODY':
            if x.weight_target not in support or target_regions[x.weight_target]!=x.region:raise ValueError(x.name+': weight target is outside the body whitelist or same-side region')
            if x.pose_target not in tr.data.bones:raise ValueError(x.name+': missing valid target motion bone')
            bodymap[x.name]={x.weight_target:1.};bonemap[x.name]=x.pose_target
            if x.anchor:anchors[x.name]=x.anchor
            if x.finger!='NONE':
                sf[x.name]=x.finger
                if x.enabled:enabled.add(x.finger)
                else:
                    if x.weight_target in tf:raise ValueError(x.name+': map disabled fingers to same-side non-finger body bones')
                    disabled[x.name]={x.weight_target:1.}
        elif x.role=='DYNAMIC':
            if x.name not in tr.data.bones or not tr.data.bones[x.name].use_deform:raise ValueError(x.name+': retained dynamic bones are not attached to the target rig')
            dynamicmap[x.name]={x.name:1.}
    # Every actual source deformer must remain in the source response.
    omitted=[n for n in used if n in sr.data.bones and sr.data.bones[n].use_deform and roles[n] not in {'BODY','DYNAMIC'}]
    if omitted:raise ValueError('Effective source deform bones cannot be ignored: '+str(omitted))
    region_state=pattern_context(p)
    regions=[]
    for r in p.regions:
        if r.reviewed_stamp!=region_signature(r,region_state):raise ValueError(r.name+': not reviewed, or source weights/roles/scope changed; review again')
        bones=[]
        if r.root:
            root=sr.data.bones.get(r.root)
            if not root:raise ValueError(r.name+': source chain root does not exist')
            bones=[b.name for b in [root]+list(root.children_recursive) if roles.get(b.name)=='DYNAMIC']
        vertices=json.loads(r.vertices) if r.vertices else None
        if vertices is not None and r.topology!=wf.topology(p.source):raise ValueError(r.name+': vertex selection is stale; capture again')
        regions.append({'name':r.name,'mode':r.mode,'bones':bones,'vertices':vertices})
    modes=resolve_regions(rows,roles,regions)
    replacements={n:{'cf_s_bust03_'+n[-1]:1.} for n in support if p.exclude_bnip and 'bnip' in n}
    if any(set(mapping)-support for mapping in replacements.values()):raise ValueError('Missing same-side weighted bust compensation bone')
    if any(n in replacements for mapping in bodymap.values() for n in mapping):raise ValueError('Body mapping still targets excluded bnip bones; use same-side bust bones')
    return dict(roles=roles,source_regions=source_regions,target_regions=target_regions,
                body_map=bodymap,dynamic_map=dynamicmap,bone_map=bonemap,reference_anchors=anchors,
                finger_policy={'source_fingers':sf,'target_fingers':tf,'enabled':sorted(enabled),'disabled_map':disabled},region_modes=modes,sampling_replacements=replacements)

def scan(p):
    sr,tr=inputs(p)
    if len(p.bones) or len(p.targets):raise ValueError('Configuration already exists; export or clear it first to preserve manual decisions')
    mapping=dict(weights_body.VRC_TO_KK_BODY_GROUPS,Spine='cf_j_spine01',Chest='cf_j_spine03',Hips='cf_j_hips')
    support=wf.body_weight_support(p.body,p.target)
    mmd={}
    if p.source_profile!='VRC':
        table,asset,p.profile_digest=mmd_weight_profiles.load(p.source_profile,bpy.path.abspath(p.mmd_profile_path) if p.mmd_profile_path else '')
        records=[{'name':b.name,'name_j':getattr(getattr(sr.pose.bones[b.name],'mmd_bone',None),'name_j',''),'parent':b.parent.name if b.parent else None} for b in sr.data.bones]
        mmd=mmd_weight_profiles.recognize(records,table,asset)
    for n in sorted(support):
        x=p.targets.add();x.name=n;reg=target_region(n)
        if reg:x.region=reg;x.reviewed=True
        x.finger=finger_name(n)
    for n in sorted({n for row in wf.read_weights(p.source) for n in row}):
        x=p.bones.add();x.name=n;policy=vr.VRC_WEIGHT_POLICIES.get(n) if p.source_profile=='VRC' else None
        if p.source_profile!='VRC':
            info=mmd.get(n,{})
            x.recognition=json.dumps(info,ensure_ascii=False)
            if n in {'mmd_edge_scale','mmd_vertex_order'} and n not in sr.data.bones:x.role='IGNORE'
            elif info.get('role')=='BODY':
                x.role='BODY';x.region=info['budget_region'];semantic=info.get('reference_semantic')
                # Reuse the established semantic->KK map; do not duplicate MMD bone names in code.
                vrc=next((v for v,s in vr.VRC_MOTION_SEMANTICS.items() if s==semantic and v in mapping),None)
                motion=mapping.get(vrc,'');x.pose_target=motion
                candidates=[motion,motion.replace('cf_j_','cf_s_')]
                for a,b in [('hips','waist02'),('shoulder','shoulder02'),('arm00','arm01'),('thigh00','thigh01')]:candidates.append(motion.replace('cf_j_'+a,'cf_s_'+b))
                x.weight_target=next((v for v in candidates if v in support),'')
                if info.get('kind')=='FINGER':
                    x.finger=info['finger'].upper()+'_'+info['side'];x.semantic='NONE'
                elif info.get('kind')=='BODY' and semantic in {s[0] for s in SEMANTICS}:x.semantic=semantic
            continue
        if policy and policy.source_role=='BODY' and policy.budget_region:
            x.role='BODY';x.region=policy.budget_region;x.anchor=policy.reference_anchor if policy.reference_anchor!=n else ''
            motion=mapping.get(policy.reference_anchor,'');x.pose_target=motion
            candidates=[motion,motion.replace('cf_j_','cf_s_')]
            for a,b in [('shoulder','shoulder02'),('arm00','arm01'),('thigh00','thigh01'),('leg01','leg01')]:
                candidates.append(motion.replace('cf_j_'+a,'cf_s_'+b))
            x.weight_target=next((v for v in candidates if v in support),'')
            x.finger=finger_name(n)
            x.semantic=vr.VRC_MOTION_SEMANTICS.get(n,'NONE')
            # Fingers start disabled; user must choose a matching enabled mapping
            # or an explicit non-finger destination before running.
    count=generate_regions(p)
    analyze_regions(p)
    p.status=_fmt('Scan complete: generated {v0} candidate root regions; confirm dynamic roles and body-follow modes.', v0=count)

def generate_regions(p):
    sr=rig(p.source);roles={x.name:x.role for x in p.bones}
    weighted={n for row in wf.read_weights(p.source) for n in row}
    known={n for n,policy in vr.VRC_WEIGHT_POLICIES.items() if policy.source_role=='BODY'}
    roots=discover_roots({b.name:b.parent.name if b.parent else None for b in sr.data.bones},roles,weighted,known)
    existing={r.root for r in p.regions if r.root};added=0
    for root in sorted(roots):
        if root in existing:continue
        r=p.regions.add();r.name=root;r.root=root;r.discovered=True;r.mode='REVIEW';added+=1
    return added


def pattern_context(p):
    sr=rig(p.source);rows=wf.read_weights(p.source);roles={x.name:x.role for x in p.bones}
    candidates=set()
    # Provisional dynamic membership is only for statistics, not permission
    # to migrate or ignore unknown bone semantics.
    for r in p.regions:
        root=sr.data.bones.get(r.root)
        if root:candidates.update(b.name for b in [root]+list(root.children_recursive) if roles.get(b.name)=='REVIEW')
    effective={n:('DYNAMIC' if n in candidates and role=='REVIEW' else role) for n,role in roles.items()}
    edges=[list(e.vertices) for e in p.source.data.edges]
    topology=wf.topology(p.source)
    state=core.digest([p.source.name,topology,rows,effective,[(b.name,b.parent.name if b.parent else None) for b in sr.data.bones]])
    return dict(rig=sr,rows=rows,roles=effective,edges=edges,topology=topology,stamp=state)


def region_signature(r,state):return core.digest([state['stamp'],r.root,r.vertices,r.topology,r.mode])


def analyze_regions(p):
    state=pattern_context(p);counts={'UNIFORM':0,'EDGE_GRADIENT':0,'REVIEW':0};kept=0
    roles=state['roles']
    for r in p.regions:
        if r.reviewed_stamp and r.reviewed_stamp==region_signature(r,state):kept+=1;continue
        r.reviewed_stamp=''
        root=state['rig'].data.bones.get(r.root)
        chain={b.name for b in [root]+list(root.children_recursive)} if root else set()
        bones={n for n in chain if roles.get(n)=='DYNAMIC'}
        try:
            if r.vertices:
                if r.topology!=state['topology']:raise ValueError('Selection topology is stale')
                vertices=json.loads(r.vertices)
            else:vertices=[i for i,row in enumerate(state['rows']) if any(row.get(n,0)>0 for n in bones)]
            report=suggest_pattern(state['rows'],state['edges'],{n for n,v in roles.items() if v=='BODY'},
                {n for n,v in roles.items() if v=='DYNAMIC'},vertices,{n for n,v in roles.items() if v=='IGNORE'})
        except (ValueError,TypeError) as exc:report={'mode':'REVIEW','reason':str(exc)}
        previous=r.suggestion;r.suggestion=report['mode'];r.statistics=json.dumps(report,ensure_ascii=False)
        if r.mode=='REVIEW' or r.mode==previous:r.mode=r.suggestion
        counts[r.suggestion]+=1
    p.status=_fmt('Classification: uniform {v0}, gradient {v1}, unrecognized {v2}; preserve {v3} approved entries. Review each region.', v0=counts['UNIFORM'], v1=counts['EDGE_GRADIENT'], v2=counts['REVIEW'], v3=kept)


def confirm_region(p,region=None):
    if not p.regions:raise ValueError('Scan regions first')
    r=region if region is not None else p.regions[p.region_index]
    if r.mode=='REVIEW':raise ValueError('Unrecognized regions cannot run automatically; use per-vertex agent analysis or manual handling to determine a supported mode')
    state=pattern_context(p)
    if r.vertices and r.topology!=state['topology']:raise ValueError('Selection topology is stale; capture again')
    if not r.vertices and r.root not in state['rig'].data.bones:raise ValueError('Invalid region root bone')
    r.reviewed_stamp=region_signature(r,state)
    p.status=r.name+': mode approved; unknown bone roles still require review.'

def generate_motions(p):
    sr,tr=inputs(p)
    slots={}
    for x in p.bones:
        if x.role=='BODY' and x.semantic!='NONE':
            if x.semantic in slots:raise ValueError('Duplicate motion semantic: '+x.semantic)
            slots[x.semantic]=(x.name,x.pose_target)
    def frames(arm,index):
        def head(slot):
            name=slots.get(slot,(None,None))[index]
            if name and name in arm.data.bones:return arm.matrix_world@arm.data.bones[name].head_local
            return None
        pair=next(((head(a),head(b)) for a,b in [('UPPER_ARM_R','UPPER_ARM_L'),('UPPER_LEG_R','UPPER_LEG_L')] if head(a) is not None and head(b) is not None),None)
        vertical=next(((head(a),head(b)) for a,b in [('HIPS','NECK'),('SPINE','CHEST'),('CHEST','NECK'),('HIPS','CHEST')] if head(a) is not None and head(b) is not None and (head(a)-head(b)).length>1e-6),None)
        if pair is None or vertical is None:raise ValueError('Cannot infer anatomical axes; complete torso and bilateral limb semantics/mappings, or configure poses manually')
        up=(vertical[1]-vertical[0]).normalized();right=pair[1]-pair[0];right-=up*right.dot(up)
        if right.length<1e-6:raise ValueError('Limb and torso directions are degenerate; cannot generate motion axes')
        right.normalize();forward=up.cross(right).normalized()
        return {'right':right,'forward':forward,'up':up}
    source_frame=frames(sr,0);target_frame=frames(tr,1)
    existing={x.preset_id for x in p.motions if x.preset_id};pending=[];missing=[]
    for slot,label,axis,angle,endpoint in motion_templates(p.motion_preset):
        key=slot+':'+axis+':'+str(endpoint)
        if key in existing:continue
        if slot not in slots or slots[slot][0] not in sr.data.bones or slots[slot][1] not in tr.data.bones:
            missing.append(slot);continue
        src,dst=slots[slot];saxis=source_frame.get(axis);taxis=target_frame.get(axis)
        if axis=='limb':
            lower='LOWER_ARM_'+slot[-1]
            if lower not in slots:missing.append(lower);continue
            vectors=[]
            for arm,idx in [(sr,0),(tr,1)]:
                a=slots[slot][idx];b=slots[lower][idx]
                if a not in arm.data.bones or b not in arm.data.bones:raise ValueError('Missing bone for the wrist axis')
                vector=arm.matrix_world@(arm.data.bones[a].head_local)-arm.matrix_world@(arm.data.bones[b].head_local)
                if vector.length<1e-6:raise ValueError('Wrist and elbow positions coincide; cannot determine twist axis')
                vectors.append(vector.normalized())
            saxis,taxis=vectors
        parts=[]
        if slot=='CHEST' and dst=='cf_j_spine03' and 'cf_j_spine02' in tr.data.bones and tr.data.bones[dst].parent==tr.data.bones['cf_j_spine02']:
            parts=[('cf_j_spine02',.5),('cf_j_spine03',.5)]
        pending.append((key,label,src,dst,saxis,taxis,angle,endpoint,parts))
    for key,label,src,dst,saxis,taxis,angle,endpoint,parts in pending:
        x=p.motions.add();x.name=label;x.source=src;x.target=dst;x.axis=saxis;x.target_axis=taxis;x.separate_axis=True;x.angle=angle;x.endpoint=endpoint;x.preset_id=key
        if endpoint and angle>30:x.extra_angle=30
        for name,factor in parts:part=x.target_parts.add();part.name=name;part.factor=factor
    p.status=_fmt('Added {v0} preset poses; existing poses preserved.', v0=len(pending))+('Missing mapping; not generated: '+', '.join(sorted(set(missing))) if missing else 'Check pose directions and angles.')

def motion_control(x,degrees):
    parts=[(part.name,part.factor) for part in x.target_parts] or [(x.target,1.)]
    if any(not name or not 0<factor<=1 for name,factor in parts) or abs(sum(factor for name,factor in parts)-1)>1e-5 or len({n for n,f in parts})!=len(parts):
        raise ValueError(x.name+': sharing bones must be unique and positive shares must sum to 1')
    control={'source':[(x.source,1)],'target':parts,'axis':list(x.axis),'degrees':degrees}
    if x.separate_axis:control['target_axis']=list(x.target_axis)
    return control

def restore_preview():
    for name,state in _pose_preview.items():
        arm=bpy.data.objects.get(name)
        if arm is None:continue
        arm.data.pose_position=state['position']
        for bone,values in state['bones'].items():
            if bone not in arm.pose.bones:continue
            b=arm.pose.bones[bone]
            for key,value in values.items():setattr(b,key,value)
    _pose_preview.clear();bpy.context.view_layer.update()

def preview_motion(p):
    if not p.motions:raise ValueError('Generate or add poses first')
    sr,tr=inputs(p);x=p.motions[p.motion_index];ctrl=motion_control(x,x.angle)
    for arm,key in [(sr,'source'),(tr,'target')]:
        if any(n not in arm.pose.bones for n,f in ctrl[key]):raise ValueError('Mapped motion bone does not exist')
        if Vector(ctrl.get(key+'_axis',ctrl['axis'])).length<1e-8:raise ValueError('Invalid rotation axis')
    restore_preview()
    for arm in (sr,tr):
        _pose_preview[arm.name]={'position':arm.data.pose_position,'bones':{b.name:{key:list(getattr(b,key)) for key in ['location','rotation_euler','rotation_quaternion','rotation_axis_angle','scale']} for b in arm.pose.bones}}
    try:
        for arm in (sr,tr):
            arm.data.pose_position='POSE'
            for b in arm.pose.bones:b.matrix_basis=Matrix.Identity(4)
        bpy.context.view_layer.update()
        for arm,key in [(sr,'source'),(tr,'target')]:
            axis=Vector(ctrl.get(key+'_axis',ctrl['axis'])).normalized()
            for name,factor in ctrl[key]:
                local=(arm.matrix_world@arm.data.bones[name].matrix_local).to_3x3().inverted()@axis
                arm.pose.bones[name].matrix_basis @= Matrix.Rotation(math.radians(ctrl['degrees']*factor),4,local.normalized())
        bpy.context.view_layer.update()
    except Exception:restore_preview();raise
    p.status='Pose preview: check motion directions on both rigs, then restore the pose.'

def get_vertices(obj):
    if obj.mode=='EDIT':return [v.index for v in bmesh.from_edit_mesh(obj.data).verts if v.select]
    return [v.index for v in obj.data.vertices if v.select]

def capture_mask(p,context,local=False):
    obj=context.object
    if obj not in [p.source,p.target,p.initial,p.macro]:raise ValueError('Select vertices on the source garment or its corresponding copy')
    if obj.mode=='EDIT':obj.update_from_editmode()
    if wf.topology(obj)!=wf.topology(p.source):raise ValueError('Selected mesh topology does not match the original garment')
    ids=get_vertices(obj)
    if not ids:raise ValueError('No vertices selected')
    if local:p.local_vertices=json.dumps(ids);p.local_topology=wf.topology(p.source)
    else:
        if not p.regions:raise ValueError('Add an influence region first')
        r=p.regions[p.region_index];r.vertices=json.dumps(ids);r.topology=wf.topology(p.source)
    p.status=_fmt('Captured {v0} vertices; exit Edit Mode before solving.', v0=len(ids))

def preview_region(p,context):
    if not p.regions:raise ValueError('Add an influence region first')
    r=p.regions[p.region_index];src=p.source;sr=rig(src)
    if r.vertices:
        if r.topology!=wf.topology(src):raise ValueError('Region selection is stale')
        ids=set(json.loads(r.vertices))
    else:
        root=sr.data.bones.get(r.root)
        if not root:raise ValueError('Choose a source dynamic root or capture a vertex selection')
        roles={x.name:x.role for x in p.bones}
        names={b.name for b in [root]+list(root.children_recursive) if roles.get(b.name) in {'DYNAMIC','REVIEW'}}
        ids={i for i,row in enumerate(wf.read_weights(src)) if any(row.get(n,0)>0 for n in names)}
    if context.object and context.object.mode!='OBJECT':bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.select_all(action='DESELECT');src.hide_set(False);src.select_set(True);context.view_layer.objects.active=src
    for v in src.data.vertices:v.select=v.index in ids
    bpy.ops.object.mode_set(mode='EDIT');p.status=_fmt('Highlight {v0} source vertices; adjust the selection and capture again if needed.', v0=len(ids))

def save(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')

def folder(p):
    if not p.output:raise ValueError('Set the run output directory')
    out=Path(bpy.path.abspath(p.output));out.mkdir(parents=True,exist_ok=True)
    return out

def duplicate(obj,suffix):
    copy=obj.copy();copy.data=obj.data.copy();copy.name=obj.name+suffix
    for c in obj.users_collection:c.objects.link(copy)
    copy.hide_set(True);bpy.context.view_layer.update();return copy

def native_rest_check(p):
    # Do not sample posed body weights against static fitted coordinates.
    for r in {rig(p.body),rig(p.target)}:
        if r.data.pose_position=='POSE' and any(np.max(abs(np.array(b.matrix_basis)-np.eye(4)))>1e-6 for b in r.pose.bones):
            raise ValueError('Native transfer requires the target garment and body in a shared rest pose; restore T pose first')

def prepare(p):
    c=config(p);snapshot=wf.capture_snapshot(p.source,c['roles'])
    if p.reference_mode=='FITTED':
        src=np.array([p.source.matrix_world@v.co for v in p.source.data.vertices]);dst=np.array([p.target.matrix_world@v.co for v in p.target.data.vertices])
        if np.max(np.linalg.norm(src-dst,axis=1))>1e-5:raise ValueError('Fitted-reference mode requires the matching fitted source mesh with original untransferred weights; the old unfitted mesh is not valid')
    allowed=set(c['target_regions'])-set(c['sampling_replacements']);confidence={i:p.confidence for i in range(len(snapshot['rows']))}
    args=dict(source_regions=c['source_regions'],target_regions=c['target_regions'],finger_policy=c['finger_policy'],region_modes=c['region_modes'])
    if p.initial_mode=='NATIVE':
        native_rest_check(p)
        plan=wf.prepare_from_body(p.target,snapshot,p.body,c['body_map'],c['dynamic_map'],allowed,confidence,sampling_replacements=c['sampling_replacements'],**args)
    else:
        sample_rows=[{n:w for n,w in row.items() if n in c['target_regions']} for row in wf.read_weights(p.target)] if p.initial_mode=='EXISTING' else []
        if c['sampling_replacements']:sample_rows=core.redirect_body_samples(sample_rows,c['sampling_replacements'],c['target_regions'],allowed)
        samples=dict(enumerate(sample_rows))
        if p.initial_mode=='MAP':confidence={}
        plan=wf.prepare_plan(p.target,snapshot,c['body_map'],c['dynamic_map'],allowed,sampled_weights=samples,sampling_confidence=confidence,body_source=p.body,**args)
    root=folder(p)/('run-'+uuid.uuid4().hex[:12]);root.mkdir()
    plan['excluded_body_groups']=sorted(c['sampling_replacements'])
    plan['managed_groups']=sorted(set(plan['managed_groups'])|set(c['sampling_replacements']))
    bpy.ops.wm.save_as_mainfile(filepath=str(root/'before.blend'),copy=True)
    from . import mmd_preprocess as prep
    collection=prep.create_collection('Weight source reference')
    reference,reference_rig=prep.clone(p.source,collection,'WeightReference')
    reference.hide_set(True);reference.hide_render=True;reference_rig.hide_set(True);reference_rig.hide_render=True
    p.reference=reference;p.reference_stamp=wf.stamp(reference)
    p.reference_structure=core.digest(prep.bones(reference_rig))
    save(root/'source-snapshot.json',snapshot)
    save(root/'reference.json',{'mode':p.reference_mode,'object':reference.name,'stamp':p.reference_stamp,'input_stamp':wf.stamp(p.source)})
    plan['context_sources']={p.source.name:wf.stamp(p.source)}
    plan['plan_id']=core.digest({k:v for k,v in plan.items() if k!='plan_id'})
    save(root/'settings.json',dump_settings(p));save(root/'initial-plan.json',plan)
    p.run=str(root);p.fingerprint=fingerprint(p);p.initial=None;p.macro=None;p.final=None
    p.status=_fmt('Six-class preview complete: {v0} vertices; fallback {v1} vertices. Ready to write an initialization copy.', v0=len(plan['writes']), v1=len(plan.get('regional_fallback', {})))

def fresh(p):
    if not p.run or fingerprint(p)!=p.fingerprint:raise ValueError('Configuration changed or was not previewed; prepare the six-class plan again')
    return Path(p.run)

def write_initial(p):
    root=fresh(p)
    if p.initial:raise ValueError('This run already has an initialization copy')
    old=json.loads((root/'initial-plan.json').read_text())
    if wf.stamp(p.target)!=old['expected_stamp']:raise ValueError('Target state changed; preview again')
    copy=duplicate(p.target,'.SixBudget')
    try:
        plan=dict(old,target=copy.name);plan['plan_id']=core.digest({k:v for k,v in plan.items() if k!='plan_id'})
        report=wf.apply_plan(copy,plan)
    except Exception:
        bpy.data.objects.remove(copy,do_unlink=True);raise
    save(root/'initial-writeback.json',report);p.initial=copy;copy.hide_set(False);copy.hide_render=False;p.target.hide_set(True);p.target.hide_render=True
    p.status='Six-class initialization written to a copy; source weights and the fitted original are preserved.'

def poses(p,local):
    chosen=[x for x in p.motions if x.endpoint==local]
    if not chosen:raise ValueError('Configure source/target motion bones and world axes for this stage')
    result=[]
    for i,x in enumerate(chosen):
        if not x.source or not x.target or sum(a*a for a in x.axis)<1e-10:raise ValueError('Invalid motion bone or rotation axis')
        angles=sorted({x.angle,p.small_angle}) if local else [x.angle]
        if x.extra_angle>0:angles=sorted(set(angles+[x.extra_angle]))
        for angle in angles:
            for sign in [-1,1]:
                result.append({'name':f'{x.name}_{i}_{angle*sign:g}','kind':'common','controls':[motion_control(x,angle*sign)]})
        for sign in [-1,1]:
            result.append({'name':f'{x.name}_{i}_holdout_{sign}','kind':'holdout','controls':[motion_control(x,x.angle*.57*sign)]})
    if not local:
        rng=np.random.default_rng(31415)
        for i in range(3):
            controls=[motion_control(x,float(rng.uniform(-.35,.35)*x.angle)) for x in chosen]
            result.append({'name':f'random_{i}','kind':'random','seed':31415,'controls':controls})
    return result

def export_stage(p,stage):
    root=fresh(p);c=config(p);local=stage=='terminal';obj=p.macro if local else p.initial
    if not obj:raise ValueError('Write the main result first' if local else 'Write the six-class initialization copy first')
    args={k:c[k] for k in ['roles','source_regions','target_regions','bone_map','reference_anchors','finger_policy']}
    args['poses']=poses(p,local);args['reviewed_patterns']='uniform_and_edge_in_separate_regions'
    reference=p.reference
    if reference is None or wf.stamp(reference)!=p.reference_stamp:raise ValueError('Frozen source reference is missing or changed; prepare the run again')
    from .mmd_preprocess import bones as reference_bones
    if core.digest(reference_bones(rig(reference)))!=p.reference_structure:raise ValueError('Frozen source rig structure or constraints changed; prepare again')
    args['excluded_body_groups']=sorted(c['sampling_replacements'])
    if p.source_sampling=='EVALUATED':args['source_contract']=optimization.source_pose_contract(reference)
    if local:
        if not p.local_vertices or p.local_topology!=wf.topology(p.source):raise ValueError('Capture a valid terminal vertex selection')
        core_ids=set(json.loads(p.local_vertices));selected=set(core_ids);limits={str(i):1. for i in core_ids}
        edges=[tuple(e.vertices) for e in obj.data.edges];front=set(core_ids)
        for ring in range(p.rings):
            nxt={b for a,b in edges if a in front}|{a for a,b in edges if b in front};nxt-=selected
            for i in nxt:limits[str(i)]=.25*(.24**ring)
            selected|=nxt;front=nxt
        allowed={}
        for x in p.targets:
            if x.local and x.finger=='NONE':allowed.setdefault(x.region,[]).append(x.name)
        if not allowed:raise ValueError('Enable terminal adjustment for body bones in the target list')
        args.update(selected=sorted(selected),local_refinement={'stage':'T_pose_terminal_response','region_bones':allowed,'delta_limits':limits,
            'pose_bones':{'source':sorted({x.source for x in p.motions if x.endpoint}),'target':sorted({n for x in p.motions if x.endpoint for n,f in motion_control(x,0)['target']})},
            **TERMINAL})
    a,m=optimization.export_context(reference,obj,p.body,**args)
    m['reference_mode']=p.reference_mode
    m['reviewed_region_modes']=c['region_modes'];m['workflow_settings_digest']=fingerprint(p,True)
    m['context_id']=core.digest({k:v for k,v in m.items() if k!='context_id'})
    path=root/(stage+'-'+uuid.uuid4().hex[:8]);path.mkdir()
    np.savez_compressed(path/'context.npz',**a);save(path/'context.json',m);save(path/'export-config.json',args)
    save(root/(stage+'-current.json'),{'directory':str(path),'fingerprint':p.fingerprint})
    return path

def stage_data(p,stage):
    root=fresh(p);path=Path(json.loads((root/(stage+'-current.json')).read_text())['directory'])
    with np.load(path/'context.npz') as z:a={k:z[k] for k in z.files}
    with np.load(path/'candidate.npz') as z:c={k:z[k] for k in z.files}
    m=json.loads((path/'context.json').read_text());report=json.loads((path/'report.json').read_text())
    if m.get('workflow_settings_digest')!=fingerprint(p,True):raise ValueError('Stage settings changed; solve again before writing a candidate')
    return path,a,m,c,report

def validate_stage(p,stage):
    path,a,m,c,report=stage_data(p,stage)
    v=optimizer_validation.validate(a,m,c,report);save(path/'validation.json',v)
    p.status=('Validation passed; ready to save a copy.' if v['accepted'] else 'Weight checks passed; save and inspect collision vertices.' if v['non_contact_ok'] and p.collision_policy=='REVIEW' else 'Non-collision checks or strict policy failed; writing is blocked.')+_fmt(' held-out pose RMS {v0:.6g} → {v1:.6g}', v0=v['holdout_body_rms_before'], v1=v['holdout_body_rms_after'])

def write_stage(p,stage):
    path,a,m,c,report=stage_data(p,stage);v=json.loads((path/'validation.json').read_text())
    review=p.collision_policy=='REVIEW' and v.get('non_contact_ok') is True
    if not v['accepted'] and not review:raise ValueError('Non-collision checks or strict collision validation failed')
    original=p.macro if stage=='terminal' else p.initial
    copy=duplicate(original,'.Terminal' if stage=='terminal' else '.Optimized')
    try:
        plan=optimization.prepare_optimized_plan(original,a,m,c['weights'],v,destination=copy,collision_review=review)
        written=wf.apply_plan(copy,plan)
    except Exception:
        bpy.data.objects.remove(copy,do_unlink=True);raise
    save(path/'writeback.json',written);original.hide_set(True);copy.hide_set(False)
    copy['kkvrc_previous_hide_render']=original.hide_render;original.hide_render=True;copy.hide_render=False
    if stage=='terminal':p.final=copy
    else:p.macro=copy
    ids=set(v.get('collision_review_vertices',[]))
    for vert in copy.data.vertices:vert.select=vert.index in ids
    for obj in bpy.context.selected_objects:obj.select_set(False)
    copy.select_set(True);bpy.context.view_layer.objects.active=copy
    copy['kkvrc_collision_review']='PENDING' if not v['contact_ok'] else 'CLEAR'
    copy['kkvrc_previous_weight_result']=original.name;copy['kkvrc_validation_report']=str(path/'validation.json')
    p.status='Saved '+copy.name+('; collision vertices selected for review; reverting remains available.' if not v['contact_ok'] else '; checks passed.')
    bpy.ops.wm.save_as_mainfile(filepath=str(path/'result.blend'),copy=True)

def review_result(p, rollback=False):
    obj=p.final or p.macro
    if obj is None:raise ValueError('No optimization result copy')
    if bpy.context.object and bpy.context.object.mode!='OBJECT':bpy.ops.object.mode_set(mode='OBJECT')
    if rollback:
        previous=bpy.data.objects.get(obj.get('kkvrc_previous_weight_result',''))
        if previous is None:raise ValueError('Previous version does not exist')
        obj.hide_set(True);obj.hide_render=True;previous.hide_set(False);previous.hide_render=obj.get('kkvrc_previous_hide_render',False)
        if p.final==obj:p.final=None
        else:p.macro=None
        obj=previous;p.status='Showing the previous version; the optimization copy remains hidden.'
    else:
        path=Path(obj.get('kkvrc_validation_report',''))
        data=json.loads(path.read_text(encoding='utf8'));ids=set(data.get('collision_review_vertices',[]))
        for v in obj.data.vertices:v.select=v.index in ids
        p.status=_fmt('Selected {v0} collision-related vertices; the report distinguishes existing, new, and worsened collisions.', v0=len(ids))
    for selected in bpy.context.selected_objects:selected.select_set(False)
    obj.hide_set(False);obj.select_set(True);bpy.context.view_layer.objects.active=obj

def python_command(p):
    value=bpy.path.abspath(p.python) if ('/' in p.python or '\\' in p.python) else shutil.which(p.python)
    if not value or not Path(value).is_file():raise ValueError('External Python not found; configure it in runtime settings')
    env=os.environ.copy()
    if p.dependencies:env['PYTHONPATH']=bpy.path.abspath(p.dependencies)+os.pathsep+env.get('PYTHONPATH','')
    return value,env

class KKVRC_OT_workflow(bpy.types.Operator):
    bl_idname='kkvrc.weight_workflow'
    bl_label='Garment weight workflow'
    action:bpy.props.StringProperty()
    stage:bpy.props.StringProperty(default='macro')
    def execute(self,context):
        p=context.scene.kkvrc_weight_workflow
        try:
            if context.scene.as_pointer() in _jobs:raise ValueError('Optimization is running; wait for completion or cancel')
            if self.action=='SCAN':scan(p)
            elif self.action=='CLEAR':
                p.bones.clear();p.targets.clear();p.regions.clear();p.motions.clear();p.fingerprint='';p.status='Configuration cleared; garment results preserved.'
            elif self.action=='GENERATE_REGIONS':generate_regions(p);analyze_regions(p)
            elif self.action=='ANALYZE_REGIONS':analyze_regions(p)
            elif self.action=='CONFIRM_REGION':confirm_region(p)
            elif self.action=='GENERATE_MOTIONS':generate_motions(p)
            elif self.action=='PREVIEW_MOTION':preview_motion(p)
            elif self.action=='RESTORE_POSE':restore_preview();p.status='Restored the pose from before preview.'
            elif self.action=='ADD_PART':p.motions[p.motion_index].target_parts.add()
            elif self.action=='REMOVE_PART':
                parts=p.motions[p.motion_index].target_parts
                if parts:parts.remove(len(parts)-1)
            elif self.action=='ADD_REGION':p.regions.add();p.region_index=len(p.regions)-1
            elif self.action=='REMOVE_REGION':
                if p.regions:p.regions.remove(p.region_index);p.region_index=max(0,p.region_index-1)
            elif self.action=='ADD_MOTION':p.motions.add();p.motion_index=len(p.motions)-1
            elif self.action=='UNCONFIRM_REGION':
                if not p.regions:raise ValueError('Select a region first')
                p.regions[p.region_index].reviewed_stamp=''
                p.status='Region approval revoked; transfer requires renewed approval.'
            elif self.action=='MARK_CHAIN':
                if not p.regions:raise ValueError('Add a region and choose its chain root first')
                r=p.regions[p.region_index];root=rig(p.source).data.bones.get(r.root)
                if not root:raise ValueError('Select a valid source chain root')
                names={b.name for b in [root]+list(root.children_recursive)}
                conflicts=[n for n in names if (n in vr.VRC_WEIGHT_POLICIES and vr.VRC_WEIGHT_POLICIES[n].source_role=='BODY') or any(x.name==n and x.role=='BODY' for x in p.bones)]
                if conflicts:raise ValueError('Subtree contains recognized body bones and cannot be marked entirely dynamic: '+str(conflicts))
                for x in p.bones:
                    if x.name in names:x.role='DYNAMIC'
                p.status='Weighted bones in this chain marked as retained dynamic bones; region mode still needs approval.'
            elif self.action=='REMOVE_MOTION':
                if p.motions:p.motions.remove(p.motion_index);p.motion_index=max(0,p.motion_index-1)
            elif self.action=='CAPTURE_REGION':capture_mask(p,context)
            elif self.action=='CAPTURE_LOCAL':capture_mask(p,context,True)
            elif self.action=='CHAIN_MASK':p.regions[p.region_index].vertices='';p.regions[p.region_index].topology=''
            elif self.action=='PREVIEW_REGION':preview_region(p,context)
            elif self.action=='CHECK':
                c=config(p);p.status=_fmt('Configuration passed: {v0} region vertices; all effective source deformation contributions are preserved.', v0=len(c['region_modes']))
            elif self.action=='PREPARE':prepare(p)
            elif self.action=='WRITE_INITIAL':write_initial(p)
            elif self.action=='VALIDATE':validate_stage(p,self.stage)
            elif self.action=='WRITE':write_stage(p,self.stage)
            elif self.action=='REVIEW_CONTACTS':review_result(p)
            elif self.action=='ROLLBACK_RESULT':review_result(p,True)
            elif self.action=='EXPORT_PRESET':
                if not p.preset:raise ValueError('Specify a configuration file path')
                save(Path(bpy.path.abspath(p.preset)),dump_settings(p));p.status='Configuration exported.'
            elif self.action=='IMPORT_PRESET':
                data=json.loads(Path(bpy.path.abspath(p.preset)).read_text(encoding='utf-8-sig'))
                if data.get('schema')!=1:raise ValueError('Unsupported workflow configuration format')
                for key in ['bones','targets','regions','motions']:
                    coll=getattr(p,key);coll.clear()
                    for values in data[key]:
                        x=coll.add()
                        for k,v in values.items():
                            if k=='target_parts':
                                for part in v:
                                    term=x.target_parts.add();term.name=part['name'];term.factor=part['factor']
                            else:setattr(x,k,v)
                for key in ['source','target','body']:setattr(p,key,bpy.data.objects.get(data[key]))
                for key in ['confidence','initial_mode','local_vertices','local_topology','rings','small_angle','contacts','source_profile','mmd_profile_path','profile_digest','source_sampling','reference_mode','collision_policy','exclude_bnip']:
                    if key in data:setattr(p,key,data[key])
                p.fingerprint='';p.status='Configuration imported; check object assignments and preview again.'
            elif self.action=='DEPENDENCIES':
                exe,env=python_command(p)
                test=subprocess.run([exe,'-c','import numpy,scipy,osqp; print("OK")'],env=env,capture_output=True,text=True,timeout=20,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                if test.returncode:raise ValueError('Missing dependencies; NumPy/SciPy/OSQP required: '+test.stderr[-400:])
                p.status='External Python and NumPy/SciPy/OSQP are available.'
            return {'FINISHED'}
        except Exception as e:
            p.status=str(e);self.report({'ERROR'},str(e));return {'CANCELLED'}

class KKVRC_OT_workflow_solve(bpy.types.Operator):
    bl_idname='kkvrc.weight_workflow_solve'
    bl_label='Solve garment weights'
    stage:bpy.props.StringProperty(default='macro')
    automatic:bpy.props.BoolProperty(default=False,options={'HIDDEN'})
    include_terminal:bpy.props.BoolProperty(default=False,options={'HIDDEN'})
    def execute(self,context):
        p=context.scene.kkvrc_weight_workflow;self.scene=context.scene;self.key=self.scene.as_pointer()
        try:
            if self.key in _jobs:raise ValueError('An optimization task is already running')
            exe,env=python_command(p);path=export_stage(p,self.stage)
            command=[exe,str(Path(__file__).with_name('optimizer_cli.py')),str(path)]
            if p.contacts:command.append('--contacts')
            self.log=open(path/'solver.log','w',encoding='utf-8')
            try:self.process=subprocess.Popen(command,env=env,stdout=self.log,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            except Exception:self.log.close();raise
            self.path=path;self.timer=context.window_manager.event_timer_add(.5,window=context.window)
            _jobs[self.key]=self;context.window_manager.modal_handler_add(self)
            p.status='Optimization running; Esc cancels. Run independent validation afterward.';return {'RUNNING_MODAL'}
        except Exception as e:p.status=str(e);self.report({'ERROR'},str(e));return {'CANCELLED'}
    def finish(self,context,cancel=False):
        if cancel and self.process.poll() is None:self.process.terminate()
        self.log.close();context.window_manager.event_timer_remove(self.timer);_jobs.pop(self.key,None)
    def modal(self,context,event):
        p=self.scene.kkvrc_weight_workflow
        if event.type=='ESC':self.finish(context,True);p.status='Solve canceled; no weights written.';return {'CANCELLED'}
        if event.type=='TIMER' and self.process.poll() is not None:
            code=self.process.returncode;self.finish(context)
            if not code:
                # CLI keeps contact runs separately; expose a common verified input.
                if (self.path/'contact_report.json').exists():
                    shutil.copyfile(self.path/'contact_report.json',self.path/'report.json');shutil.copyfile(self.path/'contact_candidate.npz',self.path/'candidate.npz')
                p.status='Solve complete; not yet written. Run independent validation.'
                if self.automatic:
                    try:
                        if context.scene!=self.scene:raise ValueError('Scene changed; automatic writing stopped. Return to the original scene for manual validation')
                        from . import workflow_beginner as beginner
                        beginner.finish_stage(p,self.stage)
                        if self.stage=='macro' and self.include_terminal and p.macro.get('kkvrc_collision_review')!='PENDING':
                            result=bpy.ops.kkvrc.weight_workflow_solve('INVOKE_DEFAULT',stage='terminal',automatic=True,include_terminal=False)
                            if result=={'CANCELLED'}:raise ValueError(p.status)
                        # write_stage already reports saved result / pending collision review.
                    except Exception as exc:
                        p.status='Automatic workflow stopped: '+str(exc);self.report({'ERROR'},p.status)
                        return {'CANCELLED'}
            else:p.status='Solve failed; nothing written. See '+str(self.path/'solver.log')
            return {'FINISHED'}
        return {'PASS_THROUGH'}

def stop_jobs():
    restore_preview()
    for job in list(_jobs.values()):
        if job.process.poll() is None:job.process.terminate()
        job.log.close()
        try:bpy.context.window_manager.event_timer_remove(job.timer)
        except Exception:pass
    _jobs.clear()

def button(layout,text,action,stage='macro'):
    op=layout.operator('kkvrc.weight_workflow',text=text);op.action=action;op.stage=stage

def draw(layout,context):
    p=context.scene.kkvrc_weight_workflow
    box=layout.box();box.label(text='1 · Inputs and scan')
    for key in ['source','target','body']:box.prop(p,key)
    box.prop(p,'source_profile')
    if p.source_profile!='VRC':box.prop(p,'mmd_profile_path')
    box.prop(p,'source_sampling');box.prop(p,'reference_mode')
    if p.reference_mode=='FITTED':box.label(text='Source must retain complete original weights and match the fitted mesh; preparation freezes a copy.',icon='INFO')
    button(box,'Scan bones and dynamic root regions','SCAN')
    box=layout.box();box.label(text='2 · Review body and dynamic regions')
    box.prop(p,'show_review_bones')
    if p.show_review_bones:
        box.label(text='Source bones: assign roles and body regions')
        box.template_list('KKVRC_UL_wf','source',p,'bones',p,'bone_index',rows=5)
        if p.bones:
            x=p.bones[min(p.bone_index,len(p.bones)-1)]
            box.prop(p,'show_source_details')
            if p.show_source_details:
                detail=box.box();detail.label(text=x.name);detail.prop(x,'role')
                if x.recognition:detail.label(text='Recognition: maintained MMD profile; unknown and dynamic candidates still require review',icon='INFO')
                if x.role=='BODY':
                    detail.prop(x,'region');detail.prop(x,'finger');detail.prop(x,'semantic')
                    if x.finger!='NONE':detail.prop(x,'enabled')
                    if p.body:
                        detail.prop_search(x,'weight_target',p.body,'vertex_groups')
                        try:detail.prop_search(x,'pose_target',rig(p.body).data,'bones')
                        except ValueError:pass
                    if p.source:
                        try:detail.prop_search(x,'anchor',rig(p.source).data,'bones')
                        except ValueError:pass
        button(box,'Refresh dynamic regions after editing roles','GENERATE_REGIONS')
        box.label(text='Target bones: only bones with actual body weights')
        box.template_list('KKVRC_UL_wf','target',p,'targets',p,'target_index',rows=5)
        if p.targets:
            x=p.targets[min(p.target_index,len(p.targets)-1)]
            box.prop(p,'show_target_details')
            if p.show_target_details:
                detail=box.box();detail.label(text=x.name)
                for key in ['region','reviewed','finger','local']:detail.prop(x,key)
    row=box.row(align=True)
    button(row,'Add missing root regions','GENERATE_REGIONS')
    button(row,'Reclassify regions','ANALYZE_REGIONS')
    box.template_list('KKVRC_UL_wf','region',p,'regions',p,'region_index',rows=4)
    if p.regions:
        x=p.regions[min(p.region_index,len(p.regions)-1)]
        box.label(text=x.root or x.name,icon='BONE_DATA')
        row=box.row(align=True)
        button(row,'Mark this root chain as dynamic','MARK_CHAIN')
        button(row,'Show mesh region','PREVIEW_REGION')
        box.prop(x,'mode')
        box.label(text='Suggested mode: '+{'UNIFORM':'Uniform follow','EDGE_GRADIENT':'Boundary gradient','REVIEW':'Needs review'}.get(x.suggestion,'Needs review'))
        if x.mode=='REVIEW':
            box.label(text='Analyze per vertex or handle manually before approval',icon='INFO')
        confirmed=bool(x.reviewed_stamp)
        row=box.row();row.enabled=x.mode!='REVIEW' or confirmed
        row.prop(x,'reviewed',text='Region mode reviewed')
        box.label(text=_fmt('Scope: explicit selection, {v0} vertices', v0=len(json.loads(x.vertices))) if x.vertices else 'Scope: vertices with nonzero root-chain weights')
        box.prop(x,'show_statistics',text='Statistics and advanced region settings')
        if x.show_statistics:
            advanced=box.box()
            advanced.prop(x,'name')
            if p.source:
                try:advanced.prop_search(x,'root',rig(p.source).data,'bones')
                except ValueError:pass
            row=advanced.row(align=True)
            button(row,'Capture current selection','CAPTURE_REGION')
            button(row,'Restore root-chain scope','CHAIN_MASK')
            row=advanced.row(align=True);button(row,'Add region','ADD_REGION');button(row,'Remove region','REMOVE_REGION')
            if x.statistics:
                stats=json.loads(x.statistics);numbers=stats.get('statistics',{})
                advanced.label(text=stats.get('reason','')[:65])
                if numbers:
                    advanced.label(text=_fmt('Mean {v0:.4f}  Variance {v1:.6f}', v0=numbers['mean'], v1=numbers['variance']))
                    advanced.label(text=_fmt('Range {v0:.4f}  Relative range {v1:.3f}', v0=numbers['range'], v1=numbers['relative_range']))
                    advanced.label(text=f"P05 {numbers['p05']:.4f}  P95 {numbers['p95']:.4f}")
                for part in stats.get('components',[]):
                    if part.get('reason'):advanced.label(text=part['reason'][:65])
    else:
        button(box,'Add region manually','ADD_REGION')
    button(box,'Check regions and mappings','CHECK')
    box=layout.box();box.label(text='3 · Six-class transfer and main optimization')
    box.prop(p,'output')
    box.prop(p,'collision_policy');box.prop(p,'exclude_bnip')
    row=box.row(align=True);button(row,'Select collision vertices','REVIEW_CONTACTS');button(row,'Revert to previous version','ROLLBACK_RESULT')
    box.prop(p,'advanced_solver')
    if p.advanced_solver:
        box.prop(p,'initial_mode');box.prop(p,'confidence')
    row=box.row(align=True);button(row,'Preview six-class initialization','PREPARE');button(row,'Write initialization copy','WRITE_INITIAL')
    box.label(text=_fmt('Configured: {v0} poses', v0=len(p.motions)))
    button(box,'Generate preset poses (add missing entries)','GENERATE_MOTIONS')
    box.prop(p,'edit_pose_preset')
    if p.edit_pose_preset:
        box.prop(p,'motion_preset')
        box.label(text='Pose comparison: select a preset, then review angles')
        box.template_list('KKVRC_UL_wf','motion',p,'motions',p,'motion_index',rows=3)
        row=box.row(align=True);button(row,'Add pose','ADD_MOTION');button(row,'Remove pose','REMOVE_MOTION')
        if p.motions:
            x=p.motions[min(p.motion_index,len(p.motions)-1)];box.prop(x,'name')
            for obj,key in [(p.source,'source'),(p.body,'target')]:
                if obj:
                    try:box.prop_search(x,key,rig(obj).data,'bones')
                    except ValueError:pass
            box.prop(x,'angle');box.prop(x,'endpoint')
            row=box.row(align=True);button(row,'Preview pose','PREVIEW_MOTION');button(row,'Restore pose','RESTORE_POSE')
            box.prop(p,'motion_advanced')
            if p.motion_advanced:
                box.prop(x,'extra_angle')
                box.prop(x,'axis');box.prop(x,'separate_axis')
                if x.separate_axis:box.prop(x,'target_axis')
                box.label(text='Rotation sharing (leave empty to use only the target bone above)')
                for part in x.target_parts:
                    row=box.row(align=True)
                    if p.body:row.prop_search(part,'name',rig(p.body).data,'bones',text='')
                    row.prop(part,'factor')
                row=box.row(align=True);button(row,'Add sharing bone','ADD_PART');button(row,'Remove last entry','REMOVE_PART')
    box.prop(p,'contacts')
    op=box.operator('kkvrc.weight_workflow_solve',text='Solve main weights');op.stage='macro'
    row=box.row(align=True);button(row,'Independent validation','VALIDATE');button(row,'Write main copy','WRITE')
    box=layout.box();box.label(text='4 · Local terminal refinement in T pose')
    box.label(text='Use only terminal poses and the selected target candidate bones')
    button(box,'Capture terminal vertex selection','CAPTURE_LOCAL')
    box.label(text=_fmt('Core vertices: {v0}', v0=len(json.loads(p.local_vertices))) if p.local_vertices else 'No terminal region specified')
    if p.advanced_solver:
        box.prop(p,'rings');box.prop(p,'small_angle')
    op=box.operator('kkvrc.weight_workflow_solve',text='Solve terminal weights');op.stage='terminal'
    row=box.row(align=True);button(row,'Independent validation','VALIDATE','terminal');button(row,'Write terminal copy','WRITE','terminal')
    for key in ['initial','macro','final']:
        if getattr(p,key):box.prop(p,key)
    box=layout.box();box.prop(p,'advanced')
    if p.advanced:
        box.prop(p,'python');box.prop(p,'dependencies');button(box,'Check solver dependencies','DEPENDENCIES')
        box.prop(p,'preset');row=box.row(align=True);button(row,'Import configuration','IMPORT_PRESET');button(row,'Export configuration','EXPORT_PRESET')
        button(box,'Clear configuration (keep results)','CLEAR')
    layout.label(text=p.status[:110])

CLASSES=(KKVRC_WFBone,KKVRC_WFTarget,KKVRC_WFRegion,KKVRC_WFMotionPart,KKVRC_WFMotion,KKVRC_WorkflowProperties,KKVRC_UL_wf,KKVRC_OT_workflow,KKVRC_OT_workflow_solve)
