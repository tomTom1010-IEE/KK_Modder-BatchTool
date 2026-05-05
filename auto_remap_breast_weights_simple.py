import bpy


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


def set_vertex_weight(obj, group_name, vertex_index, weight):
    group = get_or_create_group(obj, group_name)
    if weight <= 0.0:
        group.remove([vertex_index])
    else:
        group.add([vertex_index], weight, "REPLACE")


def remove_vertex_from_group(group, vertex_index):
    try:
        group.remove([vertex_index])
    except RuntimeError:
        pass


def normalize_affected_vertices(obj, vertex_indices):
    for vertex_index in vertex_indices:
        vertex = obj.data.vertices[vertex_index]
        total = sum(group.weight for group in vertex.groups if group.weight > 0.0)
        if total <= 0.0:
            continue

        for group_ref in list(vertex.groups):
            vertex_group = obj.vertex_groups[group_ref.group]
            vertex_group.add([vertex_index], group_ref.weight / total, "REPLACE")


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


def remap_breast_weights(obj, mapping, kk_bone_names, do_apply, remove_sources, normalize_affected):
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
    target_summary = []

    for vertex in obj.data.vertices:
        source_weights = []
        for source_name, source_group in source_groups.items():
            weight = get_vertex_weight(vertex, source_group.index)
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
                target_group = get_or_create_group(obj, target_name)
                old_weight = get_vertex_weight(vertex, target_group.index)
                target_group.add([vertex.index], old_weight + source_weight * factor, "REPLACE")

            if remove_sources:
                remove_vertex_from_group(source_group, vertex.index)

    if do_apply and normalize_affected:
        normalize_affected_vertices(obj, affected_vertices)

    if do_apply and remove_sources:
        remove_empty_groups(obj, source_groups.keys())

    for source_name, targets in mapping.items():
        target_summary.append(f"{source_name} -> " + ", ".join(f"{name}*{factor:g}" for name, factor in targets))

    return {
        "mesh": obj.name,
        "affected_vertices": len(affected_vertices),
        "mapping": target_summary,
        "missing_sources": missing_sources,
        "missing_targets": sorted(set(missing_targets)),
    }


def print_report(title, reports):
    print("\n" + title)
    print("=" * len(title))
    for report in reports:
        print(f"\nMesh: {report['mesh']}")
        print(f"  Affected vertices: {report['affected_vertices']}")
        if report["mapping"]:
            print("  Mapping:")
            for item in report["mapping"]:
                print(f"    {item}")
        if report["missing_sources"]:
            print(f"  Missing source groups: {', '.join(report['missing_sources'])}")
        if report["missing_targets"]:
            print(f"  Missing KK targets: {', '.join(report['missing_targets'])}")


class KKMODS_OT_remap_breast_weights_simple(bpy.types.Operator):
    bl_idname = "kkmods.remap_breast_weights_simple"
    bl_label = "Remap Breast Weights Simple"
    bl_description = "Remap VRC breast vertex groups to KK bust bones using simple or distributed mapping"
    bl_options = {"REGISTER", "UNDO"}

    action: bpy.props.EnumProperty(
        name="Action",
        items=(
            ("PREVIEW", "Preview", "Preview breast remapping without changing meshes"),
            ("APPLY", "Apply", "Apply breast remapping"),
            ("REPORT", "Report", "Report source and target availability"),
        ),
        default="PREVIEW",
    )
    mode: bpy.props.EnumProperty(
        name="Mode",
        items=(
            ("SIMPLE", "Simple J Chain", "Breast_root/1/2 map directly to cf_j_bust01/02/03"),
            ("DISTRIBUTED", "Distributed J Chain", "Distribute each VRC breast group across adjacent KK bust bones"),
        ),
        default="SIMPLE",
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

        mapping = SIMPLE_J_CHAIN if self.mode == "SIMPLE" else DISTRIBUTED_J_CHAIN
        do_apply = self.action == "APPLY"
        reports = [
            remap_breast_weights(
                mesh,
                mapping,
                kk_bone_names,
                do_apply,
                self.remove_source_groups,
                self.normalize_affected_only,
            )
            for mesh in meshes
        ]

        title = "Breast Simple Remap Applied" if do_apply else "Breast Simple Remap Preview"
        if self.action == "REPORT":
            title = "Breast Simple Remap Report"
        print_report(title, reports)
        self.report({"INFO"}, f"{'Applied' if do_apply else 'Previewed'} breast remap for {len(meshes)} mesh(es). See console.")
        return {"FINISHED"}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=520)


class KKMODS_MT_breast_simple_tools(bpy.types.Menu):
    bl_idname = "KKMODS_MT_breast_simple_tools"
    bl_label = "KK Mods"

    def draw(self, context):
        self.layout.operator(KKMODS_OT_remap_breast_weights_simple.bl_idname)


def menu_func(self, context):
    self.layout.menu(KKMODS_MT_breast_simple_tools.bl_idname)


def safe_unregister_class(cls):
    try:
        bpy.utils.unregister_class(cls)
    except Exception:
        pass


def register():
    bpy.utils.register_class(KKMODS_OT_remap_breast_weights_simple)
    bpy.utils.register_class(KKMODS_MT_breast_simple_tools)
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
    safe_unregister_class(KKMODS_MT_breast_simple_tools)
    safe_unregister_class(KKMODS_OT_remap_breast_weights_simple)


if __name__ == "__main__":
    unregister()
    register()
    bpy.ops.kkmods.remap_breast_weights_simple("INVOKE_DEFAULT")
