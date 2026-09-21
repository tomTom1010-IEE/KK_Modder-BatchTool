"""Blender adapter for offline kinematic optimization; no SciPy dependency here."""
import math
import bpy
import numpy as np
from mathutils import Matrix, Vector
from . import weight_features as core
from . import weights_features as wf


def source_pose_contract(obj):
    """Opt-in contract for self-contained, evaluated MMD-style source constraints.

    This does not bake or remove constraints. Every sampled deformation still
    passes the actual Blender/source-LBS check before optimization and writeback.
    """
    from .mmd_preprocess import properties
    rig = obj.find_armature()
    if rig is None: raise ValueError('Source armature required')
    if rig.constraints: raise ValueError('Source object constraints are unsupported')
    for owner in (obj, rig, rig.data):
        a = owner.animation_data
        if a and (a.action or a.drivers or a.nla_tracks):
            raise ValueError('Animated source requires a time-dependent sampling contract')
    records = []
    allowed = {'IK', 'LIMIT_ROTATION', 'DAMPED_TRACK', 'COPY_TRANSFORMS', 'TRANSFORM'}
    for bone in rig.pose.bones:
        if bone.bone.bbone_segments != 1: raise ValueError('Segmented B-Bones unsupported')
        for c in bone.constraints:
            if c.type not in allowed: raise ValueError('Unreviewed source constraint type: '+c.type)
            for field, sub in [('target','subtarget'),('pole_target','pole_subtarget'),('space_object','space_subtarget')]:
                target = getattr(c,field,None)
                if target is not None and target != rig: raise ValueError('External source constraint dependency')
                if target is not None and getattr(c,sub,'') not in rig.data.bones:
                    raise ValueError('Missing source constraint bone')
            if c.type == 'IK' and c.use_tail and c.chain_count == 0:
                raise ValueError('Unbounded source IK chain')
            records.append([bone.name, properties(c)])
    return {'schema':1,'rig':rig.name,'constraints':records,'digest':core.digest(records)}


def _rig(obj, source_contract=None):
    if obj.type != 'MESH' or obj.mode != 'OBJECT' or obj.data.users != 1:
        raise ValueError('Single-user mesh in Object mode required')
    mods = list(obj.modifiers)
    if len(mods) != 1 or mods[0].type != 'ARMATURE' or not mods[0].object:
        raise ValueError('Optimizer currently requires exactly one Armature modifier')
    m = mods[0]
    if m.use_deform_preserve_volume or m.use_bone_envelopes or m.vertex_group or not m.use_vertex_groups or not m.show_viewport:
        raise ValueError('Only unmasked LBS with vertex groups is supported')
    if obj.data.shape_keys and any(abs(k.value)>1e-9 for k in obj.data.shape_keys.key_blocks[1:]):
        raise ValueError('Active shape keys require an explicit baked optimization context')
    rig = m.object
    if source_contract is not None and source_contract != source_pose_contract(obj):
        raise ValueError('Source pose contract changed')
    if (any(b.constraints for b in rig.pose.bones) and source_contract is None) or (rig.animation_data and (rig.animation_data.action or rig.animation_data.drivers or rig.animation_data.nla_tracks)):
        raise ValueError('Animated/constrained rig needs a separately sampled pose contract')
    return rig


def _frame(rig, name, posed):
    m = rig.matrix_world @ (rig.pose.bones[name].matrix if posed else rig.data.bones[name].matrix_local)
    a = np.array(m, dtype=float)
    u,_,vt = np.linalg.svd(a[:3,:3]); rot = u@vt
    if np.linalg.det(rot)<0:raise ValueError('Reflected reference frame')
    a[:3,:3]=rot
    return a


def _world_vertices(obj, evaluated=False):
    if not evaluated:
        return np.array([obj.matrix_world@v.co for v in obj.data.vertices],float)
    ev=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=ev.to_mesh()
    try:return np.array([ev.matrix_world@v.co for v in mesh.vertices],float)
    finally:ev.to_mesh_clear()


def _matrices(rig, names):
    return np.array([rig.matrix_world@rig.pose.bones[n].matrix@rig.data.bones[n].matrix_local.inverted()@rig.matrix_world.inverted() for n in names],float)


def _dense(rows,names):
    return np.array([[row.get(n,0.) for n in names] for row in rows],float)


def export_context(source, target, body, *, roles, bone_map, source_regions,
                   target_regions, finger_policy, poses, reviewed_patterns,
                   selected=None, local_refinement=None, reference_anchors=None, excluded_body_groups=(), source_contract=None):
    """Read-only scene sampling, including exact finally restoration of pose channels.

    Pose controls: [{source:[(bone,fraction)], target:[(bone,fraction)],
    axis:[world x,y,z], degrees:number}]. Explicit macro retargeting, not Euler copying.
    Pattern review is semantic authorization, not inferred from numerical labels.
    """
    if reviewed_patterns not in {'uniform','edge_gradient','uniform_and_edge_in_separate_regions'}:
        raise ValueError('Unsupported/unreviewed mixed pattern: manual analysis required')
    sr,tr,br=_rig(source,source_contract),_rig(target),_rig(body)
    if tr != br or sr==tr:raise ValueError('Distinct source rig and shared target/body rig required')
    if wf.topology(source)!=wf.topology(target):raise ValueError('Garment topology/index correspondence changed')
    snapshot=wf.capture_snapshot(source,roles)
    original=wf.read_weights(source);initial=wf.read_weights(target)
    omitted = sorted({n for row in original for n,w in row.items() if w>0
                      and n in sr.data.bones and sr.data.bones[n].use_deform
                      and roles.get(n) not in {'BODY','DYNAMIC'}})
    if omitted:raise ValueError('Source reference would discard effective deform weights: '+str(omitted))
    reference_anchors = dict(reference_anchors or {})
    for name,anchor in reference_anchors.items():
        if name not in sr.data.bones or anchor not in sr.data.bones or roles.get(name)!='BODY' or roles.get(anchor)!='BODY':
            raise ValueError('Invalid source anatomical reference anchor: '+name)
        if source_regions[name]!=source_regions[anchor] or anchor not in bone_map:
            raise ValueError('Cross-region/unmapped source reference anchor: '+name)
    source_names=sorted({n for row in original for n in row if roles[n] in {'BODY','DYNAMIC'}})
    target_names=sorted({n for row in initial for n in row if roles.get(n) != 'IGNORE'})
    if any(n in tr.data.bones and tr.data.bones[n].use_deform for row in initial for n in row if roles.get(n)=='IGNORE'):
        raise ValueError('Cannot ignore a deforming target influence')
    if set(target_names)&set(excluded_body_groups):raise ValueError('Initial state contains excluded body influences')
    for n in target_names:
        if n not in tr.data.bones or not tr.data.bones[n].use_deform:raise ValueError('Unbound target influence: '+n)
    for n in source_names:
        if n not in sr.data.bones or not sr.data.bones[n].use_deform:raise ValueError('Unbound source influence: '+n)
    dynamic={n for n in source_names if roles[n]=='DYNAMIC'}
    body_support=wf.body_weight_support(body,target)
    unsupported=set(target_names)-body_support-dynamic
    if unsupported:raise ValueError('Unsupported body weights in optimizer initial state: '+str(sorted(unsupported)))
    if any(bone_map.get(n,n)!=n for n in dynamic):raise ValueError('First adapter requires retained dynamic names unchanged')
    regions_list=['TORSO','ARM_L','ARM_R','LEG_L','LEG_R','DYNAMIC']
    regions=np.array([5 if n in dynamic else regions_list.index(target_regions[n]) for n in target_names])
    budget=np.zeros((len(original),6));sw=_dense(original,source_names)
    if np.any(sw.sum(axis=1)<=0):raise ValueError('Unweighted source vertices')
    sw/=sw.sum(axis=1)[:,None]
    for j,n in enumerate(source_names):budget[:,5 if n in dynamic else regions_list.index(source_regions[n])]+=sw[:,j]
    w0=_dense(initial,target_names)
    if np.max(abs(w0.sum(axis=1)-1))>1e-6:raise ValueError('Initial target must be normalized')
    for r in range(6):
        if np.max(abs(w0[:,regions==r].sum(axis=1)-budget[:,r]))>1e-6:raise ValueError('Initial regional budgets differ from source')
    fixed=np.zeros_like(w0,dtype=bool)
    tf=finger_policy['target_fingers'];sf=finger_policy['source_fingers'];enabled=set(finger_policy['enabled'])
    for j,n in enumerate(target_names):
        if n in dynamic or n in tf:
            fixed[:,j]=True
            expected=np.zeros(len(w0))
            if n in dynamic:expected=sw[:,source_names.index(n)]
            elif tf[n] in enabled:
                for k,srcname in enumerate(source_names):
                    if sf.get(srcname)==tf[n] and bone_map.get(srcname)==n:expected+=sw[:,k]
            if np.max(abs(w0[:,j]-expected))>1e-6:raise ValueError('Initial dynamic/finger differs from preserved source: '+n)
    # Candidate support comes from current reviewed solution plus one-ring evidence.
    candidates=(w0>0).copy()
    for edge in target.data.edges:
        a,b=edge.vertices
        for v,u in ((a,b),(b,a)):
            candidates[v]|=(w0[u]>0)&(budget[v,regions]>0)&~fixed[v]
    delta_limits=None
    if local_refinement is not None:
        if selected is None or not len(selected):raise ValueError('Local refinement requires explicit vertices')
        allowed=np.zeros_like(candidates)
        for region,names in local_refinement['region_bones'].items():
            if region not in regions_list[:5]:raise ValueError('Only body regions may be refined')
            for name in names:
                if name not in target_names or target_regions.get(name)!=region or name in tf:
                    raise ValueError('Invalid local candidate bone: '+name)
                j=target_names.index(name)
                allowed[:,j]=budget[:,regions_list.index(region)]>0
        fixed |= ~allowed
        candidates=(w0>0)|(allowed&~fixed)
        delta_limits=np.zeros(len(w0))
        for i in selected:delta_limits[i]=float(local_refinement['delta_limits'][str(i)])
        if not np.isfinite(delta_limits).all() or np.any(delta_limits<0) or np.any(delta_limits>1):raise ValueError('Invalid local delta limits')
        for spec in poses:
            for ctrl in spec['controls']:
                for side in ['source','target']:
                    if any(n not in local_refinement['pose_bones'][side] for n,f in ctrl[side]):
                        raise ValueError('Macro/unapproved pose bone in local stage')
    anchors=[]
    for row in original:
        bodyrow={n:w for n,w in row.items() if roles[n]=='BODY' and n not in sf}
        if bodyrow:anchor=max(bodyrow,key=bodyrow.get)
        elif any(n in sf for n in row):
            name=max((n for n in row if n in sf),key=row.get)
            b=sr.data.bones[name].parent
            while b and b.name not in bone_map:b=b.parent
            if b is None:raise ValueError('No hand reference for finger-only vertex')
            anchor=b.name
        else:
            name=max((n for n in row if roles[n]=='DYNAMIC'),key=row.get)
            b=sr.data.bones[name]
            while b and b.name not in bone_map:b=b.parent
            anchor=b.name if b else None
            # Retained dynamics may exist in bone_map: climb to a body anchor.
            while anchor in dynamic:
                b=sr.data.bones[anchor].parent
                anchor=b.name if b else None
            if anchor not in bone_map:raise ValueError('No body attachment frame')
        anchors.append(reference_anchors.get(anchor,anchor))
    anchor_names=sorted(set(anchors));anchor_ids=np.array([anchor_names.index(a) for a in anchors])
    context_stamp=wf.stamp(target);source_stamp=wf.stamp(source);body_stamp=wf.stamp(body)
    saved={rig.name:{b.name:(b.rotation_mode,list(b.location),list(b.rotation_euler),list(b.rotation_quaternion),list(b.rotation_axis_angle),list(b.scale)) for b in rig.pose.bones} for rig in (sr,tr)}
    pose_modes={r.name:r.data.pose_position for r in (sr,tr)}
    source_mats=[];target_mats=[];source_frames=[];target_frames=[];body_poses=[];actual_target=[];actual_source=[]
    allposes=[{'name':'rest','controls':[],'kind':'common','weight':1.}]+list(poses)
    try:
        for spec in allposes:
            for rig in (sr,tr):
                rig.data.pose_position='POSE'
                for b in rig.pose.bones:b.matrix_basis=Matrix.Identity(4)
            bpy.context.view_layer.update()
            for ctrl in spec['controls']:
                for rig,key in ((sr,'source'),(tr,'target')):
                    axis=Vector(ctrl.get(key+'_axis',ctrl['axis']))
                    if axis.length<1e-8 or not all(math.isfinite(v) for v in axis):raise ValueError('Invalid pose world axis')
                    axis.normalize()
                    for name,factor in ctrl[key]:
                        local_axis=(rig.matrix_world@rig.data.bones[name].matrix_local).to_3x3().inverted()@axis
                        rig.pose.bones[name].matrix_basis @= Matrix.Rotation(math.radians(ctrl['degrees']*factor),4,local_axis.normalized())
            bpy.context.view_layer.update()
            source_mats.append(_matrices(sr,source_names));target_mats.append(_matrices(tr,target_names))
            source_frames.append(np.array([_frame(sr,n,True) for n in anchor_names])[anchor_ids])
            target_frames.append(np.array([_frame(tr,bone_map[n],True) for n in anchor_names])[anchor_ids])
            body_poses.append(_world_vertices(body,True));actual_target.append(_world_vertices(target,True))
            actual_source.append(_world_vertices(source,True))
    finally:
        for rig in (sr,tr):
            for b in rig.pose.bones:
                mode,loc,euler,quat,axisangle,scale=saved[rig.name][b.name]
                b.rotation_mode=mode;b.location=loc;b.rotation_euler=euler;b.rotation_quaternion=quat;b.rotation_axis_angle=axisangle;b.scale=scale
            rig.data.pose_position=pose_modes[rig.name]
        bpy.context.view_layer.update()
    if wf.stamp(target)!=context_stamp or wf.stamp(source)!=source_stamp or wf.stamp(body)!=body_stamp:
        raise RuntimeError('Sampling state restoration mismatch')
    if source_contract is not None and source_contract != source_pose_contract(source):
        raise RuntimeError('Source constraints changed during sampling')
    target.data.calc_loop_triangles();body.data.calc_loop_triangles()
    arrays={'source_rest':_world_vertices(source),'target_rest':_world_vertices(target),
        'source_weights':sw,'initial':w0,'source_matrices':np.array(source_mats),'target_matrices':np.array(target_mats),
        'source_frames':np.array(source_frames),'target_frames':np.array(target_frames),
        'body_poses':np.array(body_poses),'actual_target':np.array(actual_target),'actual_source':np.array(actual_source),
        'triangles':np.array([t.vertices[:] for t in target.data.loop_triangles],int),
        'body_triangles':np.array([t.vertices[:] for t in body.data.loop_triangles],int),
        'edges':np.array([e.vertices[:] for e in target.data.edges],int),
        'smooth_edges':np.array([e.vertices[:] for e in target.data.edges if not e.use_edge_sharp],int),
        'anchor_length_ratio':np.array([(tr.matrix_world.to_3x3()@(tr.data.bones[bone_map[n]].tail_local-tr.data.bones[bone_map[n]].head_local)).length / max((sr.matrix_world.to_3x3()@(sr.data.bones[n].tail_local-sr.data.bones[n].head_local)).length,1e-10) for n in anchors]),
        'regions':regions,'budgets':budget,
        'fixed':fixed,'candidates':candidates,'selected':np.arange(len(w0)) if selected is None else np.array(selected,int)}
    metadata={'schema':1,'target':target.name,'source':source.name,'body':body.name,
        'target_stamp':context_stamp,'source_stamp':source_stamp,'body_stamp':body_stamp,'topology':wf.topology(target),
        'target_names':target_names,'source_names':source_names,'poses':allposes,'snapshot_id':snapshot['id'],
        'finger_policy':finger_policy,'source_regions':source_regions,'target_regions':target_regions,
        'reviewed_patterns':reviewed_patterns,'anchor_names':anchor_names,'roles':roles,'bone_map':bone_map,
        'reference_anchors':reference_anchors,'source_reference_contract':'all_effective_deform_weights_blender_verified',
        'source_pose_contract':source_contract,
        'allowed_body_bones':sorted(body_support-set(excluded_body_groups)),'retained_dynamic_bones':sorted(dynamic),
        'excluded_body_groups':sorted(excluded_body_groups),
        'arrays_digest':core.digest({k:v.tolist() for k,v in arrays.items()})}
    if local_refinement is not None:
        arrays['delta_limits']=delta_limits
        metadata['local_refinement']=local_refinement
        metadata['arrays_digest']=core.digest({k:v.tolist() for k,v in arrays.items()})
    metadata['context_id']=core.digest(metadata)
    return arrays,metadata


def prepare_optimized_plan(target, arrays, metadata, candidate, validation, destination=None,
                           existing_collision_authorization=None, collision_review=False):
    """Rebuild a checked write plan; never edit a signed legacy proposal."""
    if metadata['context_id']!=core.digest({k:v for k,v in metadata.items() if k!='context_id'}):raise ValueError('Context metadata changed')
    if metadata['arrays_digest']!=core.digest({k:v.tolist() for k,v in arrays.items()}):raise ValueError('Context arrays changed')
    authorized_existing = False
    if existing_collision_authorization is not None:
        if not isinstance(existing_collision_authorization,str) or not existing_collision_authorization.strip():
            raise ValueError('Explicit user authorization reason required')
        required=('holdout_motion_ok','fixed_ok','body_admission_ok','source_reference_ok',
                  'local_limits_ok','exterior_geometry_unchanged','dynamic_geometry_unchanged')
        authorized_existing = all(validation.get(k) is True for k in required) and validation.get('max_region_error',1.)<1e-6
        poses=validation.get('poses',[])
        authorized_existing &= len(poses)==len(metadata['poses']) and bool(poses)
        for pose in poses:
            before,after=pose['before']['in_scope'],pose['after']['in_scope']
            authorized_existing &= set(map(tuple,after['triangle_pairs'])) <= set(map(tuple,before['triangle_pairs']))
            authorized_existing &= all(after[k]<=before[k] for k in ('penetrating_samples','ambiguous_coplanar_pairs'))
            authorized_existing &= after['max_oriented_depth'] <= before['max_oriented_depth']+1e-6
        if not authorized_existing:
            raise ValueError('Existing-collision authorization cannot accept new/worse contacts or failed non-contact checks')
    review_allowed=bool(collision_review and destination is not None and validation.get('non_contact_ok') is True)
    if collision_review and not review_allowed:raise ValueError('Collision review requires a separate copy and passed non-contact validation')
    if validation.get('context_id')!=metadata['context_id'] or validation.get('candidate_digest')!=core.digest(np.asarray(candidate).tolist()) or not (validation.get('accepted') or authorized_existing or review_allowed):
        raise ValueError('Candidate lacks accepted independent validation')
    for key,stamp_key in [('target','target_stamp'),('source','source_stamp'),('body','body_stamp')]:
        obj=bpy.data.objects.get(metadata[key])
        if obj is None or wf.stamp(obj)!=metadata[stamp_key]:raise ValueError('Stale optimization context: '+key)
    if metadata.get('source_pose_contract') is not None and source_pose_contract(bpy.data.objects[metadata['source']]) != metadata['source_pose_contract']:
        raise ValueError('Stale source constraint contract')
    if target.name!=metadata['target']:raise ValueError('Wrong target')
    candidate=np.asarray(candidate,float);w0=arrays['initial'];fixed=arrays['fixed'];regions=arrays['regions']
    if candidate.shape!=w0.shape or not np.isfinite(candidate).all() or np.any(candidate<0):raise ValueError('Invalid candidate')
    if 'delta_limits' in arrays and np.any(abs(candidate-w0)>arrays['delta_limits'][:,None]+1e-7):raise ValueError('Local correction limit exceeded')
    if np.max(abs(candidate[fixed]-w0[fixed]),initial=0)>1e-8:raise ValueError('Fixed contributions changed')
    if np.any(candidate[~arrays['candidates']]>1e-10):raise ValueError('Unauthorized candidate bone')
    for r in range(6):
        if np.max(abs(candidate[:,regions==r].sum(axis=1)-arrays['budgets'][:,r]))>1e-6:raise ValueError('Regional budget drift')
    selected=set(int(i) for i in arrays['selected'])
    if any(not np.array_equal(candidate[i],w0[i]) for i in range(len(w0)) if i not in selected):raise ValueError('Changed protected vertex')
    original=target
    if destination is not None:
        if destination==original or destination.data==original.data or destination.data.users!=1:
            raise ValueError('Destination must be an independent mesh copy')
        if wf.stamp(destination)!=metadata['target_stamp']:
            raise ValueError('Destination differs from validated target baseline')
        target=destination
    names=metadata['target_names'];writes={i:{n:float(w) for n,w in zip(names,candidate[i]) if w>0} for i in selected}
    plan={'target':target.name,'expected_stamp':wf.stamp(target),'topology':wf.topology(target),
          'excluded_body_groups':metadata.get('excluded_body_groups',[]),
          'writes':writes,'managed_groups':names,'snapshot_id':metadata['snapshot_id'],
          'summary':{'optimized_vertices':len(writes)},'skipped':{},'optimization_context':metadata['context_id'],
          'context_sources':{metadata['source']:metadata['source_stamp'],metadata['body']:metadata['body_stamp']}}
    if metadata.get('source_pose_contract') is not None:
        plan['source_pose_contract']={'source':metadata['source'],'contract':metadata['source_pose_contract']}
    if authorized_existing:
        plan['existing_collision_authorization']={'reason':existing_collision_authorization,
            'validation_digest':core.digest(validation),'policy':'explicitly accepted existing intersections; no new triangle pairs, sample count increase or depth regression above 1e-6',
            'strict_collision_acceptance':bool(validation.get('accepted'))}
    if review_allowed:
        plan['collision_review']={'status':'PENDING_USER_REVIEW' if not validation['contact_ok'] else 'CLEAR',
            'validation_digest':core.digest(validation),'vertices':validation.get('collision_review_vertices',[])}
    if destination is not None:
        plan['context_sources'][original.name]=metadata['target_stamp']
        plan['copied_from']=original.name
    wf.attach_body_support(plan,bpy.data.objects[metadata['body']],target,metadata['retained_dynamic_bones'])
    plan['plan_id']=core.digest(plan)
    return plan
