"""Persistent compatibility policy and optional Blender dynamic probe sampling."""
import math
import json
import bpy
import numpy as np
from bpy.app.handlers import persistent
from mathutils import Matrix
from .influence_policy import policy


def properties():
    return {
        'influence_version': bpy.props.IntProperty(default=0, options={'HIDDEN'}),
        'influence_report': bpy.props.StringProperty(default='',options={'HIDDEN'}),
        'total_influences': bpy.props.EnumProperty(name='Total influences per vertex',
            items=[('FOUR','Four (body + dynamics + fingers)','Preserve budgets within four total bone slots'),
                   ('UNLIMITED','Unlimited (legacy)','Keep the original dense workflow')],default='FOUR'),
        'compress_dynamic': bpy.props.BoolProperty(name='Allow approximate dynamic compression',default=False,
            description='Only resolve slot conflicts; preserve the dynamic total and require separate chain-response validation'),
        'dynamic_error_limit': bpy.props.FloatProperty(name='Dynamic response tolerance / mesh span',default=.002,min=.000001,max=.1),
    }


def settings(p):
    # Also mark configurations created in scenes added after add-on registration.
    if not p.influence_version:p.influence_version=1
    return policy(dict(max_influences=4 if p.total_influences=='FOUR' else 0,
                       compress_dynamic=p.compress_dynamic,dynamic_error_limit=p.dynamic_error_limit))


def load_settings(p, value=None):
    v=policy(value)
    p.total_influences='FOUR' if v['max_influences'] else 'UNLIMITED'
    p.compress_dynamic=v['compress_dynamic'];p.dynamic_error_limit=v['dynamic_error_limit'];p.influence_version=1


@persistent
def migrate_existing(_=None):
    # RNA defaults alone cannot distinguish a new scene from a saved legacy
    # configuration. Inspect saved fields before introducing the version marker.
    for scene in bpy.data.scenes:
        for key in ('kkvrc_weight_workflow','kkvrc_shoes'):
            if not hasattr(scene,key):continue
            p=getattr(scene,key)
            if p.influence_version:continue
            saved=scene.get(key)
            legacy=bool(saved and any(k in saved for k in ('source','target','body','bones','source_bones','run','scan_stamp')))
            if legacy and not p.is_property_set('total_influences'):
                load_settings(p)
            else:p.influence_version=1


def draw(layout,p):
    # Blender forbids ID-property writes during panel drawing. Initialization
    # belongs in register/load migration or an explicit operator (settings).
    box=layout.box();box.label(text='Runtime influence compatibility')
    box.prop(p,'total_influences')
    if p.total_influences=='FOUR':
        box.prop(p,'compress_dynamic')
        if p.compress_dynamic:box.prop(p,'dynamic_error_limit')
        box.label(text='Unresolved vertices remain unchanged and require runtime review.')
    row=box.row(align=True)
    for label,select in [('Scan influence counts',False),('Select over-limit vertices',True)]:
        op=row.operator('kkvrc.scan_influence_limits',text=label)
        op.shoes=hasattr(p,'source_bones');op.select_vertices=select
    if p.influence_report:
        record=json.loads(p.influence_report)
        box.label(text='Last scan: '+record['object']+': '+record['representation'])
        box.label(text=str(len(record['over_limit_vertices']))+' over-limit vertices; maximum '+str(record['maximum']))


class KKVRC_OT_scan_influence_limits(bpy.types.Operator):
    bl_idname='kkvrc.scan_influence_limits'
    bl_label='Scan total bone influences'
    shoes:bpy.props.BoolProperty(default=False)
    select_vertices:bpy.props.BoolProperty(default=False)
    def execute(self,context):
        from . import weights_features as wf
        from .influence_policy import audit
        try:
            p=context.scene.kkvrc_shoes if self.shoes else context.scene.kkvrc_weight_workflow
            obj=(p.optimized or p.baseline or p.target) if self.shoes else (p.final or p.macro or p.initial or p.target)
            if obj is None:raise ValueError('Choose a fitted garment or create a result first')
            rig=obj.find_armature()
            if rig is None:raise ValueError('The mesh requires an armature')
            rows=wf.read_weights(obj);bones={b.name for b in rig.data.bones if b.use_deform}
            names=sorted({n for row in rows for n in row if n in bones})
            record=audit([[row.get(n,0) for n in names] for row in rows],settings(p))
            record.update(object=obj.name,stamp=wf.stamp(obj));p.influence_report=json.dumps(record)
            if self.select_vertices:
                if context.object and context.object.mode!='OBJECT':bpy.ops.object.mode_set(mode='OBJECT')
                for ob in context.selected_objects:ob.select_set(False)
                obj.hide_set(False);obj.select_set(True);context.view_layer.objects.active=obj
                indices=set(record['over_limit_vertices'])
                for v in obj.data.vertices:v.select=v.index in indices
                context.tool_settings.mesh_select_mode=(True,False,False)
                bpy.ops.object.mode_set(mode='EDIT')
            self.report({'INFO'},record['representation']+'; maximum '+str(record['maximum']))
            return {'FINISHED'}
        except Exception as exc:
            self.report({'ERROR'},str(exc));return {'CANCELLED'}


CLASSES=(KKVRC_OT_scan_influence_limits,)


def limit_initial_plan(plan, value):
    """Keep a dense reference, and prepare a budget-feasible initialization copy.

    No dynamic compression at initialization: pose evidence is not yet sampled.
    The main stage may resolve those conflicts if explicitly enabled.
    """
    from .influence_policy import select
    names=sorted({n for row in plan['writes'].values() for n in row})
    ids=sorted(map(int,plan['writes']))
    rows=[plan['writes'].get(i,plan['writes'].get(str(i))) for i in ids]
    w=np.array([[row.get(n,0.) for n in names] for row in rows])
    regions_list=['TORSO','ARM_L','ARM_R','LEG_L','LEG_R','DYNAMIC']
    dynamic=set(plan['retained_dynamic_bones'])
    regions=np.array([5 if n in dynamic else regions_list.index(plan['target_regions'][n]) for n in names])
    budgets=np.stack([w[:,regions==r].sum(1) for r in range(6)],axis=1)
    fingers=set(plan.get('finger_policy',{}).get('target_fingers',{}))
    fixed=np.broadcast_to([n in dynamic or n in fingers for n in names],w.shape).copy()
    p=policy(value)
    out,_,report=select(w,regions,budgets,fixed,w>0,dict(p,compress_dynamic=False))
    # Public policy stays the requested policy; this stage has no dynamic probes.
    report['policy']=p;report['stage']='INITIALIZATION_WITHOUT_DYNAMIC_APPROXIMATION'
    for row in report['exceptions']:row['vertex']=ids[row['vertex']]
    report['over_limit_vertices']=[ids[i] for i in report['over_limit_vertices']]
    plan['dense_reference_writes']=plan['writes']
    plan['writes']={i:{n:float(v) for n,v in zip(names,row) if v>0} for i,row in zip(ids,out)}
    plan['influence_policy']=p;plan['influence_support']=report
    from .weight_features import digest
    plan['plan_id']=digest({k:v for k,v in plan.items() if k!='plan_id'})


def sample_dynamic_probes(target,body,names,dynamic):
    """Isolated bend/twist probes; exact channel restoration, no physics fitting.

    The target body must be unaffected by the retained chains. This deliberately
    rejects grafts in which a supposedly dynamic subtree contains body deformers.
    """
    from . import weights_optimization as kin, weights_features as wf
    rig=kin._rig(target);body_support=wf.body_weight_support(body,target)
    if any(({n}|{b.name for b in rig.data.bones[n].children_recursive}) & body_support for n in dynamic):
        raise ValueError('Dynamic compression probes cannot include body-weighted descendants')
    saved={b.name:(b.rotation_mode,list(b.location),list(b.rotation_euler),list(b.rotation_quaternion),list(b.rotation_axis_angle),list(b.scale)) for b in rig.pose.bones}
    mode=rig.data.pose_position;before=wf.stamp(target);body_before=wf.stamp(body)
    train=[];holdout=[];errors=[]
    rest=kin._world_vertices(target);w=kin._dense(wf.read_weights(target),names)
    try:
        rig.data.pose_position='POSE'
        for name in sorted(dynamic):
            for axis in ('X','Y','Z'):
                for degrees,records in ((12.,train),(-7.,holdout)):
                    for b in rig.pose.bones:b.matrix_basis=Matrix.Identity(4)
                    rig.pose.bones[name].matrix_basis=Matrix.Rotation(math.radians(degrees),4,axis)
                    bpy.context.view_layer.update()
                    matrices=kin._matrices(rig,names)
                    basis=np.einsum('bij,vj->vbi',matrices[:,:3,:3],rest)+matrices[None,:,:3,3]
                    errors.append(float(np.max(abs(np.einsum('vb,vbc->vc',w,basis)-kin._world_vertices(target,True)))))
                    records.append(matrices)
    finally:
        for b in rig.pose.bones:
            mode_b,loc,euler,quat,axisangle,scale=saved[b.name]
            b.rotation_mode=mode_b;b.location=loc;b.rotation_euler=euler;b.rotation_quaternion=quat;b.rotation_axis_angle=axisangle;b.scale=scale
        rig.data.pose_position=mode;bpy.context.view_layer.update()
    if wf.stamp(target)!=before or wf.stamp(body)!=body_before:raise RuntimeError('Dynamic probe restoration failed')
    if max(errors,default=0)>2e-5:raise ValueError('Dynamic probe Blender/LBS mismatch')
    return dict(dynamic_train=np.array(train),dynamic_holdout=np.array(holdout)), max(float(np.linalg.norm(np.ptp(rest,axis=0))),1e-6)
