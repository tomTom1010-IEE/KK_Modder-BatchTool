import bpy

from . import common


SIMPLE_J_CHAIN = {
    "Breast_root.L": (("cf_j_bust01_L", 1.0),),
    "Breast_1.L": (("cf_j_bust02_L", 1.0),),
    "Breast_2.L": (("cf_j_bust03_L", 1.0),),
    "Breast_root.R": (("cf_j_bust01_R", 1.0),),
    "Breast_1.R": (("cf_j_bust02_R", 1.0),),
    "Breast_2.R": (("cf_j_bust03_R", 1.0),),
}

DISTRIBUTED_J_CHAIN = {
    "Breast_root.L": (("cf_j_bust01_L", 0.7), ("cf_d_bust00", 0.3)),
    "Breast_1.L": (("cf_j_bust02_L", 0.6), ("cf_j_bust01_L", 0.4)),
    "Breast_2.L": (("cf_j_bust03_L", 0.7), ("cf_j_bust02_L", 0.3)),
    "Breast_root.R": (("cf_j_bust01_R", 0.7), ("cf_d_bust00", 0.3)),
    "Breast_1.R": (("cf_j_bust02_R", 0.6), ("cf_j_bust01_R", 0.4)),
    "Breast_2.R": (("cf_j_bust03_R", 0.7), ("cf_j_bust02_R", 0.3)),
}

BREAST_SOURCE_GROUPS = tuple(SIMPLE_J_CHAIN.keys())

DEFAULT_BODY_GROUPS = {
    "cf_j_spine03",
    "cf_d_bust00",
    "cf_j_bust01_L",
    "cf_j_bust02_L",
    "cf_j_bust03_L",
    "cf_j_bust01_R",
    "cf_j_bust02_R",
    "cf_j_bust03_R",
    "cf_j_shoulder_L",
    "cf_j_shoulder_R",
    "cf_j_arm00_L",
    "cf_j_arm00_R",
}


def remap_breast_weights(
    obj,
    mapping,
    kk_bone_names,
    do_apply,
    remove_sources,
    normalize_affected,
    smooth_after_apply,
    smooth_iterations,
    smooth_strength,
    smooth_expand_rings,
):
    missing_targets = []
    missing_sources = []
    source_groups = {}

    for source_name, targets in mapping.items():
        source_group = obj.vertex_groups.get(source_name)
        if source_group is None:
            missing_sources.append(source_name)
            continue
        source_groups[source_name] = source_group
        for target_name, _factor in targets:
            if target_name not in kk_bone_names:
                missing_targets.append(f"{source_name} -> {target_name}")

    affected_vertices = set()
    for vertex in obj.data.vertices:
        source_weights = []
        for source_name, source_group in source_groups.items():
            weight = common.get_vertex_weight(vertex, source_group.index)
            if weight > 0.0:
                source_weights.append((source_name, source_group, weight))
        if not source_weights:
            continue
        affected_vertices.add(vertex.index)
        if not do_apply:
            continue
        for source_name, source_group, source_weight in source_weights:
            for target_name, factor in mapping[source_name]:
                if target_name not in kk_bone_names:
                    continue
                target_group = common.get_or_create_group(obj, target_name)
                old_weight = common.get_vertex_weight(vertex, target_group.index)
                target_group.add([vertex.index], old_weight + source_weight * factor, "REPLACE")
            if remove_sources:
                common.remove_vertex_from_group(source_group, vertex.index)

    if do_apply and normalize_affected:
        common.normalize_affected_vertices(obj, affected_vertices)

    smoothed_vertices = 0
    if do_apply and smooth_after_apply:
        smooth_groups = [
            target_name
            for targets in mapping.values()
            for target_name, _factor in targets
            if target_name in kk_bone_names
        ]
        smoothed_vertices = common.smooth_vertex_group_weights(
            obj,
            affected_vertices,
            smooth_groups,
            smooth_iterations,
            smooth_strength,
            smooth_expand_rings,
            normalize_affected,
        )

    if do_apply and remove_sources:
        common.remove_empty_groups(obj, source_groups.keys())

    return {
        "mesh": obj.name,
        "affected_vertices": len(affected_vertices),
        "smoothed_vertices": smoothed_vertices,
        "mapping": [f"{source} -> " + ", ".join(f"{name}*{factor:g}" for name, factor in targets) for source, targets in mapping.items()],
        "missing_sources": missing_sources,
        "missing_targets": sorted(set(missing_targets)),
    }


def mix_breast_weights(
    obj,
    kk_bone_names,
    mapping,
    include_root,
    breast_factor,
    body_factor,
    do_apply,
    remove_sources,
    normalize_affected,
    smooth_after_apply,
    smooth_iterations,
    smooth_strength,
    smooth_expand_rings,
):
    source_names = set(BREAST_SOURCE_GROUPS)
    if not include_root:
        source_names.discard("Breast_root.L")
        source_names.discard("Breast_root.R")

    source_groups = {}
    missing_sources = []
    missing_targets = []
    for source_name in source_names:
        group = obj.vertex_groups.get(source_name)
        if group is None:
            missing_sources.append(source_name)
            continue
        source_groups[source_name] = group
        for target_name, _factor in mapping[source_name]:
            if target_name not in kk_bone_names:
                missing_targets.append(f"{source_name} -> {target_name}")

    body_group_names = {name for name in DEFAULT_BODY_GROUPS if name in obj.vertex_groups and name in kk_bone_names}
    affected_vertices = set()
    touched_group_names = set(body_group_names)

    for vertex in obj.data.vertices:
        source_weights = []
        source_total = 0.0
        for source_name, source_group in source_groups.items():
            weight = common.get_vertex_weight(vertex, source_group.index)
            if weight > 0.0:
                source_weights.append((source_name, source_group, weight))
                source_total += weight
        if source_total <= 0.0:
            continue
        affected_vertices.add(vertex.index)
        if not do_apply:
            continue

        existing_body_weights = {}
        body_total = 0.0
        for body_name in body_group_names:
            body_group = obj.vertex_groups.get(body_name)
            if body_group is None:
                continue
            weight = common.get_vertex_weight(vertex, body_group.index)
            if weight > 0.0:
                existing_body_weights[body_name] = weight
                body_total += weight
        if body_total > 0.0:
            for body_name, weight in existing_body_weights.items():
                common.set_weight(obj, body_name, vertex.index, (weight / body_total) * body_factor)
        elif "cf_j_spine03" in kk_bone_names:
            common.set_weight(obj, "cf_j_spine03", vertex.index, body_factor)
            touched_group_names.add("cf_j_spine03")

        breast_target_weights = {}
        for source_name, source_group, weight in source_weights:
            source_ratio = weight / source_total
            for target_name, target_factor in mapping[source_name]:
                if target_name not in kk_bone_names:
                    continue
                breast_target_weights[target_name] = breast_target_weights.get(target_name, 0.0) + source_ratio * target_factor * breast_factor
            if remove_sources:
                common.remove_vertex_from_group(source_group, vertex.index)

        for target_name, weight in breast_target_weights.items():
            target_group = obj.vertex_groups.get(target_name)
            old_weight = common.get_vertex_weight(vertex, target_group.index) if target_group is not None else 0.0
            common.set_weight(obj, target_name, vertex.index, old_weight + weight)
            touched_group_names.add(target_name)

        if normalize_affected:
            common.normalize_vertex_subset(obj, vertex.index, touched_group_names)

    smoothed_vertices = 0
    if do_apply and smooth_after_apply:
        smooth_groups = set(body_group_names)
        for source_name in source_names:
            for target_name, _factor in mapping[source_name]:
                if target_name in kk_bone_names:
                    smooth_groups.add(target_name)
        if "cf_j_spine03" in kk_bone_names:
            smooth_groups.add("cf_j_spine03")
        smoothed_vertices = common.smooth_vertex_group_weights(
            obj,
            affected_vertices,
            smooth_groups,
            smooth_iterations,
            smooth_strength,
            smooth_expand_rings,
            normalize_affected,
        )

    if do_apply and remove_sources:
        common.remove_empty_groups(obj, source_groups.keys())

    return {
        "mesh": obj.name,
        "affected_vertices": len(affected_vertices),
        "smoothed_vertices": smoothed_vertices,
        "source_groups": sorted(source_groups.keys()),
        "body_groups": sorted(body_group_names),
        "missing_sources": sorted(missing_sources),
        "missing_targets": sorted(set(missing_targets)),
    }


class KKVRC_OT_remap_breast_simple(bpy.types.Operator):
    bl_idname = "kkvrc.remap_breast_simple"
    bl_label = "Breast Simple Remap"
    bl_description = "Remap VRC breast vertex groups to KK bust bones"
    bl_options = {"REGISTER", "UNDO"}

    action: bpy.props.EnumProperty(
        items=(("PREVIEW", "Preview", ""), ("APPLY", "Apply", ""), ("REPORT", "Report", "")),
        default="PREVIEW",
        options={"HIDDEN"},
    )

    def execute(self, context):
        props = context.scene.kkvrc_cloth_tools
        try:
            kk_armature = common.get_active_kk_armature(context)
            meshes = common.get_target_meshes(kk_armature, context)
            kk_bone_names = common.get_armature_bone_names(kk_armature)
        except Exception as ex:
            self.report({"ERROR"}, str(ex))
            common.set_status(context, f"Breast simple failed: {ex}")
            return {"CANCELLED"}
        mapping = SIMPLE_J_CHAIN if props.breast_simple_mode == "SIMPLE" else DISTRIBUTED_J_CHAIN
        do_apply = self.action == "APPLY"
        reports = [
            remap_breast_weights(
                mesh,
                mapping,
                kk_bone_names,
                do_apply,
                props.breast_simple_remove_source_groups,
                props.breast_simple_normalize_affected_only,
                props.breast_simple_smooth_after_apply,
                props.breast_simple_smooth_iterations,
                props.breast_simple_smooth_strength,
                props.breast_simple_smooth_expand_rings,
            )
            for mesh in meshes
        ]
        title = "Breast Simple Remap Applied" if do_apply else "Breast Simple Remap Preview"
        if self.action == "REPORT":
            title = "Breast Simple Remap Report"
        common.print_report(title, reports, (("smoothed_vertices", "Smoothed vertices"), ("mapping", "Mapping"), ("missing_sources", "Missing source groups"), ("missing_targets", "Missing KK targets")))
        self.report({"INFO"}, f"{'Applied' if do_apply else 'Previewed'} breast remap for {len(meshes)} mesh(es). See console.")
        common.set_status(context, f"Breast simple {'applied' if do_apply else 'preview'}: {len(meshes)} mesh(es)")
        return {"FINISHED"}


class KKVRC_OT_mix_breast_local(bpy.types.Operator):
    bl_idname = "kkvrc.mix_breast_local"
    bl_label = "Breast Local Mix"
    bl_description = "Locally mix VRC breast weights into KK bust bones while preserving body influence"
    bl_options = {"REGISTER", "UNDO"}

    action: bpy.props.EnumProperty(
        items=(("PREVIEW", "Preview", ""), ("APPLY", "Apply", ""), ("REPORT", "Report", "")),
        default="PREVIEW",
        options={"HIDDEN"},
    )

    def execute(self, context):
        props = context.scene.kkvrc_cloth_tools
        try:
            kk_armature = common.get_active_kk_armature(context)
            meshes = common.get_target_meshes(kk_armature, context)
            kk_bone_names = common.get_armature_bone_names(kk_armature)
        except Exception as ex:
            self.report({"ERROR"}, str(ex))
            common.set_status(context, f"Breast local failed: {ex}")
            return {"CANCELLED"}
        mapping = SIMPLE_J_CHAIN if props.breast_local_mode == "DIRECT" else DISTRIBUTED_J_CHAIN
        do_apply = self.action == "APPLY"
        reports = [
            mix_breast_weights(
                mesh,
                kk_bone_names,
                mapping,
                props.breast_local_include_root_group,
                props.breast_local_breast_factor,
                props.breast_local_body_factor,
                do_apply,
                props.breast_local_remove_source_groups,
                props.breast_local_normalize_affected_only,
                props.breast_local_smooth_after_apply,
                props.breast_local_smooth_iterations,
                props.breast_local_smooth_strength,
                props.breast_local_smooth_expand_rings,
            )
            for mesh in meshes
        ]
        title = "Local Breast Mix Applied" if do_apply else "Local Breast Mix Preview"
        if self.action == "REPORT":
            title = "Local Breast Mix Report"
        common.print_report(title, reports, (("smoothed_vertices", "Smoothed vertices"), ("source_groups", "Source breast groups"), ("body_groups", "Body groups kept/mixed"), ("missing_sources", "Missing source groups"), ("missing_targets", "Missing KK targets")))
        self.report({"INFO"}, f"{'Applied' if do_apply else 'Previewed'} local breast mix for {len(meshes)} mesh(es). See console.")
        common.set_status(context, f"Breast local {'applied' if do_apply else 'preview'}: {len(meshes)} mesh(es)")
        return {"FINISHED"}
