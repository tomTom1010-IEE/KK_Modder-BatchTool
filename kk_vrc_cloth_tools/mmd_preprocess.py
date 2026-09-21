"""Staged, reversible single-garment MMD preparation. No weight transfer."""
import hashlib
import json
import math
from pathlib import Path
from datetime import datetime
from uuid import uuid4
import bpy
import numpy as np
from mathutils import Matrix, Vector, Quaternion
from . import mmd_preprocess_rules as rules


def dump(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


def hash_data(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def rows(obj):
    names = {g.index: g.name for g in obj.vertex_groups}
    return [{names[g.group]: float(g.weight) for g in v.groups} for v in obj.data.vertices]


def attributes(obj):
    mesh = obj.data
    return {'topology': hash_data(([list(e.vertices) for e in mesh.edges], [list(p.vertices) for p in mesh.polygons])),
            'weights': hash_data(rows(obj)),
            'uv': hash_data({u.name: [list(d.uv) for d in u.data] for u in mesh.uv_layers}),
            'materials': hash_data(([s.material.name if s.material else None for s in obj.material_slots], [p.material_index for p in mesh.polygons])),
            'sharp': hash_data([e.use_edge_sharp for e in mesh.edges]),
            'custom_normals': mesh.has_custom_normals}


def properties(owner):
    """Fingerprint constraint parameters as well as its visible name/target."""
    result = {}
    for prop in owner.bl_rna.properties:
        key = prop.identifier
        if key in {'rna_type', 'is_valid', 'error_location', 'error_rotation'}: continue
        value = getattr(owner, key)
        if prop.type == 'POINTER':
            result[key] = getattr(value, 'name_full', getattr(value, 'name', None))
        elif prop.type == 'COLLECTION':
            if key == 'targets': result[key] = [properties(v) for v in value]
        elif getattr(prop, 'is_array', False):
            result[key] = [list(v) if hasattr(v, '__iter__') else v for v in value]
        elif isinstance(value, (str, int, float, bool)) or value is None: result[key] = value
    return result


def bones(rig):
    out = []
    for b in rig.data.bones:
        p = rig.pose.bones[b.name]; meta = getattr(p, 'mmd_bone', None)
        deps = set()
        for field in ('bbone_custom_handle_start', 'bbone_custom_handle_end'):
            handle = getattr(b, field, None)
            if handle: deps.add(handle.name)
        if meta and (meta.has_additional_rotation or meta.has_additional_location):
            deps.add(meta.additional_transform_bone)
        if meta and getattr(meta,'display_connection_bone',''):
            deps.add(meta.display_connection_bone)
        for c in p.constraints:
            for target in [c, *list(getattr(c, 'targets', ()) )]:
                for field, sub in [('target', 'subtarget'), ('pole_target', 'pole_subtarget')]:
                    value = getattr(target, field, None)
                    if value and value != rig:
                        raise ValueError('Bone constraints reference external objects; handle these first: ' + b.name)
                    if value == rig and getattr(target, sub, ''): deps.add(getattr(target, sub))
        out.append({'name': b.name, 'name_j': getattr(meta, 'name_j', ''),
                    'parent': b.parent.name if b.parent else None, 'use_deform': b.use_deform,
                    'helper': bool(getattr(p, 'is_mmd_shadow_bone', False)),
                    'dependencies': sorted(deps), 'matrix': [list(r) for r in b.matrix_local],
                    'head': list(b.head_local), 'tail': list(b.tail_local),
                    'inherit_scale': b.inherit_scale, 'use_inherit_rotation': b.use_inherit_rotation,
                    'constraints': [properties(c) for c in p.constraints],
                    'mmd': properties(meta) if meta else {}})
    return out


def rig_of(source):
    if not source or source.type != 'MESH' or source.mode != 'OBJECT':
        raise ValueError('Select one garment mesh in Object Mode')
    mods = list(source.modifiers)
    if len(mods) != 1 or mods[0].type != 'ARMATURE' or not mods[0].object:
        raise ValueError('This version requires a single Armature modifier; process other modifiers separately first')
    m = mods[0]
    if m.use_deform_preserve_volume or m.use_bone_envelopes or m.vertex_group or not m.use_vertex_groups or not m.show_viewport:
        raise ValueError('This version supports unmasked vertex-group LBS only; SDEF/DQS are not converted automatically')
    if source.data.shape_keys:
        raise ValueError('Shape keys/SDEF detected; this version does not bake or delete them automatically. Process them separately first')
    rig = m.object
    if rig.mode != 'OBJECT' or source.constraints or rig.constraints:
        raise ValueError('Source must be in Object Mode without object constraints')
    for owner in (source, source.data, rig, rig.data):
        ad = owner.animation_data
        if ad and (ad.action or ad.drivers or ad.nla_tracks):
            raise ValueError('Source has animation/drivers; handle these explicitly first. They are not deleted automatically')
    if rig.data.pose_position != 'POSE': raise ValueError('Set the source armature to Pose Position before scanning')
    return rig


def stamp(source, include_pose=True):
    rig = rig_of(source)
    value = {'attributes': attributes(source), 'coords': [list(v.co) for v in source.data.vertices],
             'normals': [list(n.vector) for n in source.data.corner_normals],
             'source_world': [list(r) for r in source.matrix_world], 'rig_world': [list(r) for r in rig.matrix_world],
             'groups': [g.name for g in source.vertex_groups], 'bones': bones(rig)}
    if include_pose: value['basis'] = {p.name: [list(r) for r in p.matrix_basis] for p in rig.pose.bones}
    return hash_data(value)


def scan(source, config):
    rig = rig_of(source)
    if source.get('kkvrc_mmd_preprocessed') or source.get('preprocess_round'):
        raise ValueError('Object is already marked as preprocessed; select the original input to avoid double baking')
    data = bones(rig); available = set(rig.data.bones.keys())
    weight_rows = rows(source)
    if any(not math.isfinite(w) or w < 0 for row in weight_rows for w in row.values()):
        raise ValueError('Non-finite or negative weights found; repair source data first')
    weighted = {n for row in weight_rows for n, w in row.items() if w > 0 and n in available}
    if not weighted: raise ValueError('Garment has no actual bone weights')
    if any(not rig.data.bones[n].use_deform for n in weighted):
        raise ValueError('Weighted bones have deformation disabled; confirm their semantics before proceeding')
    mapping = dict(config.get('mapping') or rules.arm_mapping(data))
    if config.get('auto_tpose', True):
        required = [k + '_' + s for s in ('L', 'R') for k in ('upper', 'lower', 'hand')]
        if any(not mapping.get(k) or mapping[k] not in available for k in required):
            raise ValueError('Bilateral upper-arm/forearm/wrist mappings are incomplete; complete them or disable automatic T pose')
        if len({mapping[k] for k in required}) != 6: raise ValueError('Arm mappings must be unique')
        for side in ('L', 'R'):
            a, b, c = [rig.data.bones[mapping[k + '_' + side]] for k in ('upper','lower','hand')]
            if a not in b.parent_recursive or b not in c.parent_recursive:
                raise ValueError('Arm mapping does not follow upper arm → forearm → wrist hierarchy')
    pins = set(config.get('pins', [])) | {n for n in mapping.values() if n}
    plan = rules.plan(data, weighted, pins, config.get('chains', []), config.get('excluded', []),
                      config.get('preserve_tips', True), config.get('confirmed_removals', []))
    users = [o.name for o in bpy.data.objects if o.type == 'MESH' and any(m.type == 'ARMATURE' and m.object == rig for m in o.modifiers)]
    return {'source': source.name, 'rig': rig.name, 'stamp': stamp(source), 'config': config,
            'mapping': mapping, 'plan': plan, 'bones_before': len(data), 'mesh_users': users,
            'status': 'SCANNED', 'warning': 'Copy only this garment; preserve required dependencies; do not migrate the physics runtime'}


def activate(obj):
    if bpy.context.mode != 'OBJECT': bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.select_all(action='DESELECT')
    obj.hide_set(False); obj.hide_viewport = False; obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def evaluate(obj):
    bpy.context.view_layer.update()
    ev = obj.evaluated_get(bpy.context.evaluated_depsgraph_get()); mesh = ev.to_mesh()
    try:
        value = np.array([ev.matrix_world @ v.co for v in mesh.vertices], dtype=float)
        if not len(value) or not np.all(np.isfinite(value)):
            raise ValueError('Evaluated mesh is empty or contains non-finite coordinates')
        return value
    finally: ev.to_mesh_clear()


def clone(source, collection, label):
    old = rig_of(source)
    rig = old.copy(); rig.data = old.data.copy(); rig.name = old.name + '.' + label
    collection.objects.link(rig)
    world = old.matrix_world.copy(); rig.parent = None; rig.matrix_world = world
    rig.hide_viewport = False; rig.hide_set(False); rig.hide_render = True
    for p in rig.pose.bones:
        for c in p.constraints:
            for target in [c, *list(getattr(c, 'targets', ()) )]:
                for attr in ('target', 'pole_target'):
                    if getattr(target, attr, None) == old: setattr(target, attr, rig)
    obj = source.copy(); obj.data = source.data.copy(); obj.name = source.name + '.' + label
    collection.objects.link(obj)
    world = source.matrix_world.copy(); obj.parent = rig; obj.matrix_world = world
    obj.hide_viewport = False; obj.hide_set(False); obj.hide_render = False
    obj.modifiers[0].object = rig
    return obj, rig


def discard(collection):
    if bpy.context.mode != 'OBJECT': bpy.ops.object.mode_set(mode='OBJECT')
    for obj in list(collection.objects):
        data = obj.data; kind = obj.type
        bpy.data.objects.remove(obj, do_unlink=True)
        if data and data.users == 0:
            if kind == 'MESH': bpy.data.meshes.remove(data)
            elif kind == 'ARMATURE': bpy.data.armatures.remove(data)
    bpy.data.collections.remove(collection)


def create_collection(name):
    c = bpy.data.collections.new(name); bpy.context.scene.collection.children.link(c); return c


def prepare(source, config, expected_stamp, directory):
    report = scan(source, config)
    if report['stamp'] != expected_stamp: raise ValueError('Source model or configuration changed; rescan')
    root = Path(bpy.path.abspath(directory))
    if not directory or (directory.startswith('//') and not bpy.data.filepath):
        raise ValueError('Save the project or specify an absolute output directory first')
    root.mkdir(parents=True, exist_ok=True)
    output = root / (datetime.now().strftime('%Y%m%d-%H%M%S') + '-' + uuid4().hex[:6]); output.mkdir()
    backup = output / 'before.blend'
    bpy.ops.wm.save_as_mainfile(filepath=str(backup), copy=True)
    if not backup.is_file(): raise RuntimeError('Backup failed; no changes started')
    collection = create_collection('MMD Preprocess Candidate')
    try:
        obj, rig = clone(source, collection, 'MMD_Candidate')
        initial = attributes(source)
        if attributes(obj) != initial: raise ValueError('Attribute mismatch after duplication')
        if np.max(np.linalg.norm(evaluate(source)-evaluate(obj),axis=1)) > 1e-6:
            raise ValueError('Evaluation mismatch after duplication')
        rotations = []
        if config.get('auto_tpose', True):
            # Source anatomical axes, not world-space X on an arbitrarily rotated object.
            for side, sign in [('L',1),('R',-1)]:
                for part in ('upper','lower','hand'):
                    n = report['mapping'][part+'_'+side]; bpy.context.view_layer.update(); p = rig.pose.bones[n]
                    if p.constraints: raise ValueError('Pose control bones have constraints; disable automatic posing and pose manually: '+n)
                    d = p.tail-p.head
                    if d.length < 1e-8: raise ValueError('Zero-length arm bone: '+n)
                    q = d.normalized().rotation_difference(Vector((sign,0,0)))
                    pivot = p.head.copy()
                    p.matrix = Matrix.Translation(pivot) @ q.to_matrix().to_4x4() @ Matrix.Translation(-pivot) @ p.matrix
                    rotations.append({'bone': n, 'degrees': math.degrees(q.angle)})
        bpy.context.view_layer.update()
        report.update(candidate=obj.name, candidate_rig=rig.name, candidate_collection=collection.name,
                      candidate_stamp=stamp(obj,False), directory=str(output), attributes=initial,
                      rotations=rotations, status='POSE_REVIEW')
        dump(output/'plan.json',report); dump(output/'source_weights.json',rows(source))
        obj['kkvrc_mmd_candidate_directory'] = str(output)
        activate(obj)
        return report
    except Exception:
        discard(collection); activate(source); raise


def motion_check(obj, reference, config, mapping):
    rig, other = rig_of(obj), rig_of(reference)
    names = list(dict.fromkeys([*mapping.values(), *config.get('chains', [])]))
    names += [p.mmd_bone.additional_transform_bone for p in rig.pose.bones
              if hasattr(p,'mmd_bone') and (p.mmd_bone.has_additional_rotation or p.mmd_bone.has_additional_location)]
    weighted = {n for row in rows(obj) for n,w in row.items() if w>0 and n in rig.data.bones}
    names += sorted(weighted)[:4]
    names = [n for n in dict.fromkeys(names) if n in rig.pose.bones and not rig.pose.bones[n].constraints][:24]
    states = [('rest', [])] + [(n, [(n,(0,1,0) if '捩' in n else (1,0,0),20)]) for n in names]
    if names: states.append(('mixed',[(n,(1,0,0),12) for n in names[:3]]))
    snapshots = {r.name:{p.name:p.matrix_basis.copy() for p in r.pose.bones} for r in (rig,other)}
    base = evaluate(obj); extent = max(float(np.linalg.norm(np.ptp(base,axis=0))),1e-3)
    results = []
    try:
        for label, edits in states:
            for r in (rig,other):
                for p in r.pose.bones: p.matrix_basis = snapshots[r.name][p.name]
                for n, axis, angle in edits:
                    r.pose.bones[n].matrix_basis = Quaternion(Vector(axis),math.radians(angle)).to_matrix().to_4x4()
            a,b = evaluate(obj),evaluate(reference)
            err = np.linalg.norm(a-b,axis=1); moved = np.linalg.norm(a-base,axis=1)
            results.append({'pose':label,'max_error':float(err.max()),'moved_vertices':int(np.sum(moved>extent*1e-7))})
            if err.max()>extent*2e-6: raise ValueError('Motion mismatch after cleanup: '+label)
        if len(results)>1 and not any(r['moved_vertices'] for r in results):
            raise ValueError('Motion validation produced no effective deformation')
    finally:
        for r in (rig,other):
            for p in r.pose.bones: p.matrix_basis = snapshots[r.name][p.name]
        bpy.context.view_layer.update()
    return results


def compensate_rebase_roundoff(obj, target_world, extent):
    """Invert only a tiny residual LBS transform after native rest-pose baking.

    IK can reevaluate to a slightly different solution even at identity basis.
    Never compensate a substantial rig change or unsupported B-Bone skinning.
    Validation still uses actual Blender evaluation, not this numerical model.
    """
    rig=rig_of(obj)
    before=evaluate(obj)
    residual=np.linalg.norm(before-target_world,axis=1)
    if residual.max()>extent*2e-5:
        raise ValueError('Rest-pose residual exceeds numerical compensation limits; specialized rig handling required')
    weights=rows(obj); transforms={}
    to_rig=rig.matrix_world.inverted() @ obj.matrix_world
    from_rig=to_rig.inverted()
    for row in weights:
        for name,w in row.items():
            if w<=0 or name not in rig.data.bones or name in transforms:continue
            bone=rig.data.bones[name]
            if bone.bbone_segments>1:
                raise ValueError('Rest-pose residual compensation does not support segmented B-Bone skinning')
            transforms[name]=np.array(from_rig @ rig.pose.bones[name].matrix @ bone.matrix_local.inverted() @ to_rig)
    inv_world=obj.matrix_world.inverted()
    old=[v.co.copy() for v in obj.data.vertices]
    try:
        for i in np.flatnonzero(residual>extent*1e-8):
            row={n:w for n,w in weights[i].items() if n in transforms and w>0}
            total=sum(row.values())
            if abs(total-1)>1e-5:raise ValueError('Residual compensation requires normalized effective bone weights')
            matrix=sum(transforms[n]*(w/total) for n,w in row.items())
            if np.linalg.cond(matrix[:3,:3])>1e6:raise ValueError('Residual skinning matrix cannot be inverted stably')
            target=np.array(inv_world @ Vector(target_world[i]))
            co=np.linalg.solve(matrix[:3,:3],target-matrix[:3,3])
            if not np.all(np.isfinite(co)):raise ValueError('Residual compensation produced non-finite coordinates')
            obj.data.vertices[int(i)].co=co.tolist()
        obj.data.update();after=evaluate(obj)
        correction=float(max((obj.matrix_world.to_3x3() @ (v.co-o)).length for v,o in zip(obj.data.vertices,old)))
        error=float(np.linalg.norm(after-target_world,axis=1).max())
        if correction>extent*3e-5 or error>extent*2e-6:
            raise ValueError('Rest-pose residual compensation failed actual evaluation validation')
        return {'before_max_error':float(residual.max()),'after_max_error':error,'max_rest_vertex_correction':correction}
    except Exception:
        for v,co in zip(obj.data.vertices,old):v.co=co
        obj.data.update()
        raise


def finalize(job):
    source = bpy.data.objects.get(job['source']); candidate = bpy.data.objects.get(job['candidate'])
    if not source or not candidate: raise ValueError('Source object or pose candidate no longer exists')
    if any(o.get('kkvrc_mmd_report') == str(Path(job['directory'])/'result.json') for o in bpy.data.objects):
        raise ValueError('This candidate already has a result; rest pose cannot be applied twice')
    if stamp(source) != job['stamp']: raise ValueError('Source data changed; rescan and generate a new candidate')
    fresh=scan(source,job['config'])
    if fresh['plan']!=job['plan'] or fresh['mapping']!=job['mapping']:
        raise ValueError('Saved cleanup plan no longer matches inputs; execution blocked')
    if stamp(candidate,False) != job['candidate_stamp']:
        raise ValueError('Candidate mesh, weights, or rig structure changed; only pose edits are allowed at this step')
    output = Path(job['directory']); collection = create_collection('MMD Preprocess Result')
    try:
        reference, ref_rig = clone(candidate,collection,'T_Reference')
        before = evaluate(reference); extent = max(float(np.linalg.norm(np.ptp(before,axis=0))),1e-3)
        dg = bpy.context.evaluated_depsgraph_get(); ev = reference.evaluated_get(dg)
        normals = np.array([list(n.vector) for n in ev.data.corner_normals])
        mesh = bpy.data.meshes.new_from_object(ev,preserve_all_data_layers=True,depsgraph=dg)
        activate(ref_rig); bpy.ops.object.mode_set(mode='POSE'); bpy.ops.pose.armature_apply(selected=False); bpy.ops.object.mode_set(mode='OBJECT')
        old = reference.data; reference.data = mesh
        if old.users == 0: bpy.data.meshes.remove(old)
        after = evaluate(reference); error = float(np.linalg.norm(after-before,axis=1).max())
        compensation=None
        if error > extent*2e-6:
            compensation=compensate_rebase_roundoff(reference,before,extent)
            error=compensation['after_max_error']
        if error > extent*2e-6: raise ValueError('Appearance changed after applying rest pose; candidate result reverted')
        if attributes(reference) != job['attributes']: raise ValueError('Rest-pose conversion changed mesh attributes')
        if any(np.max(np.abs(np.array(p.matrix_basis)-np.eye(4)))>1e-6 for p in ref_rig.pose.bones):
            raise ValueError('Nonzero pose basis remains after rest-pose conversion')
        ev2=reference.evaluated_get(bpy.context.evaluated_depsgraph_get())
        n2=np.array([list(n.vector) for n in ev2.data.corner_normals])
        normal_error=float(np.degrees(np.arccos(np.clip(np.sum(normals*n2,axis=1),-1,1))).max()) if len(normals) else 0.
        if not math.isfinite(normal_error) or normal_error > 1.:
            raise ValueError('Normals changed by more than 1° after rest-pose conversion; inspect shading')
        obj,rig=clone(reference,collection,'Clean')
        plan=job['plan']; activate(rig); bpy.ops.object.mode_set(mode='EDIT')
        for n in plan['remove']: rig.data.edit_bones.remove(rig.data.edit_bones[n])
        bpy.ops.object.mode_set(mode='OBJECT')
        # Retained references must resolve after deletion, including MMD grants.
        data=bones(rig)
        rules.plan(data,plan['weighted'])
        if set(rig.data.bones.keys()) != set(plan['keep']):
            raise ValueError('Bone set after cleanup differs from the preservation plan')
        assigned={g.group for v in obj.data.vertices for g in v.groups}
        remove_groups=[g.name for g in obj.vertex_groups if g.name in plan['remove'] and g.index not in assigned]
        for n in remove_groups: obj.vertex_groups.remove(obj.vertex_groups[n])
        if attributes(obj)!=job['attributes']: raise ValueError('Cleanup changed weights or mesh attributes')
        motions=motion_check(obj,reference,job['config'],job['mapping'])
        constraint_count=sum(len(p.constraints) for p in rig.pose.bones)
        result=dict(job,status='EDIT_READY',result=obj.name,result_rig=rig.name,reference=reference.name,
                    result_collection=collection.name,bones_after=len(rig.data.bones),
                    empty_groups_removed=remove_groups,rebase_max_error=error,
                    normal_max_angle=normal_error,motion_validation=motions,
                    rebase_roundoff_compensation=compensation,
                    constraints_remaining=constraint_count,optimizer_ready=constraint_count==0)
        if stamp(source)!=job['stamp']: raise ValueError('Source object changed unexpectedly')
        obj['kkvrc_mmd_preprocessed']=True;obj['kkvrc_mmd_reference']=reference.name
        obj['kkvrc_mmd_report']=str(output/'result.json')
        dump(output/'prepared_weights.json',rows(obj));dump(output/'prepared_bones.json',data)
        dump(output/'result.json',result)
        for o in (reference,ref_rig,candidate,rig): o.hide_set(True)
        reference.hide_render=True; candidate.hide_render=True
        activate(obj)
        return result
    except Exception:
        discard(collection); activate(candidate); raise


def save_result(job):
    """Call after UI state is updated so saved files resume at EDIT_READY."""
    if job.get('status')!='EDIT_READY' or not bpy.data.objects.get(job.get('result','')):
        raise ValueError('No validated result to save')
    path=Path(job['directory'])/'result.blend'
    bpy.ops.wm.save_as_mainfile(filepath=str(path),copy=True)
    if not path.is_file():raise RuntimeError('Failed to save the result copy; scene results remain available for another save attempt')
    return str(path)
