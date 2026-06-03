import bpy
from mathutils.bvhtree import BVHTree
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

DATA_TRANSFER_MODIFIER_NAME = "__KKVRC_NATIVE_BODY_WEIGHT_SAMPLE__"
BNIP_GROUP_PREFIXES = ("cf_j_bnip", "cf_s_bnip", "cf_d_bnip")
BNIP_FALLBACK_GROUPS = (
    "cf_j_bust03_L",
    "cf_j_bust03_R",
    "cf_j_bust02_L",
    "cf_j_bust02_R",
    "cf_j_bust01_L",
    "cf_j_bust01_R",
    "cf_j_spine03",
)
LR_NAME_RULES = (
    (".L", ".R"),
    (".l", ".r"),
    ("_L", "_R"),
    ("_l", "_r"),
    ("-L", "-R"),
    ("-l", "-r"),
    (" Left", " Right"),
    (" left", " right"),
)


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


class SourceGeometrySampler:
    def __init__(self, source_body):
        mesh = source_body.data
        self.vertices_world = [source_body.matrix_world @ vertex.co for vertex in mesh.vertices]
        self.polygons = [tuple(poly.vertices) for poly in mesh.polygons if len(poly.vertices) >= 3]
        self.bvh = BVHTree.FromPolygons(self.vertices_world, self.polygons, all_triangles=False) if self.polygons else None

        self.vertex_tree = KDTree(len(self.vertices_world)) if self.vertices_world else None
        if self.vertex_tree:
            for index, co in enumerate(self.vertices_world):
                self.vertex_tree.insert(co, index)
            self.vertex_tree.balance()

    def find_nearest_distance(self, world_position):
        if self.bvh:
            _co, _normal, _poly_index, distance = self.bvh.find_nearest(world_position)
            if distance is not None:
                return distance

        if self.vertex_tree:
            _co, _index, distance = self.vertex_tree.find(world_position)
            return distance

        return None

    def sample_weights(self, source_weights, world_position, max_distance=0.0):
        if self.bvh:
            nearest_co, _normal, poly_index, distance = self.bvh.find_nearest(world_position)
            if nearest_co is not None and poly_index is not None:
                if max_distance > 0.0 and distance > max_distance:
                    return None, distance
                return self._interpolate_polygon_weights(source_weights, nearest_co, poly_index), distance

        return self._sample_nearest_vertex_weights(source_weights, world_position, max_distance)

    def _sample_nearest_vertex_weights(self, source_weights, world_position, max_distance):
        if not self.vertex_tree:
            return None, None

        _co, source_index, distance = self.vertex_tree.find(world_position)
        if max_distance > 0.0 and distance > max_distance:
            return None, distance
        return dict(source_weights[source_index]), distance

    def _interpolate_polygon_weights(self, source_weights, nearest_co, poly_index):
        vertex_indices = self.polygons[poly_index]
        weighted_indices = []
        total_factor = 0.0
        epsilon = 0.000001

        for vertex_index in vertex_indices:
            distance = (self.vertices_world[vertex_index] - nearest_co).length
            if distance <= epsilon:
                return dict(source_weights[vertex_index])

            factor = 1.0 / distance
            weighted_indices.append((vertex_index, factor))
            total_factor += factor

        if total_factor <= 0.0:
            return {}

        result = {}
        for vertex_index, factor in weighted_indices:
            ratio = factor / total_factor
            for group_name, weight in source_weights[vertex_index].items():
                result[group_name] = result.get(group_name, 0.0) + weight * ratio
        return result


def build_source_kdtree(source_body):
    return SourceGeometrySampler(source_body)


def try_set_modifier_property(modifier, name, value):
    try:
        setattr(modifier, name, value)
        return True
    except Exception:
        return False


def read_vertex_weights(obj, group_names):
    group_names_by_index = {
        group.index: group.name
        for group in obj.vertex_groups
        if group.name in group_names
    }
    weights = []
    for vertex in obj.data.vertices:
        vertex_weights = {}
        for group_ref in vertex.groups:
            group_name = group_names_by_index.get(group_ref.group)
            if group_name and group_ref.weight > 0.0:
                vertex_weights[group_name] = group_ref.weight
        weights.append(vertex_weights)
    return weights


def scale_body_weights_to_capacity(weights, capacity):
    weights = {name: weight for name, weight in weights.items() if weight > 0.0}
    total = sum(weights.values())
    if total <= 0.0 or capacity <= 0.0:
        return {}
    scale = capacity / total
    return {name: weight * scale for name, weight in weights.items()}


def transfer_source_body_weights_to_target(source_body, target, body_group_names):
    body_group_names = sorted(body_group_names)
    if not body_group_names:
        return [{} for _vertex in target.data.vertices]

    context = bpy.context
    previous_active = context.view_layer.objects.active
    previous_selected = list(context.selected_objects)
    previous_mode = previous_active.mode if previous_active is not None else "OBJECT"

    temp_mesh = target.data.copy()
    temp_obj = bpy.data.objects.new(f"{target.name}_kkvrc_transfer_sample", temp_mesh)
    temp_obj.matrix_world = target.matrix_world.copy()
    context.collection.objects.link(temp_obj)

    try:
        for group_name in body_group_names:
            if temp_obj.vertex_groups.get(group_name) is None:
                temp_obj.vertex_groups.new(name=group_name)

        if context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")

        bpy.ops.object.select_all(action="DESELECT")
        temp_obj.select_set(True)
        context.view_layer.objects.active = temp_obj

        modifier = temp_obj.modifiers.new(DATA_TRANSFER_MODIFIER_NAME, "DATA_TRANSFER")
        modifier.object = source_body
        try_set_modifier_property(modifier, "use_vert_data", True)
        try_set_modifier_property(modifier, "data_types_verts", {"VGROUP_WEIGHTS"})
        try_set_modifier_property(modifier, "vert_mapping", "POLYINTERP_NEAREST")
        try_set_modifier_property(modifier, "use_object_transform", True)
        try_set_modifier_property(modifier, "layers_vgroup_select_src", "ALL")
        try_set_modifier_property(modifier, "layers_vgroup_select_dst", "NAME")
        try_set_modifier_property(modifier, "mix_mode", "REPLACE")
        try_set_modifier_property(modifier, "mix_factor", 1.0)
        try_set_modifier_property(modifier, "use_create", True)

        bpy.ops.object.modifier_apply(modifier=modifier.name)
        return read_vertex_weights(temp_obj, body_group_names)
    finally:
        bpy.data.objects.remove(temp_obj, do_unlink=True)
        if temp_mesh.users == 0:
            bpy.data.meshes.remove(temp_mesh)

        bpy.ops.object.select_all(action="DESELECT")
        for obj in previous_selected:
            if obj.name in bpy.data.objects:
                obj.select_set(True)
        if previous_active is not None and previous_active.name in bpy.data.objects:
            context.view_layer.objects.active = previous_active
            if previous_mode != "OBJECT":
                try:
                    bpy.ops.object.mode_set(mode=previous_mode)
                except Exception:
                    pass


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
    do_apply,
    physical_threshold,
    replace_body_weights,
    normalize_affected,
    max_distance,
    treat_vrc_humanoid_as_body,
    remove_replaced_non_kk_groups,
):
    affected_vertices = set()
    protected_physical = 0
    skipped_distance = 0
    missing_source_weights = 0
    used_groups = set()
    removed_non_kk_groups = set()
    body_group_names = collect_source_body_group_names(source_body, kk_bone_names)
    transferred_weights = transfer_source_body_weights_to_target(source_body, target, body_group_names)

    for vertex in target.data.vertices:
        physical_total = get_physical_weight_total(target, vertex, kk_bone_names, treat_vrc_humanoid_as_body)
        if physical_total > physical_threshold:
            protected_physical += 1

        world_position = target.matrix_world @ vertex.co
        distance = source_tree.find_nearest_distance(world_position)
        if max_distance > 0.0 and (distance is None or distance > max_distance):
            skipped_distance += 1
            continue

        weights = transferred_weights[vertex.index]
        if not weights:
            missing_source_weights += 1
            continue

        capacity = max(0.0, 1.0 - physical_total) if physical_total > physical_threshold else 1.0
        weights = scale_body_weights_to_capacity(weights, capacity)
        if not weights:
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
        "protected_physical": protected_physical,
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


def vertex_group_max_weight(obj, group_index):
    max_weight = 0.0
    for vertex in obj.data.vertices:
        weight = common.get_vertex_weight(vertex, group_index)
        if weight > max_weight:
            max_weight = weight
    return max_weight


def remove_empty_vertex_groups(target, do_apply, threshold):
    removed_groups = []
    kept_groups = 0

    for group in list(target.vertex_groups):
        max_weight = vertex_group_max_weight(target, group.index)
        if max_weight > threshold:
            kept_groups += 1
            continue

        removed_groups.append(group.name)
        if do_apply:
            target.vertex_groups.remove(group)

    return {
        "mesh": target.name,
        "removed_groups": removed_groups,
        "kept_groups": kept_groups,
    }


def get_lr_counterpart_name(name):
    for left, right in LR_NAME_RULES:
        if name.endswith(left):
            return name[: -len(left)] + right
        if name.endswith(right):
            return name[: -len(right)] + left
    return None


def is_left_side_name(name):
    for left, _right in LR_NAME_RULES:
        if name.endswith(left):
            return True
    return False


def collect_lr_vertex_group_pairs(target):
    pairs = []
    seen = set()
    names = {group.name for group in target.vertex_groups}

    for name in sorted(names):
        if name in seen:
            continue

        counterpart = get_lr_counterpart_name(name)
        if counterpart is None:
            continue

        left_name = name if is_left_side_name(name) else counterpart
        right_name = counterpart if is_left_side_name(name) else name
        key = tuple(sorted((left_name, right_name)))
        if key in seen:
            continue

        if left_name in names or right_name in names:
            pairs.append((left_name, right_name))
            seen.add(key)
            seen.add(left_name)
            seen.add(right_name)

    return pairs


def swap_lr_vertex_group_weights(target, do_apply, remove_empty_groups_after):
    pairs = collect_lr_vertex_group_pairs(target)
    affected_vertices = set()
    created_groups = set()
    removed_groups = set()

    for left_name, right_name in pairs:
        left_group = target.vertex_groups.get(left_name)
        right_group = target.vertex_groups.get(right_name)

        vertex_swaps = []
        for vertex in target.data.vertices:
            left_weight = common.get_vertex_weight(vertex, left_group.index) if left_group else 0.0
            right_weight = common.get_vertex_weight(vertex, right_group.index) if right_group else 0.0
            if left_weight > 0.0 or right_weight > 0.0:
                vertex_swaps.append((vertex.index, left_weight, right_weight))
                affected_vertices.add(vertex.index)

        if not do_apply or not vertex_swaps:
            continue

        if left_group is None and any(right_weight > 0.0 for _index, _left_weight, right_weight in vertex_swaps):
            left_group = common.get_or_create_group(target, left_name)
            created_groups.add(left_name)
        if right_group is None and any(left_weight > 0.0 for _index, left_weight, _right_weight in vertex_swaps):
            right_group = common.get_or_create_group(target, right_name)
            created_groups.add(right_name)

        for vertex_index, left_weight, right_weight in vertex_swaps:
            if left_group is not None:
                common.set_weight(target, left_name, vertex_index, right_weight)
            if right_group is not None:
                common.set_weight(target, right_name, vertex_index, left_weight)

    if do_apply and remove_empty_groups_after:
        all_pair_names = {name for pair in pairs for name in pair}
        before = set(group.name for group in target.vertex_groups)
        common.remove_empty_groups(target, all_pair_names)
        after = set(group.name for group in target.vertex_groups)
        removed_groups = before.difference(after).intersection(all_pair_names)

    return {
        "mesh": target.name,
        "affected_vertices": len(affected_vertices),
        "pairs": [f"{left} <-> {right}" for left, right in pairs],
        "created_groups": sorted(created_groups),
        "removed_groups": sorted(removed_groups),
    }


def is_bnip_group_name(name):
    return name.startswith(BNIP_GROUP_PREFIXES)


def choose_bnip_fallback_group(target, side):
    side_suffix = f"_{side}" if side in {"L", "R"} else ""
    side_candidates = [name for name in BNIP_FALLBACK_GROUPS if side_suffix and name.endswith(side_suffix)]
    candidates = side_candidates + [name for name in BNIP_FALLBACK_GROUPS if not name.endswith(("_L", "_R"))]
    candidates += [name for name in BNIP_FALLBACK_GROUPS if name not in candidates]

    for name in candidates:
        group = target.vertex_groups.get(name)
        if group is not None:
            return group

    return common.get_or_create_group(target, "cf_j_spine03")


def get_bnip_side(group_name):
    if group_name.endswith("_L"):
        return "L"
    if group_name.endswith("_R"):
        return "R"
    return ""


def remove_bnip_weights(target, do_apply, merge_to_bust, normalize_affected):
    bnip_groups = [group for group in list(target.vertex_groups) if is_bnip_group_name(group.name)]
    affected_vertices = set()
    removed_groups = set()
    fallback_groups = set()
    moved_weight_total = 0.0

    for vertex in target.data.vertices:
        vertex_moves = []
        for group in bnip_groups:
            weight = common.get_vertex_weight(vertex, group.index)
            if weight > 0.0:
                vertex_moves.append((group, weight))

        if not vertex_moves:
            continue

        affected_vertices.add(vertex.index)
        for group, weight in vertex_moves:
            removed_groups.add(group.name)
            moved_weight_total += weight

            if not do_apply:
                continue

            common.remove_vertex_from_group(group, vertex.index)
            if merge_to_bust:
                fallback_group = choose_bnip_fallback_group(target, get_bnip_side(group.name))
                fallback_groups.add(fallback_group.name)
                old_weight = common.get_vertex_weight(vertex, fallback_group.index)
                fallback_group.add([vertex.index], old_weight + weight, "REPLACE")

    if do_apply and normalize_affected:
        common.normalize_affected_vertices(target, affected_vertices)

    if do_apply and removed_groups:
        common.remove_empty_groups(target, removed_groups)

    return {
        "mesh": target.name,
        "affected_vertices": len(affected_vertices),
        "removed_groups": sorted(removed_groups),
        "fallback_groups": sorted(fallback_groups),
        "moved_weight_total": round(moved_weight_total, 4),
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
        reports = [
            transfer_body_weights(
                source_body,
                target,
                kk_bone_names,
                source_tree,
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
                ("protected_physical", "Dynamic-protected vertices"),
                ("skipped_distance", "Skipped by max distance"),
                ("missing_source_weights", "Data Transfer vertices without weights"),
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


class KKVRC_OT_remove_empty_vertex_groups(bpy.types.Operator):
    bl_idname = "kkvrc.remove_empty_vertex_groups"
    bl_label = "Remove Empty Vertex Groups"
    bl_description = "Remove selected mesh vertex groups whose weights are all at or below the threshold"
    bl_options = {"REGISTER", "UNDO"}

    action: bpy.props.EnumProperty(
        items=(("PREVIEW", "Preview", ""), ("APPLY", "Apply", ""), ("REPORT", "Report", "")),
        default="PREVIEW",
        options={"HIDDEN"},
    )

    def execute(self, context):
        props = context.scene.kkvrc_cloth_tools
        targets = [obj for obj in context.selected_objects if common.is_mesh(obj)]
        if not targets:
            self.report({"ERROR"}, "Select one or more mesh objects.")
            common.set_status(context, "Remove empty groups failed: no selected meshes")
            return {"CANCELLED"}

        do_apply = self.action == "APPLY"
        reports = [
            remove_empty_vertex_groups(
                target,
                do_apply,
                props.cleanup_empty_group_threshold,
            )
            for target in targets
        ]

        title = "Empty Vertex Groups Removed" if do_apply else "Empty Vertex Groups Preview"
        if self.action == "REPORT":
            title = "Empty Vertex Groups Report"

        common.print_report(
            title,
            reports,
            (
                ("removed_groups", "Removed groups"),
                ("kept_groups", "Kept groups"),
            ),
        )
        message = f"{'Removed' if do_apply else 'Previewed'} empty vertex groups for {len(targets)} mesh(es)."
        self.report({"INFO"}, message + " See console.")
        common.set_status(context, message)
        return {"FINISHED"}


class KKVRC_OT_swap_lr_vertex_group_weights(bpy.types.Operator):
    bl_idname = "kkvrc.swap_lr_vertex_group_weights"
    bl_label = "Swap L/R Vertex Group Weights"
    bl_description = "Swap weights between paired left and right vertex groups such as .L/.R and _L/_R"
    bl_options = {"REGISTER", "UNDO"}

    action: bpy.props.EnumProperty(
        items=(("PREVIEW", "Preview", ""), ("APPLY", "Apply", ""), ("REPORT", "Report", "")),
        default="PREVIEW",
        options={"HIDDEN"},
    )

    def execute(self, context):
        props = context.scene.kkvrc_cloth_tools
        targets = [obj for obj in context.selected_objects if common.is_mesh(obj)]
        if not targets:
            self.report({"ERROR"}, "Select one or more mesh objects.")
            common.set_status(context, "Swap L/R weights failed: no selected meshes")
            return {"CANCELLED"}

        do_apply = self.action == "APPLY"
        reports = [
            swap_lr_vertex_group_weights(
                target,
                do_apply,
                props.cleanup_mirror_weights_remove_empty,
            )
            for target in targets
        ]

        title = "L/R Vertex Group Weights Swapped" if do_apply else "L/R Vertex Group Weight Swap Preview"
        if self.action == "REPORT":
            title = "L/R Vertex Group Weight Swap Report"

        common.print_report(
            title,
            reports,
            (
                ("pairs", "Swapped pairs"),
                ("created_groups", "Created groups"),
                ("removed_groups", "Removed empty groups"),
            ),
        )
        message = f"{'Swapped' if do_apply else 'Previewed'} L/R vertex group weights for {len(targets)} mesh(es)."
        self.report({"INFO"}, message + " See console.")
        common.set_status(context, message)
        return {"FINISHED"}


class KKVRC_OT_remove_bnip_weights(bpy.types.Operator):
    bl_idname = "kkvrc.remove_bnip_weights"
    bl_label = "Remove Nipple Detail Weights"
    bl_description = "Remove cf_*_bnip nipple-detail weights that often create bumps on transferred upper clothes"
    bl_options = {"REGISTER", "UNDO"}

    action: bpy.props.EnumProperty(
        items=(("PREVIEW", "Preview", ""), ("APPLY", "Apply", ""), ("REPORT", "Report", "")),
        default="PREVIEW",
        options={"HIDDEN"},
    )

    def execute(self, context):
        props = context.scene.kkvrc_cloth_tools
        targets = [obj for obj in context.selected_objects if common.is_mesh(obj)]
        if not targets:
            self.report({"ERROR"}, "Select one or more mesh objects.")
            common.set_status(context, "Remove nipple weights failed: no selected meshes")
            return {"CANCELLED"}

        do_apply = self.action == "APPLY"
        reports = [
            remove_bnip_weights(
                target,
                do_apply,
                props.cleanup_bnip_merge_to_bust,
                props.cleanup_bnip_normalize_affected,
            )
            for target in targets
        ]

        title = "Nipple Detail Weights Removed" if do_apply else "Nipple Detail Weights Preview"
        if self.action == "REPORT":
            title = "Nipple Detail Weights Report"

        common.print_report(
            title,
            reports,
            (
                ("removed_groups", "Removed bnip groups"),
                ("fallback_groups", "Merged fallback groups"),
                ("moved_weight_total", "Total bnip weight"),
            ),
        )
        message = f"{'Removed' if do_apply else 'Previewed'} nipple detail weights for {len(targets)} mesh(es)."
        self.report({"INFO"}, message + " See console.")
        common.set_status(context, message)
        return {"FINISHED"}
