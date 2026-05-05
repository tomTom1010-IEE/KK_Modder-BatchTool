import bpy


BREAST_SOURCE_GROUPS = (
    "Breast_root.L",
    "Breast_1.L",
    "Breast_2.L",
    "Breast_root.R",
    "Breast_1.R",
    "Breast_2.R",
)

BREAST_DIRECT_TARGETS = {
    "Breast_root.L": (("cf_j_bust01_L", 1.0),),
    "Breast_1.L": (("cf_j_bust02_L", 1.0),),
    "Breast_2.L": (("cf_j_bust03_L", 1.0),),
    "Breast_root.R": (("cf_j_bust01_R", 1.0),),
    "Breast_1.R": (("cf_j_bust02_R", 1.0),),
    "Breast_2.R": (("cf_j_bust03_R", 1.0),),
}

BREAST_DISTRIBUTED_TARGETS = {
    "Breast_root.L": (("cf_j_bust01_L", 0.7), ("cf_d_bust00", 0.3)),
    "Breast_1.L": (("cf_j_bust02_L", 0.6), ("cf_j_bust01_L", 0.4)),
    "Breast_2.L": (("cf_j_bust03_L", 0.7), ("cf_j_bust02_L", 0.3)),
    "Breast_root.R": (("cf_j_bust01_R", 0.7), ("cf_d_bust00", 0.3)),
    "Breast_1.R": (("cf_j_bust02_R", 0.6), ("cf_j_bust01_R", 0.4)),
    "Breast_2.R": (("cf_j_bust03_R", 0.7), ("cf_j_bust02_R", 0.3)),
}

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


def get_or_create_group(obj, name):
    group = obj.vertex_groups.get(name)
    if group is None:
        group = obj.vertex_groups.new(name=name)
    return group


def get_vertex_weight(vertex, group_index):
    for group in vertex.groups:
        if group.group == group_index:
            return group.weight
    return 0.0


def set_weight(obj, group_name, vertex_index, weight):
    group = get_or_create_group(obj, group_name)
    if weight <= 0.0:
        try:
            group.remove([vertex_index])
        except RuntimeError:
            pass
    else:
        group.add([vertex_index], weight, "REPLACE")


def normalize_vertex_subset(obj, vertex_index, group_names):
    total = 0.0
    vertex = obj.data.vertices[vertex_index]

    for group_name in group_names:
        group = obj.vertex_groups.get(group_name)
        if group is None:
            continue
        total += get_vertex_weight(vertex, group.index)

    if total <= 0.0:
        return

    for group_name in group_names:
        group = obj.vertex_groups.get(group_name)
        if group is None:
            continue
        weight = get_vertex_weight(vertex, group.index)
        if weight > 0.0:
            group.add([vertex_index], weight / total, "REPLACE")


def remove_vertex_from_group(group, vertex_index):
    try:
        group.remove([vertex_index])
    except RuntimeError:
        pass


def remove_empty_groups(obj, names):
    for name in names:
        group = obj.vertex_groups.get(name)
        if group is None:
            continue

        has_weights = False
        for vertex in obj.data.vertices:
            if get_vertex_weight(vertex, group.index) > 0.0:
                has_weights = True
                break

        if not has_weights:
            obj.vertex_groups.remove(group)


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
            weight = get_vertex_weight(vertex, source_group.index)
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
            weight = get_vertex_weight(vertex, body_group.index)
            if weight > 0.0:
                existing_body_weights[body_name] = weight
                body_total += weight

        if body_total > 0.0:
            for body_name, weight in existing_body_weights.items():
                set_weight(obj, body_name, vertex.index, (weight / body_total) * body_factor)
        elif "cf_j_spine03" in kk_bone_names:
            set_weight(obj, "cf_j_spine03", vertex.index, body_factor)
            touched_group_names.add("cf_j_spine03")

        breast_target_weights = {}
        for source_name, source_group, weight in source_weights:
            source_ratio = weight / source_total
            for target_name, target_factor in mapping[source_name]:
                if target_name not in kk_bone_names:
                    continue
                breast_target_weights[target_name] = breast_target_weights.get(target_name, 0.0) + source_ratio * target_factor * breast_factor

            if remove_sources:
                remove_vertex_from_group(source_group, vertex.index)

        for target_name, weight in breast_target_weights.items():
            old_weight = 0.0
            target_group = obj.vertex_groups.get(target_name)
            if target_group is not None:
                old_weight = get_vertex_weight(vertex, target_group.index)
            set_weight(obj, target_name, vertex.index, old_weight + weight)
            touched_group_names.add(target_name)

        if normalize_affected:
            normalize_vertex_subset(obj, vertex.index, touched_group_names)

    if do_apply and remove_sources:
        remove_empty_groups(obj, source_groups.keys())

    return {
        "mesh": obj.name,
        "affected_vertices": len(affected_vertices),
        "source_groups": sorted(source_groups.keys()),
        "body_groups": sorted(body_group_names),
        "missing_sources": sorted(missing_sources),
        "missing_targets": sorted(set(missing_targets)),
    }


def print_report(title, reports):
    print("\n" + title)
    print("=" * len(title))
    for report in reports:
        print(f"\nMesh: {report['mesh']}")
        print(f"  Affected vertices: {report['affected_vertices']}")
        if report["source_groups"]:
            print(f"  Source breast groups: {', '.join(report['source_groups'])}")
        if report["body_groups"]:
            print(f"  Body groups kept/mixed: {', '.join(report['body_groups'])}")
        if report["missing_sources"]:
            print(f"  Missing source groups: {', '.join(report['missing_sources'])}")
        if report["missing_targets"]:
            print(f"  Missing KK targets: {', '.join(report['missing_targets'])}")


class KKMODS_OT_mix_breast_weights_local(bpy.types.Operator):
    bl_idname = "kkmods.mix_breast_weights_local"
    bl_label = "Mix Breast Weights Local"
    bl_description = "Locally mix VRC breast weights into KK bust bones while preserving body influence"
    bl_options = {"REGISTER", "UNDO"}

    action: bpy.props.EnumProperty(
        name="Action",
        items=(
            ("PREVIEW", "Preview", "Preview local breast mixing without changing meshes"),
            ("APPLY", "Apply", "Apply local breast mixing"),
            ("REPORT", "Report", "Report affected vertices and groups"),
        ),
        default="PREVIEW",
    )
    mode: bpy.props.EnumProperty(
        name="Breast Target Mapping",
        items=(
            ("DIRECT", "Direct J Chain", "Use direct cf_j_bust01/02/03 targets"),
            ("DISTRIBUTED", "Distributed J Chain", "Distribute into adjacent KK bust bones"),
        ),
        default="DISTRIBUTED",
    )
    include_root_group: bpy.props.BoolProperty(
        name="Include Breast_root.L/R",
        default=False,
    )
    breast_factor: bpy.props.FloatProperty(
        name="Breast influence",
        default=0.7,
        min=0.0,
        max=1.0,
    )
    body_factor: bpy.props.FloatProperty(
        name="Body influence",
        default=0.3,
        min=0.0,
        max=1.0,
    )
    remove_source_groups: bpy.props.BoolProperty(
        name="Remove source breast groups after apply",
        default=True,
    )
    normalize_affected_only: bpy.props.BoolProperty(
        name="Normalize affected vertices only",
        default=True,
    )

    def execute(self, context):
        try:
            kk_armature = get_active_kk_armature()
            meshes = get_target_meshes(kk_armature)
            kk_bone_names = get_armature_bone_names(kk_armature)
        except Exception as ex:
            self.report({"ERROR"}, str(ex))
            return {"CANCELLED"}

        mapping = BREAST_DIRECT_TARGETS if self.mode == "DIRECT" else BREAST_DISTRIBUTED_TARGETS
        do_apply = self.action == "APPLY"
        reports = [
            mix_breast_weights(
                mesh,
                kk_bone_names,
                mapping,
                self.include_root_group,
                self.breast_factor,
                self.body_factor,
                do_apply,
                self.remove_source_groups,
                self.normalize_affected_only,
            )
            for mesh in meshes
        ]

        title = "Local Breast Mix Applied" if do_apply else "Local Breast Mix Preview"
        if self.action == "REPORT":
            title = "Local Breast Mix Report"
        print_report(title, reports)
        self.report({"INFO"}, f"{'Applied' if do_apply else 'Previewed'} local breast mix for {len(meshes)} mesh(es). See console.")
        return {"FINISHED"}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=520)


class KKMODS_MT_breast_mix_tools(bpy.types.Menu):
    bl_idname = "KKMODS_MT_breast_mix_tools"
    bl_label = "KK Mods"

    def draw(self, context):
        self.layout.operator(KKMODS_OT_mix_breast_weights_local.bl_idname)


def menu_func(self, context):
    self.layout.menu(KKMODS_MT_breast_mix_tools.bl_idname)


def safe_unregister_class(cls):
    try:
        bpy.utils.unregister_class(cls)
    except Exception:
        pass


def register():
    bpy.utils.register_class(KKMODS_OT_mix_breast_weights_local)
    bpy.utils.register_class(KKMODS_MT_breast_mix_tools)
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
    safe_unregister_class(KKMODS_MT_breast_mix_tools)
    safe_unregister_class(KKMODS_OT_mix_breast_weights_local)


if __name__ == "__main__":
    unregister()
    register()
    bpy.ops.kkmods.mix_breast_weights_local("INVOKE_DEFAULT")
