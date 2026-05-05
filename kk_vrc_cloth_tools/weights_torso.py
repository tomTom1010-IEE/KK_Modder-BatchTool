import bpy

from . import common


BALANCED_TORSO = {
    "Hips": (("cf_j_hips", 0.50), ("cf_j_waist02", 0.30), ("cf_j_waist01", 0.20)),
    "Spine": (("cf_j_waist01", 0.40), ("cf_j_spine01", 0.40), ("cf_j_spine02", 0.20)),
    "Chest": (("cf_j_spine02", 0.30), ("cf_j_spine03", 0.70)),
    "Butt.L": (("cf_j_siri_L", 0.60), ("cf_j_waist02", 0.25), ("cf_j_hips", 0.15)),
    "Butt.R": (("cf_j_siri_R", 0.60), ("cf_j_waist02", 0.25), ("cf_j_hips", 0.15)),
}

CONSERVATIVE_TORSO = {
    "Hips": (("cf_j_hips", 0.50), ("cf_j_waist02", 0.50)),
    "Spine": (("cf_j_waist01", 0.50), ("cf_j_spine01", 0.50)),
    "Chest": (("cf_j_spine03", 1.00),),
    "Butt.L": (("cf_j_siri_L", 0.70), ("cf_j_waist02", 0.30)),
    "Butt.R": (("cf_j_siri_R", 0.70), ("cf_j_waist02", 0.30)),
}


def mix_torso_hip_weights(
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
    source_groups = {}
    missing_sources = []
    missing_targets = []

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
    mapping_summary = [
        f"{source} -> " + ", ".join(f"{target}*{factor:g}" for target, factor in targets)
        for source, targets in mapping.items()
    ]

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

        if normalize_affected:
            common.normalize_affected_vertices(obj, {vertex.index})

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
        "mapping": mapping_summary,
        "missing_sources": sorted(missing_sources),
        "missing_targets": sorted(set(missing_targets)),
    }


class KKVRC_OT_mix_torso_hip_weights(bpy.types.Operator):
    bl_idname = "kkvrc.mix_torso_hip_weights"
    bl_label = "Mix Torso/Hip Weights"
    bl_description = "Distribute VRC Hips/Spine/Chest/Butt weights into KK waist, spine, and siri bones"
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
            common.set_status(context, f"Torso mix failed: {ex}")
            return {"CANCELLED"}

        mapping = BALANCED_TORSO if props.torso_mode == "BALANCED" else CONSERVATIVE_TORSO
        do_apply = self.action == "APPLY"
        reports = [
            mix_torso_hip_weights(
                mesh,
                mapping,
                kk_bone_names,
                do_apply,
                props.torso_remove_source_groups,
                props.torso_normalize_affected_only,
                props.torso_smooth_after_apply,
                props.torso_smooth_iterations,
                props.torso_smooth_strength,
                props.torso_smooth_expand_rings,
            )
            for mesh in meshes
        ]
        title = "Torso/Hip Weight Mix Applied" if do_apply else "Torso/Hip Weight Mix Preview"
        if self.action == "REPORT":
            title = "Torso/Hip Weight Mix Report"
        common.print_report(title, reports, (("smoothed_vertices", "Smoothed vertices"), ("mapping", "Mapping"), ("missing_sources", "Missing source groups"), ("missing_targets", "Missing KK targets")))
        self.report({"INFO"}, f"{'Applied' if do_apply else 'Previewed'} torso/hip mix for {len(meshes)} mesh(es). See console.")
        common.set_status(context, f"Torso {'applied' if do_apply else 'preview'}: {len(meshes)} mesh(es)")
        return {"FINISHED"}
