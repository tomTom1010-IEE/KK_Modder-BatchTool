import bpy
from mathutils.kdtree import KDTree

from . import common


VRC_HUMANOID_GROUPS = {
    "Hips",
    "Spine",
    "Chest",
    "Neck",
    "Head",
    "Shoulder.L",
    "Upper_arm.L",
    "Lower_arm.L",
    "Hand.L",
    "Shoulder.R",
    "Upper_arm.R",
    "Lower_arm.R",
    "Hand.R",
    "Upper_leg.L",
    "Lower_leg.L",
    "Foot.L",
    "Toe.L",
    "Upper_leg.R",
    "Lower_leg.R",
    "Foot.R",
    "Toe.R",
    "Thumb Proximal.L",
    "Thumb Intermediate.L",
    "Thumb Distal.L",
    "Index Proximal.L",
    "Index Intermediate.L",
    "Index Distal.L",
    "Middle Proximal.L",
    "Middle Intermediate.L",
    "Middle Distal.L",
    "Ring Proximal.L",
    "Ring Intermediate.L",
    "Ring Distal.L",
    "Little Proximal.L",
    "Little Intermediate.L",
    "Little Distal.L",
    "Thumb Proximal.R",
    "Thumb Intermediate.R",
    "Thumb Distal.R",
    "Index Proximal.R",
    "Index Intermediate.R",
    "Index Distal.R",
    "Middle Proximal.R",
    "Middle Intermediate.R",
    "Middle Distal.R",
    "Ring Proximal.R",
    "Ring Intermediate.R",
    "Ring Distal.R",
    "Little Proximal.R",
    "Little Intermediate.R",
    "Little Distal.R",
}


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


def collect_source_body_group_names(source_body, kk_bone_names):
    return {
        group.name
        for group in source_body.vertex_groups
        if group.name in kk_bone_names and common.group_has_weights(source_body, group.index)
    }


def is_replaceable_non_kk_group(group_name, treat_vrc_humanoid_as_body):
    if treat_vrc_humanoid_as_body and group_name in VRC_HUMANOID_GROUPS:
        return True
    return False


def get_dynamic_weight_total(obj, vertex, body_group_names, treat_vrc_humanoid_as_body):
    total = 0.0
    for group_ref in vertex.groups:
        group = obj.vertex_groups[group_ref.group]
        if group.name in body_group_names:
            continue
        if is_replaceable_non_kk_group(group.name, treat_vrc_humanoid_as_body):
            continue
        if group_ref.weight > 0.0:
            total += group_ref.weight
    return total


def get_physical_weight_total(obj, vertex, kk_bone_names, treat_vrc_humanoid_as_body):
    total = 0.0
    for group_ref in vertex.groups:
        group = obj.vertex_groups[group_ref.group]
        if group.name in kk_bone_names:
            continue
        if is_replaceable_non_kk_group(group.name, treat_vrc_humanoid_as_body):
            continue
        if group_ref.weight > 0.0:
            total += group_ref.weight
    return total


def clear_named_weights(obj, vertex_index, group_names):
    removed = []
    for group in list(obj.vertex_groups):
        if group.name not in group_names:
            continue
        if common.get_vertex_weight(obj.data.vertices[vertex_index], group.index) <= 0.0:
            continue
        common.remove_vertex_from_group(group, vertex_index)
        removed.append(group.name)
    return removed


def clear_body_weights(obj, vertex_index, kk_bone_names):
    for group in list(obj.vertex_groups):
        if group.name in kk_bone_names:
            common.remove_vertex_from_group(group, vertex_index)


def clear_replaceable_non_kk_weights(obj, vertex_index, kk_bone_names, treat_vrc_humanoid_as_body):
    removed = []
    for group in list(obj.vertex_groups):
        if group.name in kk_bone_names:
            continue
        if not is_replaceable_non_kk_group(group.name, treat_vrc_humanoid_as_body):
            continue

        common.remove_vertex_from_group(group, vertex_index)
        removed.append(group.name)
    return removed


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
    treat_vrc_humanoid_as_body,
    remove_replaced_non_kk_groups,
):
    affected_vertices = set()
    skipped_physical = 0
    skipped_distance = 0
    missing_source_weights = 0
    used_groups = set()
    removed_non_kk_groups = set()

    for vertex in target.data.vertices:
        physical_total = get_physical_weight_total(target, vertex, kk_bone_names, treat_vrc_humanoid_as_body)
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
            if remove_replaced_non_kk_groups:
                removed_non_kk_groups.update(
                    clear_replaceable_non_kk_weights(
                        target,
                        vertex.index,
                        kk_bone_names,
                        treat_vrc_humanoid_as_body,
                    )
                )

        for group_name, weight in weights.items():
            common.set_weight(target, group_name, vertex.index, weight)

    if do_apply and normalize_affected:
        common.normalize_affected_vertices(target, affected_vertices)

    if do_apply and remove_replaced_non_kk_groups and removed_non_kk_groups:
        common.remove_empty_groups(target, removed_non_kk_groups)

    return {
        "mesh": target.name,
        "affected_vertices": len(affected_vertices),
        "used_groups": sorted(used_groups),
        "removed_non_kk_groups": sorted(removed_non_kk_groups),
        "skipped_physical": skipped_physical,
        "skipped_distance": skipped_distance,
        "missing_source_weights": missing_source_weights,
    }


def cleanup_body_weights_from_dynamic_vertices(
    target,
    body_group_names,
    do_apply,
    dynamic_threshold,
    normalize_affected,
    treat_vrc_humanoid_as_body,
):
    affected_vertices = set()
    removed_body_groups = set()
    dynamic_vertices = 0

    for vertex in target.data.vertices:
        dynamic_total = get_dynamic_weight_total(
            target,
            vertex,
            body_group_names,
            treat_vrc_humanoid_as_body,
        )
        if dynamic_total <= dynamic_threshold:
            continue

        dynamic_vertices += 1
        removable_groups = []
        for group_ref in vertex.groups:
            group = target.vertex_groups[group_ref.group]
            if group.name in body_group_names and group_ref.weight > 0.0:
                removable_groups.append(group.name)

        if not removable_groups:
            continue

        affected_vertices.add(vertex.index)
        removed_body_groups.update(removable_groups)

        if do_apply:
            clear_named_weights(target, vertex.index, removable_groups)

    if do_apply and normalize_affected:
        common.normalize_affected_vertices(target, affected_vertices)

    if do_apply and removed_body_groups:
        common.remove_empty_groups(target, removed_body_groups)

    return {
        "mesh": target.name,
        "affected_vertices": len(affected_vertices),
        "dynamic_vertices": dynamic_vertices,
        "removed_body_groups": sorted(removed_body_groups),
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
                props.transfer_treat_vrc_humanoid_as_body,
                props.transfer_remove_replaced_non_kk_groups,
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
                ("removed_non_kk_groups", "Removed replaced non-KK groups"),
                ("skipped_physical", "Skipped physical vertices"),
                ("skipped_distance", "Skipped by max distance"),
                ("missing_source_weights", "Nearest source vertices without weights"),
            ),
        )
        self.report({"INFO"}, f"{'Applied' if do_apply else 'Previewed'} body weight transfer for {len(targets)} mesh(es). See console.")
        common.set_status(context, f"Body transfer {'applied' if do_apply else 'preview'}: {len(targets)} mesh(es)")
        return {"FINISHED"}


class KKVRC_OT_cleanup_dynamic_body_weights(bpy.types.Operator):
    bl_idname = "kkvrc.cleanup_dynamic_body_weights"
    bl_label = "Clean Body Weights From Dynamic Areas"
    bl_description = "Remove KK body standard weights from vertices controlled by clothing dynamic bones"
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
            body_group_names = collect_source_body_group_names(source_body, kk_bone_names)
            if not body_group_names:
                raise RuntimeError("Source body mesh has no weighted KK body groups to use as cleanup standard.")
            targets = get_transfer_targets(context, source_body)
        except Exception as ex:
            self.report({"ERROR"}, str(ex))
            common.set_status(context, f"Dynamic cleanup failed: {ex}")
            return {"CANCELLED"}

        do_apply = self.action == "APPLY"
        reports = [
            cleanup_body_weights_from_dynamic_vertices(
                target,
                body_group_names,
                do_apply,
                props.transfer_dynamic_cleanup_threshold,
                props.transfer_dynamic_cleanup_normalize,
                props.transfer_treat_vrc_humanoid_as_body,
            )
            for target in targets
        ]

        title = "Dynamic Area Body Weight Cleanup Applied" if do_apply else "Dynamic Area Body Weight Cleanup Preview"
        if self.action == "REPORT":
            title = "Dynamic Area Body Weight Cleanup Report"

        common.print_report(
            title,
            reports,
            (
                ("dynamic_vertices", "Vertices above dynamic threshold"),
                ("removed_body_groups", "Removed KK body groups"),
            ),
        )
        self.report({"INFO"}, f"{'Applied' if do_apply else 'Previewed'} dynamic area cleanup for {len(targets)} mesh(es). See console.")
        common.set_status(context, f"Dynamic cleanup {'applied' if do_apply else 'preview'}: {len(targets)} mesh(es)")
        return {"FINISHED"}
