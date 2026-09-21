"""Independent accessory rigs with fixed attachment proxies and original chains."""
from pathlib import Path
from datetime import datetime
from uuid import uuid4
import json, math
import bpy
import numpy as np
from mathutils import Matrix, Vector, Quaternion
from . import mmd_preprocess as prep, mmd_preprocess_rules as body_rules, accessory_rules as rules


def scan(source,config):
    rig=prep.rig_of(source)
    if source.get('kkvrc_accessory_result'):raise ValueError('Object already processed; weights cannot be accumulated again')
    data=prep.bones(rig);rows=prep.rows(source);available=set(rig.data.bones.keys())
    weighted={n for row in rows for n,w in row.items() if n in available and w>0}
    if not weighted:raise ValueError('No actual bone weights')
    for row in rows:
        if any(not math.isfinite(w) or w<0 for w in row.values()):raise ValueError('Invalid weights')
        if abs(sum(w for n,w in row.items() if n in available)-1)>1e-5:
            raise ValueError('Effective bone weights are not normalized; dynamic shares will not be changed automatically')
    if any(not rig.data.bones[n].use_deform for n in weighted):raise ValueError('A weighted bone has deformation disabled; specialized handling required')
    # Custom transform spaces require references beyond target/subtarget.
    for p in rig.pose.bones:
        for c in p.constraints:
            if getattr(c,'space_object',None):raise ValueError('Custom constraint spaces are not supported: '+p.name)
    external=set(config.get('external',[]))
    if config.get('mmd_body',True):external.update(body_rules.protected_body(data))
    plan=rules.plan(data,weighted,config.get('owned_roots',[]),external)
    mapping={};occupied=available|set(source.vertex_groups.keys())
    for i,n in enumerate(plan['anchors'],1):
        name=f'ACC_Attach_{i:03d}'
        while name in occupied:name+='_' 
        occupied.add(name);mapping[n]=name
    root='ACC_Root'
    while root in occupied:root+='_' 
    return {'source':source.name,'source_rig':rig.name,'stamp':prep.stamp(source),
            'config':config,'plan':plan,'mapping':mapping,'root':root,'status':'SCANNED'}


def evaluated_normals(obj):
    bpy.context.view_layer.update()
    ev=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=ev.to_mesh()
    try:return np.array([n.vector[:] for n in mesh.corner_normals])
    finally:ev.to_mesh_clear()


def set_anchors(rig,reference,mapping):
    bpy.context.view_layer.update()
    transform=rig.matrix_world.inverted() @ reference.matrix_world
    for old,new in mapping.items():rig.pose.bones[new].matrix=transform @ reference.pose.bones[old].matrix
    bpy.context.view_layer.update()


def remove_object(obj):
    data=obj.data;kind=obj.type;bpy.data.objects.remove(obj,do_unlink=True)
    if data.users==0:
        if kind=='MESH':bpy.data.meshes.remove(data)
        elif kind=='ARMATURE':bpy.data.armatures.remove(data)


def validate_motion(obj,reference,job):
    rig=obj.modifiers[0].object;ref=reference.modifiers[0].object
    own=job['plan']['owned'];mapping=job['mapping']
    snapshots={r.name:{p.name:p.matrix_basis.copy() for p in r.pose.bones} for r in (rig,ref)}
    own_controls=[n for n in own if not ref.pose.bones[n].constraints and not getattr(ref.pose.bones[n],'is_mmd_shadow_bone',False)]
    controls=list(dict.fromkeys([*mapping,*job['plan']['roots'],*own_controls]))
    states=[('rest',[])]+[(n,[n]) for n in controls]
    if mapping and own_controls:states.append(('attachment_and_chain',[next(iter(mapping)),own_controls[0]]))
    out=[];base=prep.evaluate(reference)
    extent=max(float(np.linalg.norm(np.ptp(base,axis=0))),1e-3)
    try:
        for label,changed in states:
            for r in (rig,ref):
                for p in r.pose.bones:p.matrix_basis=snapshots[r.name][p.name]
            for n in changed:
                p=ref.pose.bones[n]
                p.matrix_basis=p.matrix_basis @ Quaternion(Vector((1,0,0)),math.radians(17)).to_matrix().to_4x4()
            bpy.context.view_layer.update()
            for n in own:rig.pose.bones[n].matrix_basis=ref.pose.bones[n].matrix_basis.copy()
            set_anchors(rig,ref,mapping)
            a,b=prep.evaluate(obj),prep.evaluate(reference)
            error=float(np.linalg.norm(a-b,axis=1).max())
            if error>extent*3e-6:raise ValueError('Accessory motion mismatch: '+label+' / '+str(error))
            out.append({'pose':label,'max_error':error,'moved_vertices':int(np.sum(np.linalg.norm(b-base,axis=1)>extent*1e-7))})
        if not any(r['moved_vertices'] for r in out):raise ValueError('Motion validation produced no effective movement')
    finally:
        for r in (rig,ref):
            for p in r.pose.bones:p.matrix_basis=snapshots[r.name][p.name]
        bpy.context.view_layer.update()
    return out


def apply(source,config,expected_stamp,directory):
    job=scan(source,config)
    if job['stamp']!=expected_stamp:raise ValueError('Source data changed; rescan')
    base=Path(bpy.path.abspath(directory))
    if not directory or (directory.startswith('//') and not bpy.data.filepath):raise ValueError('Save the project or specify an absolute output directory first')
    folder=base/(datetime.now().strftime('%Y%m%d-%H%M%S')+'-'+uuid4().hex[:6]);folder.mkdir(parents=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(folder/'before.blend'),copy=True)
    if not (folder/'before.blend').is_file():raise ValueError('Backup failed')
    collection=prep.create_collection('Accessory '+source.name)
    try:
        obj,rig=prep.clone(source,collection,'Accessory')
        reference,ref=prep.clone(source,collection,'AccessoryReference')
        original=prep.attributes(source);expected=rules.remap(prep.rows(source),job['mapping'])
        source_normals=evaluated_normals(source)
        old_rest={b.name:b.matrix_local.copy() for b in rig.data.bones}
        mapping=job['mapping'];own=job['plan']['owned']
        # Rename only proxy copies; original body skeleton is never modified.
        for old,new in mapping.items():rig.data.bones[old].name=new
        for p in rig.pose.bones:
            if p.name in mapping.values():
                for c in list(p.constraints):p.constraints.remove(c)
                if hasattr(p,'mmd_bone'):
                    p.mmd_bone.has_additional_rotation=False;p.mmd_bone.has_additional_location=False
                    p.mmd_bone.additional_transform_bone='';p.mmd_bone.display_connection_bone=''
                    p.mmd_bone.name_j='';p.mmd_bone.name_e=''
            else:
                for c in p.constraints:
                    for target in [c,*list(getattr(c,'targets',()))]:
                        for field in ('subtarget','pole_subtarget'):
                            value=getattr(target,field,None)
                            if value in mapping:setattr(target,field,mapping[value])
                if hasattr(p,'mmd_bone'):
                    for field in ('additional_transform_bone','display_connection_bone'):
                        value=getattr(p.mmd_bone,field,'')
                        if value in mapping:setattr(p.mmd_bone,field,mapping[value])
        prep.activate(rig);bpy.ops.object.mode_set(mode='EDIT')
        root=rig.data.edit_bones.new(job['root']);root.head=(0,0,0);root.tail=(0,0,.05);root.use_deform=False
        for old,new in mapping.items():
            b=rig.data.edit_bones[new];matrix=b.matrix.copy();b.use_connect=False;b.parent=root;b.matrix=matrix
        for name in own:
            b=rig.data.edit_bones[name]
            if not b.parent:
                matrix=b.matrix.copy();b.parent=root;b.matrix=matrix
        for name in job['plan']['remove']:rig.data.edit_bones.remove(rig.data.edit_bones[name])
        bpy.ops.object.mode_set(mode='OBJECT')
        rest_error=0.
        for name in own:
            actual_rest=np.array(rig.data.bones[name].matrix_local);saved_rest=np.array(old_rest[name])
            delta=float(np.max(np.abs(actual_rest-saved_rest)));rest_error=max(rest_error,delta)
            # Blender edit-mode round-trips float32 head/tail/roll. Reject
            # significant changes and still validate all actual deformations.
            if delta>2e-5 or np.linalg.norm(actual_rest[:3,3]-saved_rest[:3,3])>1e-6:
                raise ValueError('Owned bone rest matrix changed: '+name+' / '+str(delta))
        for old,new in mapping.items():
            rig.data.bones[new]['attachment_source_bone']=old
            rig.data.bones[new]['accessory_fixed_anchor']=True
        set_anchors(rig,ref,mapping)
        # Rebuild group membership by names, retaining non-bone metadata groups.
        old_groups=[(g.name,g.lock_weight) for g in source.vertex_groups]
        obj.vertex_groups.clear()
        keep_names=set(own)|set(mapping.values())
        for name,locked in old_groups:
            new=mapping.get(name,name)
            if name in old_rest and new not in keep_names:continue
            g=obj.vertex_groups.new(name=new);g.lock_weight=locked
        for i,row in enumerate(expected):
            for name,w in row.items():
                if name not in obj.vertex_groups:
                    if name in old_rest and w==0:continue
                    obj.vertex_groups.new(name=name)
                obj.vertex_groups[name].add([i],w,'REPLACE')
        actual=prep.rows(obj)
        for src,dst in zip(expected,actual):
            for n,w in src.items():
                if abs(dst.get(n,0.)-w)>1e-7:raise ValueError('Weight mapping mismatch')
            if abs(sum(src.values())-sum(dst.values()))>1e-6:raise ValueError('Total influence share is not conserved')
        attrs=prep.attributes(obj)
        for key in original:
            if key!='weights' and attrs[key]!=original[key]:raise ValueError('Mesh attributes changed: '+key)
        static=float(np.linalg.norm(prep.evaluate(obj)-prep.evaluate(source),axis=1).max())
        if static>2e-6:raise ValueError('Accessory rest appearance mismatch: '+str(static))
        normals=evaluated_normals(obj)
        angle=float(np.degrees(np.arccos(np.clip(np.sum(normals*source_normals,axis=1),-1,1))).max())
        if angle>1:raise ValueError('Accessory normal mismatch')
        # References must resolve after renaming/deletion; anchors carry no MMD roles.
        data=prep.bones(rig)
        if set(b['name'] for b in data)!=set(own)|set(mapping.values())|{job['root']}:raise ValueError('Bone set mismatch')
        for b in data:
            if set(b['dependencies'])-set(rig.data.bones.keys()):raise ValueError('Dangling bone reference')
        motions=validate_motion(obj,reference,job)
        if prep.stamp(source)!=job['stamp']:raise ValueError('Source object changed')
        remove_object(reference);remove_object(ref)
        obj.name=source.name+'_Accessory';rig.name=source.name+'_Accessory_Rig'
        obj['kkvrc_accessory_result']=True
        rig['kkvrc_attachment_map']=json.dumps(mapping,ensure_ascii=False)
        rig['kkvrc_attachment_source_rig']=job['source_rig']
        rig['kkvrc_attachment_status']='PENDING_TARGET_ATTACHMENT'
        result=dict(job,status='PENDING_TARGET_ATTACHMENT',result=obj.name,result_rig=rig.name,
                    directory=str(folder),collection=collection.name,bones_after=len(rig.data.bones),
                    static_error=static,normal_max_angle=angle,motion_validation=motions,
                    rest_matrix_roundtrip_max=rest_error,
                    weights_preserved=True,source_unchanged=True)
        obj['kkvrc_accessory_report']=str(folder/'result.json')
        prep.dump(folder/'result.json',result);prep.dump(folder/'weights.json',actual)
        rig.hide_set(True);prep.activate(obj)
        bpy.ops.wm.save_as_mainfile(filepath=str(folder/'result.blend'),copy=True)
        return result
    except Exception:
        prep.discard(collection);prep.activate(source);raise
