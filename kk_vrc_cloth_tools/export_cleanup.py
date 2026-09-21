"""Export cleanup using the finite KK body-bone set and whole non-body subtrees."""
import json
from .ui_messages import format_message as _fmt
import bpy
from . import bone_cleanup, bone_rules


def discover_roots(armature):
    # A branch under a non-body bone belongs to that same indivisible chain.
    return sorted(b.name for b in armature.data.bones
                  if not bone_rules.is_kk_standard_body_bone(b.name)
                  and (b.parent is None or bone_rules.is_kk_standard_body_bone(b.parent.name)))


def selected_armature(context):
    objects = set(context.selected_objects)
    for obj in list(objects):
        objects.update(obj.children_recursive)
    rigs = {o for o in objects if o.type == 'ARMATURE'}
    for obj in objects:
        if obj.type == 'MESH':
            rigs.update(m.object for m in obj.modifiers if m.type == 'ARMATURE' and m.object)
            parent = obj.parent
            while parent:
                if parent.type == 'ARMATURE': rigs.add(parent)
                parent = parent.parent
    if len(rigs) != 1:
        raise ValueError('Select one export armature and its meshes, or a bound mesh; multiple armatures cannot be processed together')
    return rigs.pop()


def plan(armature, roots=None):
    if not armature or armature.type != 'ARMATURE':
        raise ValueError('Select an armature')
    if armature.mode == 'EDIT':
        raise ValueError('Leave Edit Mode before scanning')
    if roots is None:
        roots = discover_roots(armature)
    meshes = bone_cleanup.get_armature_meshes(armature)
    weighted = bone_cleanup.collect_weighted_bone_group_names(meshes, armature)
    bones = armature.data.bones
    protected = {}
    global_reasons = []
    # Animation/driver evaluation may refer to bones indirectly; do not guess.
    for owner in (armature, armature.data):
        if owner.animation_data:
            global_reasons.append('Armature has animation or driver data; manual inspection required')
    for obj in bpy.data.objects:
        if obj.parent == armature and obj.parent_type == 'BONE':
            protected[obj.parent_bone] = 'An object is parented to this bone'
        owners = [obj]
        if obj.type == 'ARMATURE':
            owners += list(obj.pose.bones)
        for owner in owners:
            for constraint in owner.constraints:
                if obj == armature and isinstance(owner, bpy.types.PoseBone):
                    protected[owner.name] = 'Bone has constraints'
                # Multi-target constraints and pole targets are included.
                targets = [constraint] + list(getattr(constraint, 'targets', ()))
                for target in targets:
                    for attr, sub in [('target', 'subtarget'), ('pole_target', 'pole_subtarget')]:
                        if getattr(target, attr, None) == armature:
                            name = getattr(target, sub, '')
                            if name:
                                protected[name] = 'Referenced by a constraint'
                            else:
                                global_reasons.append('A constraint references the armature without specifying a bone')
    # Driver targets can be on meshes, shape keys, materials, or other ID types.
    for prop in bpy.data.bl_rna.properties:
        if prop.type != 'COLLECTION':
            continue
        for owner in getattr(bpy.data, prop.identifier, ()):
            ad = getattr(owner, 'animation_data', None)
            if not ad:
                continue
            for fc in ad.drivers:
                for variable in fc.driver.variables:
                    for target in variable.targets:
                        if target.id in (armature, armature.data):
                            global_reasons.append('A driver references this armature')
    for mesh in meshes:
        for mod in mesh.modifiers:
            if mod.type == 'ARMATURE' and mod.object == armature and mod.use_bone_envelopes:
                global_reasons.append('A bound mesh uses bone envelopes')
    children = bone_cleanup.get_children_map(armature)
    parents = bone_cleanup.get_parent_map(armature)
    roots = bone_cleanup.filter_selected_root_bones(sorted(set(roots)), parents)
    rows = []
    for root in roots:
        if root not in bones:
            raise ValueError('Root bone does not exist: ' + root)
        chain = set(bone_cleanup.collect_subtree_names(children, root))
        reasons = set(global_reasons)
        if chain & weighted:
            reasons.add('Chain has actual weights (preserve the entire chain and tips)')
        if any(bone_rules.is_kk_standard_body_bone(n) for n in chain):
            reasons.add('Contains known body bones; automatic removal is prohibited')
        reasons.update(protected[n] for n in chain if n in protected)
        rows.append({'root': root, 'bones': sorted(chain), 'reason': '；'.join(sorted(reasons)), 'eligible': not reasons})
    return {'meshes': [m.name for m in meshes], 'rows': rows}


class KKVRC_ExportChain(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty()
    remove: bpy.props.BoolProperty(name='Remove this root chain', default=False)
    eligible: bpy.props.BoolProperty()
    reason: bpy.props.StringProperty()
    count: bpy.props.IntProperty()


class KKVRC_ExportCleanup(bpy.types.PropertyGroup):
    armature: bpy.props.PointerProperty(name='Export armature', type=bpy.types.Object, poll=lambda self, obj: obj.type == 'ARMATURE')
    roots: bpy.props.StringProperty(default='[]')
    rows: bpy.props.CollectionProperty(type=KKVRC_ExportChain)
    external_checked: bpy.props.BoolProperty(name='Selected chains have no external physics or export references', default=False)
    status: bpy.props.StringProperty(default='Select the export armature and meshes, or a bound mesh, then scan.')


class KKVRC_OT_export_cleanup(bpy.types.Operator):
    bl_idname = 'kkvrc.export_dynamic_cleanup'
    bl_label = 'Pre-export Dynamic Bone Cleanup'
    bl_options = {'REGISTER', 'UNDO'}
    action: bpy.props.EnumProperty(items=[('SCAN', 'Scan selected root chains', ''), ('REFRESH', 'Rescan', ''), ('APPLY', 'Remove checked root chains', '')])

    def execute(self, context):
        p = context.scene.kkvrc_export_cleanup
        try:
            if self.action == 'SCAN':
                arm = selected_armature(context)
                p.armature = arm
            else:
                arm = p.armature
                if not arm:
                    raise ValueError('Scan the export structure first')
            roots = discover_roots(arm)
            report = plan(arm, roots)
            if self.action == 'APPLY':
                chosen = {r.name for r in p.rows if r.remove and r.eligible}
                if not chosen:
                    raise ValueError('No eligible root chains checked for removal')
                safe = {r['root'] for r in report['rows'] if r['eligible']}
                if not chosen <= safe:
                    raise ValueError('Weights or dependencies changed; rescan')
                if arm.data.users != 1 or arm.library or arm.data.library:
                    raise ValueError('Clean up an independent, editable export armature copy')
                backup = arm.data.copy()
                backup.name = arm.data.name + '.BeforeExportCleanup'
                backup.use_fake_user = True
                removed = bone_cleanup.remove_bones_subtree(arm, sorted(chosen))
                p.rows.clear(); p.roots = '[]'; p.external_checked = False
                p.status = _fmt('Removed {v0} bones; armature data backup: {v1}', v0=len(removed), v1=backup.name)
            else:
                p.rows.clear(); p.external_checked = False
                p.roots = json.dumps(roots)
                for entry in report['rows']:
                    row = p.rows.add(); row.name = entry['root']
                    row.eligible = entry['eligible']; row.remove = entry['eligible']
                    row.reason = entry['reason'] or 'No weights or detected Blender dependencies'
                    row.count = len(entry['bones'])
                p.status = _fmt('Checked {v0} bound meshes (including hidden meshes), {v1} root chains eligible for removal.', v0=len(report['meshes']), v1=sum((r['eligible'] for r in report['rows'])))
            self.report({'INFO'}, p.status)
            return {'FINISHED'}
        except Exception as exc:
            p.status = str(exc); self.report({'ERROR'}, p.status)
            return {'CANCELLED'}


class KKVRC_PT_export_cleanup(bpy.types.Panel):
    bl_label = 'Pre-export Dynamic Bone Cleanup'
    bl_idname = 'KKVRC_PT_export_cleanup'
    bl_order = 1
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'mannual edit'
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        p = context.scene.kkvrc_export_cleanup
        layout = self.layout
        layout.label(text='Select the export armature and meshes, or select a bound mesh')
        layout.label(text='Always preserve listed KK body bones; remove non-body bones only as complete chains')
        layout.operator('kkvrc.export_dynamic_cleanup', text='Scan export structure automatically').action = 'SCAN'
        row = layout.row(); row.enabled = False; row.prop(p, 'armature')
        for item in p.rows:
            box = layout.box(); row = box.row(); row.enabled = item.eligible
            row.prop(item, 'remove', text=_fmt('{v0}（{v1} bones)', v0=item.name, v1=item.count))
            box.label(text=item.reason)
        if p.rows:
            layout.operator('kkvrc.export_dynamic_cleanup', text='Rescan weights and dependencies').action = 'REFRESH'
            row = layout.row(); row.enabled = any(x.remove and x.eligible for x in p.rows)
            row.operator('kkvrc.export_dynamic_cleanup', text='Remove checked chains (automatic backup)').action = 'APPLY'
        layout.label(text=p.status)


CLASSES = (KKVRC_ExportChain, KKVRC_ExportCleanup, KKVRC_OT_export_cleanup, KKVRC_PT_export_cleanup)
