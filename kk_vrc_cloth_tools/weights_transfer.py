import bpy
from mathutils.kdtree import KDTree

from . import common


def get_mesh_armature(obj):
    for modifier in obj.modifiers:
        if modifier.type == "ARMATURE" and common.is_armature(modifier.object):
            return modifier.object
    return None


def get_source_body_mesh(context, props):
    source = props.transfer_source_body_mesh
    if common.is_mesh(source):
        return source

    active = context.view_layer.objects.active
    if common.is_mesh(active):
        return active

    raise RuntimeError("Assign Source body mesh, or make the KK body mesh the active object.")


def get_transfer_targets(context, source_body):
    selected = [obj for obj in context.selected_objects if common.is_mesh(obj) and obj != source_body]
    if selected:
        return selected
    raise RuntimeError("Select one or more fitted clothes meshes in addition to the source body mesh.")


def build_source_kdtree(source_body):
    mesh = source_body.data
    tree = KDTree(len(mesh.vertices))
    for vertex in mesh.vertices:
        tree.insert(source_body.matrix_world @ vertex.co, vertex.index)
    tree.balance()
    return tree


def collect_source_vertex_weights(source_body, kk_bone_names):
    group_names_by_index = {
        group.index: group.name
        for group in source_body.vertex_groups
        if group.name in kk_bone_names
    }
    weights = []
    for vertex in source_body.data.vertices:
        vertex_weights = {}
        for group_ref in vertex.groups:
            group_name = group_names_by_index.get(group_ref.group)
            if group_name and group_ref.weight > 0.0:
                vertex_weights[group_name] = group_ref.weight
        weights.append(vertex_weights)
    return weights


def get_physical_weight_total(obj, vertex, kk_bone_names):
    total = 0.0
    for group_ref in vertex.groups:
        group = obj.vertex_groups[group_ref.group]
        if group.name not in kk_bone_names and group_ref.weight > 0.0:
            total += group_ref.weight
    return total


def clear_body_weights(obj, vertex_index, kk_bone_names):
    for group in list(obj.vertex_groups):
        if group.name in kk_bone_names:
            common.remove_vertex_from_group(group, vertex_index)


def transfer_body_weights(
    source_body,
    target,
    kk_bone_names,
    source_tree,
    source_weights,
    do_apply,
    physical_threshold,
    replace_body_weights,
    normalize_affected,
    max_distance,
):
    affected_vertices = set()
    skipped_physical = 0
    skipped_distance = 0
    missing_source_weights = 0
    used_groups = set()

    for vertex in target.data.vertices:
        physical_total = get_physical_weight_total(target, vertex, kk_bone_names)
        if physical_total > physical_threshold:
            skipped_physical += 1
            continue

        world_position = target.matrix_world @ vertex.co
        _co, source_index, distance = source_tree.find(world_position)
        if max_distance > 0.0 and distance > max_distance:
            skipped_distance += 1
            continue

        weights = source_weights[source_index]
        if not weights:
            missing_source_weights += 1
            continue

        affected_vertices.add(vertex.index)
        used_groups.update(weights.keys())

        if not do_apply:
            continue

        if replace_body_weights:
            clear_body_weights(target, vertex.index, kk_bone_names)

        for group_name, weight in weights.items():
            common.set_weight(target, group_name, vertex.index, weight)

    if do_apply and normalize_affected:
        common.normalize_affected_vertices(target, affected_vertices)

    return {
        "mesh": target.name,
        "affected_vertices": len(affected_vertices),
        "used_groups": sorted(used_groups),
        "skipped_physical": skipped_physical,
        "skipped_distance": skipped_distance,
        "missing_source_weights": missing_source_weights,
    }


class KKVRC_OT_transfer_body_weights_to_fitted_clothes(bpy.types.Operator):
    bl_idname = "kkvrc.transfer_body_weights_to_fitted_clothes"
    bl_label = "Transfer KK Body Weights To Fitted Clothes"
    bl_description = "Transfer KK body weights from a source body mesh to selected fitted clothes vertices not controlled by physical bones"
    bl_options = {"REGISTER", "UNDO"}

    action: bpy.props.EnumProperty(
        items=(("PREVIEW", "Preview", ""), ("APPLY", "Apply", ""), ("REPORT", "Report", "")),
        default="PREVIEW",
        options={"HIDDEN"},
    )

    def execute(self, context):
        props = context.scene.kkvrc_cloth_tools
        try:
            source_body = get_source_body_mesh(context, props)
            kk_armature = get_mesh_armature(source_body) or common.get_active_kk_armature(context)
            kk_bone_names = common.get_armature_bone_names(kk_armature)
            targets = get_transfer_targets(context, source_body)
        except Exception as ex:
            self.report({"ERROR"}, str(ex))
            common.set_status(context, f"Body transfer failed: {ex}")
            return {"CANCELLED"}

        do_apply = self.action == "APPLY"
        source_tree = build_source_kdtree(source_body)
        source_weights = collect_source_vertex_weights(source_body, kk_bone_names)
        reports = [
            transfer_body_weights(
                source_body,
                target,
                kk_bone_names,
                source_tree,
                source_weights,
                do_apply,
                props.transfer_physical_threshold,
                props.transfer_replace_body_weights,
                props.transfer_normalize_affected_only,
                props.transfer_max_distance,
            )
            for target in targets
        ]

        title = "KK Body Weight Transfer Applied" if do_apply else "KK Body Weight Transfer Preview"
        if self.action == "REPORT":
            title = "KK Body Weight Transfer Report"

        common.print_report(
            title,
            reports,
            (
                ("used_groups", "Used KK body groups"),
                ("skipped_physical", "Skipped physical vertices"),
                ("skipped_distance", "Skipped by max distance"),
                ("missing_source_weights", "Nearest source vertices without weights"),
            ),
        )
        self.report({"INFO"}, f"{'Applied' if do_apply else 'Previewed'} body weight transfer for {len(targets)} mesh(es). See console.")
        common.set_status(context, f"Body transfer {'applied' if do_apply else 'preview'}: {len(targets)} mesh(es)")
        return {"FINISHED"}

