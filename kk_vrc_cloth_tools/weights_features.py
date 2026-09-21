"""Explicit Blender API for agent-driven feature-based weight migration.

Capture/prepare do not change scene weights. Snapshots/plans are JSON serializable.
Apply validates stale state and rolls weights back on failure; it never saves files.
"""
import bpy
from . import weight_features as core
from . import vrc_bone_rules


def read_weights(obj):
    if obj.type != 'MESH' or obj.mode != 'OBJECT':
        raise ValueError('An explicit mesh in Object mode is required')
    names = {g.index: g.name for g in obj.vertex_groups}
    return [{names[g.group]: g.weight for g in v.groups if g.group in names and g.weight > 0}
            for v in obj.data.vertices]


def topology(obj):
    return core.digest([len(obj.data.vertices), [list(e.vertices) for e in obj.data.edges],
                        [list(p.vertices) for p in obj.data.polygons]])


def body_weight_support(body_source, target):
    """Use actual positive body weights, never deform flags alone, as admission."""
    rigs = [m.object for m in target.modifiers if m.type == 'ARMATURE' and m.object]
    if len(rigs) != 1 or body_source is None or body_source == target:
        raise ValueError('Explicit separate target body and one destination rig required')
    body_rigs = [m.object for m in body_source.modifiers if m.type == 'ARMATURE' and m.object]
    if body_rigs and body_rigs != rigs:
        raise ValueError('Body and garment must use the same target rig')
    bones = {b.name for b in rigs[0].data.bones if b.use_deform}
    return {n for row in read_weights(body_source) for n,w in row.items() if w > 0 and n in bones}


def attach_body_support(proposal, body_source, target, retained_dynamic):
    allowed = body_weight_support(body_source, target)
    dynamic = set(retained_dynamic)
    used = {n for row in proposal['writes'].values() for n,w in row.items() if w > 0}
    if used - allowed - dynamic:
        raise ValueError('Body weights absent from target body: ' + str(sorted(used-allowed-dynamic)))
    proposal.update(body_support_source=body_source.name, body_support_stamp=stamp(body_source),
                    allowed_body_bones=sorted(allowed), retained_dynamic_bones=sorted(dynamic))


def prepare_supported_initial(target, body_source, target_regions, dynamic_groups, replacements):
    """Repair only illegal body contributions via reviewed within-region mappings.

    No geometric weight transfer, no global normalization, no dynamic edits.
    """
    allowed=body_weight_support(body_source,target);dynamic=set(dynamic_groups)
    before=read_weights(target);writes={};removed=set()
    for i,row in enumerate(before):
        out={}
        for name,w in row.items():
            dest=name
            if name not in allowed and name not in dynamic:
                dest=replacements.get(name)
                if dest not in allowed or name not in target_regions or target_regions.get(dest)!=target_regions[name]:
                    raise ValueError('Missing supported same-region replacement: '+name)
                removed.add(name)
            out[dest]=out.get(dest,0.)+w
        if out!=row:writes[i]=out
    proposal={'target':target.name,'expected_stamp':stamp(target),'topology':topology(target),
              'writes':writes,'managed_groups':sorted({n for row in before for n in row}|{n for row in writes.values() for n in row}),
              'snapshot_id':core.digest(before),'summary':{'repaired_vertices':len(writes),'removed_body_groups':sorted(removed)},'skipped':{}}
    attach_body_support(proposal,body_source,target,dynamic)
    proposal['plan_id']=core.digest(proposal)
    return proposal


def stamp(obj):
    return core.digest([topology(obj), read_weights(obj),
                        [(g.name, g.lock_weight) for g in obj.vertex_groups],
                        [list(v.co) for v in obj.data.vertices],
                        [list(row) for row in obj.matrix_world],
                        [(m.name, m.type, m.object.name if m.type == 'ARMATURE' and m.object else None)
                         for m in obj.modifiers],
                        [(m.show_viewport,m.use_deform_preserve_volume,m.use_bone_envelopes,
                          m.use_vertex_groups,m.vertex_group,m.object.data.pose_position,
                          [list(row) for row in m.object.matrix_world])
                         for m in obj.modifiers if m.type == 'ARMATURE' and m.object],
                        [(k.name, k.value) for k in obj.data.shape_keys.key_blocks] if obj.data.shape_keys else [],
                        [(m.object.name, [(b.name, b.use_deform, [list(r) for r in b.matrix_local]) for b in m.object.data.bones],
                          [(b.name, [list(r) for r in b.matrix]) for b in m.object.pose.bones])
                         for m in obj.modifiers if m.type == 'ARMATURE' and m.object]])


def capture_snapshot(obj, roles):
    """Roles BODY/DYNAMIC/IGNORE/DROP must be reviewed before capture.

    Use the intact original mesh if source group names no longer bind after graft.
    A missing bone is not automatically a mask or an unwanted helper.
    """
    rows = read_weights(obj)
    rigs = [m.object for m in obj.modifiers if m.type == 'ARMATURE' and m.object]
    for rig in rigs:
        bones = {b.name: {'parent': b.parent.name if b.parent else None,
                         'use_deform': b.use_deform} for b in rig.data.bones}
        audit = vrc_bone_rules.audit_vrc_weight_roles(rows, bones, roles)
        if audit['discarded_deform_bones']:
            raise ValueError('Weighted source body bones cannot be discarded: ' + str(audit['discarded_deform_bones']))
    return core.snapshot(rows, [list(e.vertices) for e in obj.data.edges], roles, topology(obj))


def prepare_plan(target, snapshot, body_map, dynamic_map, target_body_groups,
                 sampled_weights=None, sampling_confidence=None, indices=None,
                 source_regions=None, target_regions=None, min_region_sample=0.05,
                 finger_policy=None, protected_components=None, body_source=None, region_modes=None):
    if protected_components is not None:
        raise NotImplementedError('Protected intra-region components are reserved; implementation required')
    if topology(target) != snapshot['topology']:
        raise ValueError('Source/target vertex topology correspondence changed')
    if source_regions is not None or target_regions is not None:
        if source_regions is None or target_regions is None:
            raise ValueError('Both source and target regional maps are required')
        proposal = core.plan_regions(snapshot, body_map, dynamic_map, target_body_groups,
                                    source_regions, target_regions, sampled_weights,
                                    sampling_confidence, indices, min_region_sample, finger_policy, region_modes=region_modes)
    else:
        if finger_policy is not None:
            raise ValueError('Finger policy requires anatomical region maps')
        proposal = core.plan(snapshot, body_map, dynamic_map, target_body_groups,
                             sampled_weights, sampling_confidence, indices)
    proposal.update(target=target.name, expected_stamp=stamp(target), topology=topology(target))
    retained={n for mapping in dynamic_map.values() for n,w in mapping.items() if w>0}
    attach_body_support(proposal,body_source,target,retained)
    proposal['plan_id'] = core.digest(proposal)
    return proposal


def apply_plan(target, proposal):
    if proposal.get('plan_id') != core.digest({k: v for k, v in proposal.items() if k != 'plan_id'}):
        raise ValueError('Plan was modified; prepare a fresh preview')
    if target.name != proposal['target'] or stamp(target) != proposal['expected_stamp']:
        raise ValueError('Target changed since preview; prepare a fresh plan')
    if proposal.get('source_pose_contract') is not None:
        from .weights_optimization import source_pose_contract
        record=proposal['source_pose_contract'];source=bpy.data.objects.get(record['source'])
        if source is None or source_pose_contract(source)!=record['contract']:
            raise ValueError('Source constraint contract changed since optimization')
    if target.data.users != 1:
        raise ValueError('Shared mesh data: create an independent copy first')
    body=bpy.data.objects.get(proposal.get('body_support_source',''))
    if body is None or stamp(body)!=proposal.get('body_support_stamp'):
        raise ValueError('Missing/stale body support contract; prepare a fresh plan')
    allowed=body_weight_support(body,target)
    if allowed!=set(proposal['allowed_body_bones']):raise ValueError('Body support changed')
    used={n for row in proposal['writes'].values() for n,w in row.items() if w>0}
    if used & set(proposal.get('excluded_body_groups',())):raise ValueError('Excluded body influence in write plan')
    if used-allowed-set(proposal['retained_dynamic_bones']):raise ValueError('Unsupported body influence in write plan')
    for name, expected in proposal.get('context_sources', {}).items():
        obj = bpy.data.objects.get(name)
        if obj is None or stamp(obj) != expected:
            raise ValueError('Optimization source changed since preview: ' + name)
    if 'sampling_source' in proposal:
        source = bpy.data.objects.get(proposal['sampling_source'])
        if source is None or stamp(source) != proposal['sampling_stamp']:
            raise ValueError('Sampling source changed since preview')
    rigs = [m.object for m in target.modifiers if m.type == 'ARMATURE' and m.object]
    if len(rigs) != 1:
        raise ValueError('Exactly one target Armature modifier is required')
    modifier = next(m for m in target.modifiers if m.type == 'ARMATURE')
    if modifier.use_bone_envelopes or not modifier.use_vertex_groups or modifier.vertex_group:
        raise ValueError('Envelope or masked Armature deformation requires a separate policy')
    bones = {b.name for b in rigs[0].data.bones if b.use_deform}
    writes = {int(i): core.checked(w) for i, w in proposal['writes'].items()}
    output_groups = set().union(*(set(w) for w in writes.values()))
    if output_groups - bones:
        raise ValueError(f'Missing/non-deforming destination bones: {sorted(output_groups-bones)}')
    managed = set(proposal['managed_groups'])
    if output_groups - managed:
        raise ValueError('Write outside managed groups')
    if any(g.lock_weight for g in target.vertex_groups if g.name in managed):
        raise ValueError('Managed group is locked; choose an explicit preservation policy')
    before = read_weights(target)
    # Unreviewed target influences must not silently change the effective budget.
    ignored = set(g.name for g in target.vertex_groups) - managed
    if any(g in bones and w > 0 for i in writes for g, w in before[i].items() if g in ignored):
        raise ValueError('Unmanaged deforming weights exist on target vertices')
    old_names = set(target.vertex_groups.keys())
    def write_rows(rows):
        for i, weights in rows.items():
            for group in target.vertex_groups:
                if group.name in managed:
                    group.remove([i])
            for name, weight in weights.items():
                group = target.vertex_groups.get(name)
                if group is None:
                    group = target.vertex_groups.new(name=name)
                group.add([i], weight, 'REPLACE')
    try:
        write_rows(writes)
        after = read_weights(target)
        errors = []
        for i, weights in writes.items():
            if 'region_budgets' in proposal:
                budgets = proposal['region_budgets'].get(i, proposal['region_budgets'].get(str(i)))
                for region in core.BODY_REGIONS:
                    actual = sum(w for n,w in after[i].items()
                                 if proposal['target_regions'].get(n) == region)
                    if abs(actual-budgets[region]) > 1e-6:
                        errors.append(i)
            if any(abs(after[i].get(k, 0.)-weights.get(k, 0.)) > 1e-6 for k in managed):
                errors.append(i)
            if {k:v for k,v in before[i].items() if k not in managed} != {k:v for k,v in after[i].items() if k not in managed}:
                errors.append(i)
        if any(after[i] != before[i] for i in range(len(before)) if i not in writes) or errors:
            raise RuntimeError('Write verification failed')
    except Exception:
        write_rows({i: {k:v for k,v in before[i].items() if k in managed} for i in writes})
        for group in list(target.vertex_groups):
            if group.name not in old_names:
                target.vertex_groups.remove(group)
        raise
    return {'changed_vertices': len(writes), 'snapshot_id': proposal['snapshot_id'],
            'features': proposal['summary'], 'skipped': proposal['skipped'], 'verified': True}


def prepare_from_body(target, snapshot, body_source, body_map, dynamic_map,
                      target_body_groups, sampling_confidence, indices=None,
                      source_regions=None, target_regions=None, min_region_sample=0.05,
                      finger_policy=None, protected_components=None, region_modes=None, sampling_replacements=None):
    """Native nearest-face interpolation as a candidate, never as the final mass.

    Caller must establish rest-space anatomical correspondence and supply sampling
    confidence per vertex. Distance alone is not evidence of correct body region.
    """
    if protected_components is not None:
        raise NotImplementedError('Protected intra-region components are reserved; implementation required')
    from .weights_transfer import transfer_source_body_weights_to_target
    actual_support=body_weight_support(body_source,target)
    replacements=dict(sampling_replacements or {})
    target_body_groups=(set(target_body_groups)&actual_support)-set(replacements)
    stamp_before = stamp(target)
    sampled = transfer_source_body_weights_to_target(body_source, target, target_body_groups | (set(replacements)&actual_support))
    if replacements:sampled=core.redirect_body_samples(sampled,replacements,target_regions or {},target_body_groups)
    if stamp(target) != stamp_before:
        raise RuntimeError('Sampling unexpectedly changed target')
    proposal = prepare_plan(target, snapshot, body_map, dynamic_map, target_body_groups,
                            dict(enumerate(sampled)), sampling_confidence, indices,
                            source_regions, target_regions, min_region_sample, finger_policy,body_source=body_source,region_modes=region_modes)
    proposal.update(sampling_source=body_source.name, sampling_stamp=stamp(body_source))
    proposal['excluded_body_groups']=sorted(replacements)
    proposal['sampling_replacements']=replacements
    proposal['managed_groups']=sorted(set(proposal['managed_groups'])|set(replacements))
    if {n for row in proposal['writes'].values() for n,w in row.items() if w>0}&set(replacements):raise ValueError('Fallback mapping reintroduced excluded body bone')
    proposal['plan_id'] = core.digest({k:v for k,v in proposal.items() if k != 'plan_id'})
    return proposal
