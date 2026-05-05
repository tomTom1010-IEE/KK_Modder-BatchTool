import bpy

from . import common


VRC_TO_KK_BODY_GROUPS = {
    "Neck": "cf_j_neck",
    "Head": "cf_j_head",
    "Shoulder.L": "cf_j_shoulder_L",
    "Upper_arm.L": "cf_j_arm00_L",
    "Lower_arm.L": "cf_j_forearm01_L",
    "Hand.L": "cf_j_hand_L",
    "Shoulder.R": "cf_j_shoulder_R",
    "Upper_arm.R": "cf_j_arm00_R",
    "Lower_arm.R": "cf_j_forearm01_R",
    "Hand.R": "cf_j_hand_R",
    "Upper_leg.L": "cf_j_thigh00_L",
    "Lower_leg.L": "cf_j_leg01_L",
    "Foot.L": "cf_j_foot_L",
    "Toe.L": "cf_j_toes_L",
    "Upper_leg.R": "cf_j_thigh00_R",
    "Lower_leg.R": "cf_j_leg01_R",
    "Foot.R": "cf_j_foot_R",
    "Toe.R": "cf_j_toes_R",
    "Thumb Proximal.L": "cf_j_thumb01_L",
    "Thumb Intermediate.L": "cf_j_thumb02_L",
    "Thumb Distal.L": "cf_j_thumb03_L",
    "Index Proximal.L": "cf_j_index01_L",
    "Index Intermediate.L": "cf_j_index02_L",
    "Index Distal.L": "cf_j_index03_L",
    "Middle Proximal.L": "cf_j_middle01_L",
    "Middle Intermediate.L": "cf_j_middle02_L",
    "Middle Distal.L": "cf_j_middle03_L",
    "Ring Proximal.L": "cf_j_ring01_L",
    "Ring Intermediate.L": "cf_j_ring02_L",
    "Ring Distal.L": "cf_j_ring03_L",
    "Little Proximal.L": "cf_j_little01_L",
    "Little Intermediate.L": "cf_j_little02_L",
    "Little Distal.L": "cf_j_little03_L",
    "Thumb Proximal.R": "cf_j_thumb01_R",
    "Thumb Intermediate.R": "cf_j_thumb02_R",
    "Thumb Distal.R": "cf_j_thumb03_R",
    "Index Proximal.R": "cf_j_index01_R",
    "Index Intermediate.R": "cf_j_index02_R",
    "Index Distal.R": "cf_j_index03_R",
    "Middle Proximal.R": "cf_j_middle01_R",
    "Middle Intermediate.R": "cf_j_middle02_R",
    "Middle Distal.R": "cf_j_middle03_R",
    "Ring Proximal.R": "cf_j_ring01_R",
    "Ring Intermediate.R": "cf_j_ring02_R",
    "Ring Distal.R": "cf_j_ring03_R",
    "Little Proximal.R": "cf_j_little01_R",
    "Little Intermediate.R": "cf_j_little02_R",
    "Little Distal.R": "cf_j_little03_R",
}

KK_STANDARD_BONE_PREFIXES = ("cf_j_", "cf_d_", "cf_s_")


def is_kk_standard_bone_name(name):
    return name.startswith(KK_STANDARD_BONE_PREFIXES)


def merge_vertex_groups(obj, source_group, target_group):
    for vertex in obj.data.vertices:
        source_weight = 0.0
        target_weight = 0.0
        for group in vertex.groups:
            if group.group == source_group.index:
                source_weight = group.weight
            elif group.group == target_group.index:
                target_weight = group.weight
        if source_weight > 0.0:
            target_group.add([vertex.index], min(source_weight + target_weight, 1.0), "REPLACE")
    obj.vertex_groups.remove(source_group)


def remap_mesh_vertex_groups(obj, kk_bone_names, do_apply):
    remapped = []
    merged = []
    missing_targets = []
    physical_or_preserved = []
    orphan = []
    empty_groups = []

    for vertex_group in list(obj.vertex_groups):
        name = vertex_group.name
        if not common.group_has_weights(obj, vertex_group.index):
            empty_groups.append(name)

        if name in VRC_TO_KK_BODY_GROUPS:
            target_name = VRC_TO_KK_BODY_GROUPS[name]
            if target_name not in kk_bone_names:
                missing_targets.append(f"{name} -> {target_name}")
                continue
            if not do_apply:
                if obj.vertex_groups.get(target_name):
                    merged.append(f"{name} -> {target_name}")
                else:
                    remapped.append(f"{name} -> {target_name}")
                continue
            target_group = obj.vertex_groups.get(target_name)
            if target_group:
                merge_vertex_groups(obj, vertex_group, target_group)
                merged.append(f"{name} -> {target_name}")
            else:
                vertex_group.name = target_name
                remapped.append(f"{name} -> {target_name}")
            continue

        if name in kk_bone_names:
            physical_or_preserved.append(name)
            continue

        orphan.append(name)

    return {
        "mesh": obj.name,
        "remapped": remapped,
        "merged": merged,
        "missing_targets": missing_targets,
        "physical_or_preserved": physical_or_preserved,
        "orphan": orphan,
        "empty_groups": empty_groups,
    }


def normalize_mesh_weights(obj, limit_total):
    if bpy.context.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode="WEIGHT_PAINT")
    bpy.ops.object.vertex_group_normalize_all(lock_active=False)
    if limit_total > 0:
        bpy.ops.object.vertex_group_limit_total(group_select_mode="ALL", limit=limit_total)
        bpy.ops.object.vertex_group_normalize_all(lock_active=False)
    bpy.ops.object.mode_set(mode="OBJECT")


class KKVRC_OT_remap_body_weights(bpy.types.Operator):
    bl_idname = "kkvrc.remap_body_weights"
    bl_label = "Remap Low-Risk Body Groups"
    bl_description = "Rename low-risk VRC humanoid vertex groups to KK body bone names"
    bl_options = {"REGISTER", "UNDO"}

    action: bpy.props.EnumProperty(
        items=(
            ("PREVIEW", "Preview", ""),
            ("APPLY", "Apply", ""),
            ("REPORT", "Report Orphans", ""),
        ),
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
            common.set_status(context, f"Body remap failed: {ex}")
            return {"CANCELLED"}

        do_apply = self.action == "APPLY"
        reports = []
        for mesh in meshes:
            report = remap_mesh_vertex_groups(mesh, kk_bone_names, do_apply)
            reports.append(report)
            if do_apply and props.body_normalize_after_apply:
                normalize_mesh_weights(mesh, props.body_limit_total)

        if self.action == "REPORT":
            title = "VRC to KK Weight Orphan Report"
            report_data = [
                {
                    "mesh": report["mesh"],
                    "missing_targets": report["missing_targets"],
                    "orphan": report["orphan"],
                    "empty_groups": report["empty_groups"],
                }
                for report in reports
            ]
            common.print_report(title, report_data, (("missing_targets", "Missing KK target"), ("orphan", "Orphan groups"), ("empty_groups", "Empty groups")))
            self.report({"INFO"}, f"Reported orphan groups for {len(meshes)} mesh(es). See console.")
            common.set_status(context, f"Body report: {len(meshes)} mesh(es)")
            return {"FINISHED"}

        title = "VRC to KK Weight Remap Applied" if do_apply else "VRC to KK Weight Remap Preview"
        common.print_report(
            title,
            reports,
            (
                ("remapped", "Remapped"),
                ("merged", "Merged"),
                ("missing_targets", "Missing KK target"),
                ("physical_or_preserved", "Preserved KK/physical groups"),
                ("orphan", "Orphan groups"),
                ("empty_groups", "Empty groups"),
            ),
        )
        self.report({"INFO"}, f"{'Applied' if do_apply else 'Previewed'} remap for {len(meshes)} mesh(es). See console.")
        common.set_status(context, f"Body {'applied' if do_apply else 'preview'}: {len(meshes)} mesh(es)")
        return {"FINISHED"}

