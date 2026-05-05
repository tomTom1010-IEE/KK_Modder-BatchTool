import bpy


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


KK_STANDARD_BONE_PREFIXES = (
    "cf_j_",
    "cf_d_",
    "cf_s_",
)


def is_armature(obj):
    return obj is not None and obj.type == "ARMATURE"


def is_mesh(obj):
    return obj is not None and obj.type == "MESH"


def get_active_kk_armature():
    obj = bpy.context.view_layer.objects.active
    if is_armature(obj):
        return obj

    for selected in bpy.context.selected_objects:
        if is_armature(selected):
            return selected

    for selected in bpy.context.selected_objects:
        if not is_mesh(selected):
            continue

        for modifier in selected.modifiers:
            if modifier.type == "ARMATURE" and is_armature(modifier.object):
                return modifier.object

    raise RuntimeError("Select the KK Armature, make it active, or select a mesh whose Armature modifier points to it.")


def is_descendant_of(obj, parent):
    current = obj.parent
    while current:
        if current == parent:
            return True
        current = current.parent
    return False


def get_target_meshes(kk_armature):
    selected_meshes = [obj for obj in bpy.context.selected_objects if is_mesh(obj)]
    if selected_meshes:
        return selected_meshes

    meshes = []
    for obj in bpy.data.objects:
        if is_mesh(obj) and is_descendant_of(obj, kk_armature):
            meshes.append(obj)

    if not meshes:
        raise RuntimeError("No selected meshes and no mesh children found under the KK Armature.")

    return meshes


def get_armature_bone_names(armature_obj):
    return {bone.name for bone in armature_obj.data.bones}


def is_kk_standard_bone_name(name):
    return name.startswith(KK_STANDARD_BONE_PREFIXES)


def find_vertex_group(obj, name):
    return obj.vertex_groups.get(name)


def group_has_weights(obj, group_index):
    for vertex in obj.data.vertices:
        for group in vertex.groups:
            if group.group == group_index and group.weight > 0.0:
                return True
    return False


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
        has_weights = group_has_weights(obj, vertex_group.index)

        if not has_weights:
            empty_groups.append(name)

        if name in VRC_TO_KK_BODY_GROUPS:
            target_name = VRC_TO_KK_BODY_GROUPS[name]
            if target_name not in kk_bone_names:
                missing_targets.append(f"{name} -> {target_name}")
                continue

            if not do_apply:
                if find_vertex_group(obj, target_name):
                    merged.append(f"{name} -> {target_name}")
                else:
                    remapped.append(f"{name} -> {target_name}")
                continue

            target_group = find_vertex_group(obj, target_name)
            if target_group:
                merge_vertex_groups(obj, vertex_group, target_group)
                merged.append(f"{name} -> {target_name}")
            else:
                vertex_group.name = target_name
                remapped.append(f"{name} -> {target_name}")
            continue

        if name in kk_bone_names and not is_kk_standard_bone_name(name):
            physical_or_preserved.append(name)
            continue

        if name in kk_bone_names and is_kk_standard_bone_name(name):
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


def print_report(title, reports):
    print("\n" + title)
    print("=" * len(title))

    if not reports:
        print("(none)")
        return

    for report in reports:
        print(f"\nMesh: {report['mesh']}")
        for key, label in (
            ("remapped", "Remapped"),
            ("merged", "Merged"),
            ("missing_targets", "Missing KK target"),
            ("physical_or_preserved", "Preserved KK/physical groups"),
            ("orphan", "Orphan groups"),
            ("empty_groups", "Empty groups"),
        ):
            values = report[key]
            if values:
                print(f"  {label}: {', '.join(values)}")


class KKMODS_OT_remap_vrc_body_weights_to_kk(bpy.types.Operator):
    bl_idname = "kkmods.remap_vrc_body_weights_to_kk"
    bl_label = "Remap VRC Body Weights To KK"
    bl_description = "Rename VRC humanoid vertex groups to KK body bone names while preserving non-standard physical bones"
    bl_options = {"REGISTER", "UNDO"}

    action: bpy.props.EnumProperty(
        name="Action",
        items=(
            ("PREVIEW", "Preview", "Preview vertex group remapping without changing meshes"),
            ("APPLY", "Apply", "Apply vertex group remapping"),
            ("REPORT", "Report Orphans", "Only report groups that are not mapped and not present in KK Armature"),
        ),
        default="PREVIEW",
    )
    normalize_after_apply: bpy.props.BoolProperty(
        name="Normalize after apply",
        default=False,
    )
    limit_total: bpy.props.IntProperty(
        name="Limit total weights",
        default=4,
        min=0,
        max=32,
        description="0 disables Limit Total",
    )

    def execute(self, context):
        try:
            kk_armature = get_active_kk_armature()
            meshes = get_target_meshes(kk_armature)
            kk_bone_names = get_armature_bone_names(kk_armature)
        except Exception as ex:
            self.report({"ERROR"}, str(ex))
            return {"CANCELLED"}

        do_apply = self.action == "APPLY"
        reports = []

        for mesh in meshes:
            report = remap_mesh_vertex_groups(mesh, kk_bone_names, do_apply)
            reports.append(report)
            if do_apply and self.normalize_after_apply:
                normalize_mesh_weights(mesh, self.limit_total)

        if self.action == "REPORT":
            orphan_reports = []
            for report in reports:
                orphan_reports.append(
                    {
                        "mesh": report["mesh"],
                        "remapped": [],
                        "merged": [],
                        "missing_targets": report["missing_targets"],
                        "physical_or_preserved": [],
                        "orphan": report["orphan"],
                        "empty_groups": report["empty_groups"],
                    }
                )
            print_report("VRC to KK Weight Orphan Report", orphan_reports)
            self.report({"INFO"}, f"Reported orphan groups for {len(meshes)} mesh(es). See console.")
            return {"FINISHED"}

        title = "VRC to KK Weight Remap Applied" if do_apply else "VRC to KK Weight Remap Preview"
        print_report(title, reports)
        self.report({"INFO"}, f"{'Applied' if do_apply else 'Previewed'} remap for {len(meshes)} mesh(es). See console.")
        return {"FINISHED"}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=520)


class KKMODS_MT_weight_tools(bpy.types.Menu):
    bl_idname = "KKMODS_MT_weight_tools"
    bl_label = "KK Mods"

    def draw(self, context):
        self.layout.operator(KKMODS_OT_remap_vrc_body_weights_to_kk.bl_idname)


def menu_func(self, context):
    self.layout.menu(KKMODS_MT_weight_tools.bl_idname)


def safe_unregister_class(cls):
    try:
        bpy.utils.unregister_class(cls)
    except Exception:
        pass


def register():
    bpy.utils.register_class(KKMODS_OT_remap_vrc_body_weights_to_kk)
    bpy.utils.register_class(KKMODS_MT_weight_tools)
    bpy.types.TOPBAR_MT_editor_menus.append(menu_func)
    bpy.types.VIEW3D_MT_object.append(menu_func)


def unregister():
    try:
        bpy.types.TOPBAR_MT_editor_menus.remove(menu_func)
    except Exception:
        pass

    try:
        bpy.types.VIEW3D_MT_object.remove(menu_func)
    except Exception:
        pass

    safe_unregister_class(KKMODS_MT_weight_tools)
    safe_unregister_class(KKMODS_OT_remap_vrc_body_weights_to_kk)


if __name__ == "__main__":
    unregister()
    register()
    bpy.ops.kkmods.remap_vrc_body_weights_to_kk("INVOKE_DEFAULT")
