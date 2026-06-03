from collections import deque

import bpy

from . import common
from . import weights_body
from . import weights_transfer


SUPPORT_GROUPS = {
    "Upper_arm_support.L",
    "Upper_arm_support.R",
    "Lower_arm_support.L",
    "Lower_arm_support.R",
}

REPLACEABLE_VRC_GROUPS = set(weights_transfer.VRC_HUMANOID_GROUPS) | SUPPORT_GROUPS | {"Butt.L", "Butt.R"}

VRC_TO_KK_HYBRID_GROUPS = dict(weights_body.VRC_TO_KK_BODY_GROUPS)
VRC_TO_KK_HYBRID_GROUPS.update(
    {
        "Hips": "cf_j_hips",
        "Spine": "cf_j_spine01",
        "Chest": "cf_j_spine03",
        "Butt.L": "cf_j_siri_L",
        "Butt.R": "cf_j_siri_R",
        "Upper_arm_support.L": "cf_s_arm01_L",
        "Upper_arm_support.R": "cf_s_arm01_R",
        "Lower_arm_support.L": "cf_s_forearm01_L",
        "Lower_arm_support.R": "cf_s_forearm01_R",
    }
)

LOWER_BODY_LIMB_PREFIXES = (
    "cf_j_thigh",
    "cf_j_leg",
    "cf_j_foot",
    "cf_j_toes",
    "cf_j_kokan",
    "cf_d_thigh",
    "cf_d_leg",
    "cf_d_knee",
    "cf_d_foot",
    "cf_d_toes",
    "cf_d_kokan",
    "cf_s_thigh",
    "cf_s_leg",
    "cf_s_knee",
    "cf_s_foot",
    "cf_s_toes",
    "cf_s_kokan",
)

SKIRT_FALLBACK_GROUPS = ("cf_j_hips", "cf_j_waist02", "cf_j_waist01")


def get_weight_total(obj, vertex, group_names):
    total = 0.0
    for group_ref in vertex.groups:
        group = obj.vertex_groups[group_ref.group]
        if group.name in group_names and group_ref.weight > 0.0:
            total += group_ref.weight
    return total


def get_dynamic_weight_total(obj, vertex, body_group_names):
    total = 0.0
    for group_ref in vertex.groups:
        group = obj.vertex_groups[group_ref.group]
        if group.name in body_group_names:
            continue
        if group.name in REPLACEABLE_VRC_GROUPS:
            continue
        if group_ref.weight > 0.0:
            total += group_ref.weight
    return total


def sample_source_weights(source_tree, transferred_weights, target, vertex, max_distance=0.0):
    world_position = target.matrix_world @ vertex.co
    distance = source_tree.find_nearest_distance(world_position)
    if max_distance > 0.0 and (distance is None or distance > max_distance):
        return None, distance
    return dict(transferred_weights[vertex.index]), distance


def body_distance_transfer_factor(distance, full_distance, zero_distance):
    if zero_distance <= 0.0 or zero_distance <= full_distance:
        return 1.0
    if distance is None:
        return 0.0
    if distance <= full_distance:
        return 1.0
    if distance >= zero_distance:
        return 0.0
    return 1.0 - ((distance - full_distance) / (zero_distance - full_distance))


def scale_weights_to_capacity(weights, capacity):
    weights = {name: weight for name, weight in weights.items() if weight > 0.0}
    total = sum(weights.values())
    if total <= 0.0 or capacity <= 0.0:
        return {}
    scale = capacity / total
    return {name: weight * scale for name, weight in weights.items()}


def is_lower_body_limb_group(group_name):
    return group_name.startswith(LOWER_BODY_LIMB_PREFIXES)


def remove_lower_body_limb_weights(weights):
    return {name: weight for name, weight in weights.items() if not is_lower_body_limb_group(name)}


def filter_skirt_body_weights(weights, kk_bone_names):
    filtered = remove_lower_body_limb_weights(weights)
    if filtered:
        return filtered

    fallback = [name for name in SKIRT_FALLBACK_GROUPS if name in kk_bone_names]
    if not fallback:
        return weights

    share = 1.0 / len(fallback)
    return {name: share for name in fallback}


def source_transfer_weights(sampled_source_weights):
    if sampled_source_weights is None:
        return {}
    return dict(sampled_source_weights)


def mapped_vrc_weights(target, vertex, kk_bone_names):
    mapped = {}
    skipped = []
    for group_ref in vertex.groups:
        group = target.vertex_groups[group_ref.group]
        if group.name not in REPLACEABLE_VRC_GROUPS or group_ref.weight <= 0.0:
            continue

        target_name = VRC_TO_KK_HYBRID_GROUPS.get(group.name)
        if not target_name:
            skipped.append(group.name)
            continue
        if target_name not in kk_bone_names:
            skipped.append(group.name)
            continue
        mapped[target_name] = mapped.get(target_name, 0.0) + group_ref.weight
    return mapped, skipped


def add_sd_weights_from_source(mapped, sampled_source_weights, sd_influence):
    if sampled_source_weights is None or sd_influence <= 0.0:
        return mapped

    result = dict(mapped)
    for group_name, weight in sampled_source_weights.items():
        if not (group_name.startswith("cf_s_") or group_name.startswith("cf_d_")):
            continue
        result[group_name] = result.get(group_name, 0.0) + weight * sd_influence
    return result


def blend_weight_dicts(a, b, a_factor):
    a_factor = max(0.0, min(1.0, a_factor))
    b_factor = 1.0 - a_factor
    names = set(a) | set(b)
    return {
        name: a.get(name, 0.0) * a_factor + b.get(name, 0.0) * b_factor
        for name in names
    }


def clear_existing_weights(target, vertex_index, body_group_names, remove_replaced_vrc_groups):
    removed = []
    vertex = target.data.vertices[vertex_index]
    for group in list(target.vertex_groups):
        if group.name not in body_group_names and not (remove_replaced_vrc_groups and group.name in REPLACEABLE_VRC_GROUPS):
            continue
        if common.get_vertex_weight(vertex, group.index) <= 0.0:
            continue
        common.remove_vertex_from_group(group, vertex_index)
        removed.append(group.name)
    return removed


def apply_result_weights(target, vertex_index, weights, body_group_names, remove_replaced_vrc_groups, dynamic_total):
    capacity = max(0.0, 1.0 - dynamic_total)
    final_weights = scale_weights_to_capacity(weights, capacity)
    if not final_weights:
        return []

    removed = clear_existing_weights(target, vertex_index, body_group_names, remove_replaced_vrc_groups)
    for group_name, weight in final_weights.items():
        common.set_weight(target, group_name, vertex_index, weight)
    return removed


def compute_dynamic_distances(target, dynamic_seed_indices, max_rings):
    if max_rings <= 0 or not dynamic_seed_indices:
        return {}

    adjacency = common.build_vertex_adjacency(target)
    distances = {index: 0 for index in dynamic_seed_indices}
    queue = deque(dynamic_seed_indices)

    while queue:
        index = queue.popleft()
        next_distance = distances[index] + 1
        if next_distance > max_rings:
            continue
        for neighbor in adjacency[index]:
            if neighbor in distances:
                continue
            distances[neighbor] = next_distance
            queue.append(neighbor)
    return distances


def compute_region_distances(target, seed_indices, max_rings):
    return compute_dynamic_distances(target, seed_indices, max_rings)


def conservative_transfer_factor(vertex_index, dynamic_distances, body_distances, transition_rings):
    dynamic_distance = dynamic_distances.get(vertex_index)
    body_distance = body_distances.get(vertex_index)

    if dynamic_distance is None:
        return 1.0
    if body_distance is None:
        return 0.0

    total = dynamic_distance + body_distance
    if total <= 0:
        return 0.0

    factor = dynamic_distance / total
    if dynamic_distance > transition_rings:
        return 1.0
    return max(0.0, min(1.0, factor))


def smooth_body_weights(target, affected_vertices, body_group_names, iterations):
    if iterations <= 0 or not affected_vertices:
        return 0
    return common.smooth_vertex_group_weights(
        target,
        affected_vertices,
        body_group_names,
        iterations=iterations,
        strength=0.35,
        expand_rings=0,
        normalize=False,
    )


def normalize_body_weights_preserve_dynamic(target, affected_vertices, body_group_names):
    for vertex_index in affected_vertices:
        vertex = target.data.vertices[vertex_index]
        dynamic_total = get_dynamic_weight_total(target, vertex, body_group_names)
        capacity = max(0.0, 1.0 - dynamic_total)

        current = {}
        for group_name in body_group_names:
            group = target.vertex_groups.get(group_name)
            if group is None:
                continue
            weight = common.get_vertex_weight(vertex, group.index)
            if weight > 0.0:
                current[group_name] = weight

        final_weights = scale_weights_to_capacity(current, capacity)
        for group_name in current:
            common.set_weight(target, group_name, vertex_index, final_weights.get(group_name, 0.0))


def collect_current_body_weights(target, vertex, body_group_names):
    weights = {}
    for group_ref in vertex.groups:
        group = target.vertex_groups[group_ref.group]
        if group.name in body_group_names and group_ref.weight > 0.0:
            weights[group.name] = group_ref.weight
    return weights


def remove_body_weights_from_vertex(target, vertex_index, body_group_names):
    removed = []
    vertex = target.data.vertices[vertex_index]
    for group_name in body_group_names:
        group = target.vertex_groups.get(group_name)
        if group is None:
            continue
        if common.get_vertex_weight(vertex, group.index) <= 0.0:
            continue
        common.remove_vertex_from_group(group, vertex_index)
        removed.append(group_name)
    return removed


def postprocess_manual_skirt_weights(
    target,
    body_group_names,
    do_apply,
    dynamic_threshold,
    ignore_leg_weights,
    normalize_affected,
    smooth_iterations,
):
    affected_vertices = set()
    used_groups = set()
    removed_groups = set()
    dynamic_protected_vertices = 0
    leg_filtered_vertices = 0
    emptied_vertices = 0

    for vertex in target.data.vertices:
        current_weights = collect_current_body_weights(target, vertex, body_group_names)
        if not current_weights:
            continue

        dynamic_total = get_dynamic_weight_total(target, vertex, body_group_names)
        protected = dynamic_total > dynamic_threshold
        if protected:
            dynamic_protected_vertices += 1

        result = dict(current_weights)
        if ignore_leg_weights:
            filtered = remove_lower_body_limb_weights(result)
            if len(filtered) != len(result):
                leg_filtered_vertices += 1
            result = filtered

        capacity = max(0.0, 1.0 - dynamic_total) if protected else sum(result.values())
        result = scale_weights_to_capacity(result, capacity)

        if result == current_weights:
            continue

        affected_vertices.add(vertex.index)
        used_groups.update(result.keys())
        removed_groups.update(name for name in current_weights if name not in result)

        if not result:
            emptied_vertices += 1

        if do_apply:
            remove_body_weights_from_vertex(target, vertex.index, current_weights.keys())
            for group_name, weight in result.items():
                common.set_weight(target, group_name, vertex.index, weight)

    if do_apply and smooth_iterations > 0 and affected_vertices:
        smooth_body_weights(target, affected_vertices, body_group_names, smooth_iterations)

    if do_apply and normalize_affected:
        normalize_body_weights_preserve_dynamic(target, affected_vertices, body_group_names)

    if do_apply and removed_groups:
        common.remove_empty_groups(target, removed_groups)

    return {
        "mesh": target.name,
        "affected_vertices": len(affected_vertices),
        "used_groups": sorted(used_groups),
        "removed_groups": sorted(removed_groups),
        "dynamic_protected_vertices": dynamic_protected_vertices,
        "leg_filtered_vertices": leg_filtered_vertices,
        "emptied_vertices": emptied_vertices,
    }


def get_manual_skirt_body_group_names(target, body_group_names, kk_bone_names, ignore_leg_weights):
    names = set(body_group_names)
    if ignore_leg_weights:
        names.update(
            group.name
            for group in target.vertex_groups
            if group.name in kk_bone_names and is_lower_body_limb_group(group.name)
        )
    return names


def make_transfer_candidate(sampled_source_weights):
    return source_transfer_weights(sampled_source_weights)


def make_map_candidate(target, vertex, kk_bone_names, sampled_source_weights, include_sd_bones, sd_influence):
    mapped, skipped = mapped_vrc_weights(target, vertex, kk_bone_names)
    if include_sd_bones:
        mapped = add_sd_weights_from_source(mapped, sampled_source_weights, sd_influence)
    return mapped, skipped


def auto_hybrid_weights(
    source_body,
    target,
    kk_bone_names,
    body_group_names,
    source_tree,
    transferred_weights,
    do_apply,
    mode,
    dynamic_threshold,
    remove_replaced_vrc_groups,
    normalize_affected,
    include_sd_bones,
    sd_influence,
    blend_width_rings,
    blend_smooth_iterations,
    max_distance,
    body_falloff_full_distance,
    body_falloff_zero_distance,
    skirt_safe_body_distance,
    skirt_safe_transition_rings,
    skirt_safe_ignore_leg_weights,
):
    dynamic_seed_indices = {
        vertex.index
        for vertex in target.data.vertices
        if get_dynamic_weight_total(target, vertex, body_group_names) > dynamic_threshold
    }
    dynamic_distances = compute_dynamic_distances(target, dynamic_seed_indices, blend_width_rings)
    conservative_body_indices = set()
    if mode == "SKIRT_SAFE":
        for vertex in target.data.vertices:
            if get_weight_total(target, vertex, REPLACEABLE_VRC_GROUPS) <= 0.0:
                continue
            dynamic_total = get_dynamic_weight_total(target, vertex, body_group_names)
            if dynamic_total > dynamic_threshold:
                continue
            _sampled_source_weights, distance = sample_source_weights(source_tree, transferred_weights, target, vertex)
            if skirt_safe_body_distance <= 0.0 or (distance is not None and distance <= skirt_safe_body_distance):
                conservative_body_indices.add(vertex.index)
        dynamic_distances = compute_dynamic_distances(target, dynamic_seed_indices, skirt_safe_transition_rings)
    body_distances = compute_region_distances(target, conservative_body_indices, skirt_safe_transition_rings) if mode == "SKIRT_SAFE" else {}

    affected_vertices = set()
    used_groups = set()
    removed_groups = set()
    skipped_dynamic = 0
    skipped_no_vrc_body = 0
    skipped_distance = 0
    missing_source_weights = 0
    skipped_mapping = set()
    transfer_vertices = 0
    mapped_vertices = 0
    blended_vertices = 0
    mapped_dynamic_vertices = 0
    distance_faded_vertices = 0

    for vertex in target.data.vertices:
        vrc_total = get_weight_total(target, vertex, REPLACEABLE_VRC_GROUPS)
        if vrc_total <= 0.0:
            skipped_no_vrc_body += 1
            continue

        dynamic_total = get_dynamic_weight_total(target, vertex, body_group_names)
        sample_max_distance = max_distance if mode == "TRANSFER" else 0.0
        sampled_source_weights, distance = sample_source_weights(
            source_tree,
            transferred_weights,
            target,
            vertex,
            sample_max_distance,
        )
        if sampled_source_weights is None:
            if mode == "TRANSFER":
                skipped_distance += 1
                continue
            sampled_source_weights = {}

        map_weights, skipped = make_map_candidate(
            target,
            vertex,
            kk_bone_names,
            sampled_source_weights,
            include_sd_bones,
            sd_influence,
        )
        skipped_mapping.update(skipped)

        if mode == "SKIRT_SAFE" and skirt_safe_ignore_leg_weights:
            map_weights = remove_lower_body_limb_weights(map_weights)

        if mode == "TRANSFER":
            if dynamic_total > dynamic_threshold:
                skipped_dynamic += 1
            transfer_weights = make_transfer_candidate(sampled_source_weights)
            if not transfer_weights:
                missing_source_weights += 1
                continue
            result = transfer_weights
            transfer_vertices += 1
        elif mode == "MAP":
            result = map_weights
            mapped_vertices += 1
        elif mode == "SKIRT_SAFE":
            transfer_weights = make_transfer_candidate(sampled_source_weights)
            if skirt_safe_ignore_leg_weights:
                transfer_weights = filter_skirt_body_weights(transfer_weights, kk_bone_names)
            if not transfer_weights:
                transfer_weights = {}
                missing_source_weights += 1

            if dynamic_total > dynamic_threshold:
                transfer_factor = 0.0
                mapped_dynamic_vertices += 1
            elif vertex.index in conservative_body_indices and vertex.index not in dynamic_distances:
                transfer_factor = 1.0
                transfer_vertices += 1
            elif vertex.index in dynamic_distances or vertex.index in body_distances:
                transfer_factor = conservative_transfer_factor(
                    vertex.index,
                    dynamic_distances,
                    body_distances,
                    skirt_safe_transition_rings,
                )
                blended_vertices += 1
            else:
                transfer_factor = 0.0
                mapped_vertices += 1

            result = blend_weight_dicts(transfer_weights, map_weights, transfer_factor)
        else:
            transfer_weights = make_transfer_candidate(sampled_source_weights)
            if not transfer_weights:
                transfer_weights = {}
                missing_source_weights += 1

            distance_from_dynamic = dynamic_distances.get(vertex.index)
            if dynamic_total > dynamic_threshold:
                dynamic_factor = 0.0
                mapped_dynamic_vertices += 1
            elif distance_from_dynamic is None:
                dynamic_factor = 1.0
            else:
                dynamic_factor = max(0.0, min(1.0, distance_from_dynamic / max(1, blend_width_rings)))
                blended_vertices += 1

            distance_factor = body_distance_transfer_factor(
                distance,
                body_falloff_full_distance,
                body_falloff_zero_distance,
            )
            if distance_factor < 1.0:
                distance_faded_vertices += 1

            transfer_factor = min(dynamic_factor, distance_factor)
            if transfer_factor >= 1.0:
                transfer_factor = 1.0
                transfer_vertices += 1
            elif transfer_factor <= 0.0:
                mapped_vertices += 1
            result = blend_weight_dicts(transfer_weights, map_weights, transfer_factor)

        if not result:
            continue

        affected_vertices.add(vertex.index)
        used_groups.update(result.keys())

        if do_apply:
            removed = apply_result_weights(
                target,
                vertex.index,
                result,
                body_group_names,
                remove_replaced_vrc_groups,
                dynamic_total,
            )
            removed_groups.update(removed)

    if do_apply and blend_smooth_iterations > 0 and mode == "BLEND":
        smooth_body_weights(target, affected_vertices, body_group_names, blend_smooth_iterations)

    if do_apply and normalize_affected:
        normalize_body_weights_preserve_dynamic(target, affected_vertices, body_group_names)

    if do_apply and removed_groups:
        common.remove_empty_groups(target, removed_groups)

    return {
        "mesh": target.name,
        "affected_vertices": len(affected_vertices),
        "used_groups": sorted(used_groups),
        "removed_groups": sorted(removed_groups),
        "skipped_dynamic": skipped_dynamic,
        "skipped_no_vrc_body": skipped_no_vrc_body,
        "skipped_distance": skipped_distance,
        "missing_source_weights": missing_source_weights,
        "skipped_mapping": sorted(skipped_mapping),
        "transfer_vertices": transfer_vertices,
        "mapped_vertices": mapped_vertices,
        "blended_vertices": blended_vertices,
        "mapped_dynamic_vertices": mapped_dynamic_vertices,
        "distance_faded_vertices": distance_faded_vertices,
    }


class KKVRC_OT_auto_hybrid_clothes_weights(bpy.types.Operator):
    bl_idname = "kkvrc.auto_hybrid_clothes_weights"
    bl_label = "Auto Hybrid Clothes Weights"
    bl_description = "Automatically mix KK body transfer and VRC body mapping while preserving clothing dynamic bones"
    bl_options = {"REGISTER", "UNDO"}

    action: bpy.props.EnumProperty(
        items=(("PREVIEW", "Preview", ""), ("APPLY", "Apply", ""), ("REPORT", "Report", "")),
        default="PREVIEW",
        options={"HIDDEN"},
    )

    def execute(self, context):
        props = context.scene.kkvrc_cloth_tools
        try:
            source_body = weights_transfer.get_source_body_mesh(context, props)
            kk_armature = weights_transfer.get_mesh_armature(source_body) or common.get_active_kk_armature(context)
            kk_bone_names = common.get_armature_bone_names(kk_armature)
            body_group_names = weights_transfer.collect_source_body_group_names(source_body, kk_bone_names)
            if not body_group_names:
                raise RuntimeError("Source body mesh has no weighted KK body groups.")
            targets = weights_transfer.get_transfer_targets(context, source_body)
        except Exception as ex:
            self.report({"ERROR"}, str(ex))
            common.set_status(context, f"Hybrid weights failed: {ex}")
            return {"CANCELLED"}

        do_apply = self.action == "APPLY"
        source_tree = weights_transfer.build_source_kdtree(source_body)

        reports = [
            auto_hybrid_weights(
                source_body,
                target,
                kk_bone_names,
                body_group_names,
                source_tree,
                weights_transfer.transfer_source_body_weights_to_target(source_body, target, body_group_names),
                do_apply,
                props.hybrid_weight_mode,
                props.hybrid_dynamic_threshold,
                props.hybrid_remove_replaced_vrc_groups,
                props.hybrid_normalize_affected_only,
                props.hybrid_include_sd_bones,
                props.hybrid_sd_influence,
                props.hybrid_blend_width_rings,
                props.hybrid_blend_smooth_iterations,
                props.hybrid_max_distance,
                props.hybrid_body_falloff_full_distance,
                props.hybrid_body_falloff_zero_distance,
                props.hybrid_skirt_safe_body_distance,
                props.hybrid_skirt_safe_transition_rings,
                props.hybrid_skirt_safe_ignore_leg_weights,
            )
            for target in targets
        ]

        title = "Auto Hybrid Clothes Weights Applied" if do_apply else "Auto Hybrid Clothes Weights Preview"
        if self.action == "REPORT":
            title = "Auto Hybrid Clothes Weights Report"

        common.print_report(
            title,
            reports,
            (
                ("used_groups", "Used KK body groups"),
                ("removed_groups", "Removed/replaced groups"),
                ("transfer_vertices", "Transfer vertices"),
                ("mapped_vertices", "Mapped vertices"),
                ("blended_vertices", "Blended vertices"),
                ("mapped_dynamic_vertices", "Mapped dynamic-overlap vertices"),
                ("distance_faded_vertices", "Body-distance faded vertices"),
                ("skipped_dynamic", "Dynamic-protected vertices"),
                ("skipped_no_vrc_body", "Skipped vertices without VRC body weights"),
                ("skipped_distance", "Skipped by max distance"),
                ("missing_source_weights", "Data Transfer vertices without weights"),
                ("skipped_mapping", "Skipped unmapped VRC groups"),
            ),
        )
        message = f"{'Applied' if do_apply else 'Previewed'} hybrid weights for {len(targets)} mesh(es)."
        self.report({"INFO"}, message + " See console.")
        common.set_status(context, message)
        return {"FINISHED"}


class KKVRC_OT_postprocess_manual_skirt_weights(bpy.types.Operator):
    bl_idname = "kkvrc.postprocess_manual_skirt_weights"
    bl_label = "Postprocess Manual Skirt Weights"
    bl_description = "After manual Blender Data Transfer, protect clothing dynamic bones and filter unsafe lower-body skirt weights"
    bl_options = {"REGISTER", "UNDO"}

    action: bpy.props.EnumProperty(
        items=(("PREVIEW", "Preview", ""), ("APPLY", "Apply", ""), ("REPORT", "Report", "")),
        default="PREVIEW",
        options={"HIDDEN"},
    )

    def execute(self, context):
        props = context.scene.kkvrc_cloth_tools
        try:
            source_body = weights_transfer.get_source_body_mesh(context, props)
            kk_armature = weights_transfer.get_mesh_armature(source_body) or common.get_active_kk_armature(context)
            kk_bone_names = common.get_armature_bone_names(kk_armature)
            body_group_names = weights_transfer.collect_source_body_group_names(source_body, kk_bone_names)
            if not body_group_names:
                raise RuntimeError("Source body mesh has no weighted KK body groups.")
            targets = weights_transfer.get_transfer_targets(context, source_body)
        except Exception as ex:
            self.report({"ERROR"}, str(ex))
            common.set_status(context, f"Manual skirt postprocess failed: {ex}")
            return {"CANCELLED"}

        do_apply = self.action == "APPLY"
        reports = [
            postprocess_manual_skirt_weights(
                target,
                get_manual_skirt_body_group_names(
                    target,
                    body_group_names,
                    kk_bone_names,
                    props.manual_skirt_ignore_leg_weights,
                ),
                do_apply,
                props.manual_skirt_dynamic_threshold,
                props.manual_skirt_ignore_leg_weights,
                props.manual_skirt_normalize_affected_only,
                props.manual_skirt_smooth_iterations,
            )
            for target in targets
        ]

        title = "Manual Skirt Weight Postprocess Applied" if do_apply else "Manual Skirt Weight Postprocess Preview"
        if self.action == "REPORT":
            title = "Manual Skirt Weight Postprocess Report"

        common.print_report(
            title,
            reports,
            (
                ("used_groups", "Remaining KK body groups"),
                ("removed_groups", "Removed/filtered body groups"),
                ("dynamic_protected_vertices", "Dynamic-protected vertices"),
                ("leg_filtered_vertices", "Leg/foot-filtered vertices"),
                ("emptied_vertices", "Vertices left to dynamic only"),
            ),
        )
        message = f"{'Applied' if do_apply else 'Previewed'} manual skirt postprocess for {len(targets)} mesh(es)."
        self.report({"INFO"}, message + " See console.")
        common.set_status(context, message)
        return {"FINISHED"}
