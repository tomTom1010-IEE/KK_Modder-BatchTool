import json
import os
from datetime import datetime

import bpy


def vector_to_list(value):
    return [float(value.x), float(value.y), float(value.z)]


def matrix_to_rows(value):
    return [[float(cell) for cell in row] for row in value]


def get_blend_dir():
    if bpy.data.filepath:
        return os.path.dirname(bpy.data.filepath)
    return os.path.expanduser("~")


def make_unique_path(path):
    if not os.path.exists(path):
        return path

    root, ext = os.path.splitext(path)
    index = 1
    while True:
        candidate = f"{root}_{index:03d}{ext}"
        if not os.path.exists(candidate):
            return candidate
        index += 1


def get_active_armature():
    obj = bpy.context.object
    if obj and obj.type == "ARMATURE":
        return obj

    selected = [item for item in bpy.context.selected_objects if item.type == "ARMATURE"]
    if len(selected) == 1:
        return selected[0]

    return None


def collect_armature_data(armature_obj):
    if armature_obj is None or armature_obj.type != "ARMATURE":
        raise ValueError("Expected an Armature object.")

    armature_data = armature_obj.data
    world_matrix = armature_obj.matrix_world.copy()

    bones = []
    for bone in armature_data.bones:
        head_local = bone.head_local.copy()
        tail_local = bone.tail_local.copy()
        head_world = world_matrix @ head_local
        tail_world = world_matrix @ tail_local
        roll = getattr(bone, "roll", None)

        parent = bone.parent.name if bone.parent else None
        children = [child.name for child in bone.children]

        bones.append(
            {
                "name": bone.name,
                "basename": bone.basename,
                "parent": parent,
                "children": children,
                "index": len(bones),
                "use_connect": bool(bone.use_connect),
                "use_deform": bool(bone.use_deform),
                "head_local": vector_to_list(head_local),
                "tail_local": vector_to_list(tail_local),
                "head_world": vector_to_list(head_world),
                "tail_world": vector_to_list(tail_world),
                "length": float(bone.length),
                "roll": float(roll) if roll is not None else None,
                "matrix_local": matrix_to_rows(bone.matrix_local),
            }
        )

    root_bones = [bone.name for bone in armature_data.bones if bone.parent is None]

    return {
        "schema": "armature_topology_v1",
        "exported_at": datetime.now().isoformat(timespec="seconds"),
        "blender_version": bpy.app.version_string,
        "object": {
            "name": armature_obj.name,
            "data_name": armature_data.name,
            "matrix_world": matrix_to_rows(world_matrix),
            "location": vector_to_list(armature_obj.location),
            "rotation_euler": vector_to_list(armature_obj.rotation_euler),
            "scale": vector_to_list(armature_obj.scale),
        },
        "bone_count": len(bones),
        "root_bones": root_bones,
        "bones": bones,
    }


def export_armature_topology(armature_obj, output_path=None):
    data = collect_armature_data(armature_obj)

    if output_path is None:
        safe_name = bpy.path.clean_name(armature_obj.name)
        output_path = os.path.join(get_blend_dir(), f"{safe_name}_armature_topology.json")

    output_path = bpy.path.abspath(output_path)
    output_path = make_unique_path(output_path)

    with open(output_path, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)

    return output_path


class EXPORT_OT_armature_topology_json(bpy.types.Operator):
    bl_idname = "export_scene.armature_topology_json"
    bl_label = "Export Armature Topology JSON"
    bl_description = "Export the active Armature bone hierarchy and rest-pose coordinates to JSON"
    bl_options = {"REGISTER"}

    filepath: bpy.props.StringProperty(
        name="Output Path",
        description="JSON file path",
        subtype="FILE_PATH",
        default="",
    )

    def execute(self, context):
        armature_obj = get_active_armature()
        if armature_obj is None:
            self.report({"ERROR"}, "Select exactly one Armature or make an Armature active.")
            return {"CANCELLED"}

        output_path = self.filepath if self.filepath else None
        try:
            exported = export_armature_topology(armature_obj, output_path)
        except Exception as ex:
            self.report({"ERROR"}, str(ex))
            return {"CANCELLED"}

        self.report({"INFO"}, f"Exported armature topology: {exported}")
        print(f"Exported armature topology: {exported}")
        return {"FINISHED"}

    def invoke(self, context, event):
        armature_obj = get_active_armature()
        if armature_obj is None:
            self.report({"ERROR"}, "Select exactly one Armature or make an Armature active.")
            return {"CANCELLED"}

        safe_name = bpy.path.clean_name(armature_obj.name)
        self.filepath = os.path.join(get_blend_dir(), f"{safe_name}_armature_topology.json")
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}


def menu_func_export(self, context):
    self.layout.operator(EXPORT_OT_armature_topology_json.bl_idname, text="Armature Topology JSON (.json)")


def register():
    bpy.utils.register_class(EXPORT_OT_armature_topology_json)
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)


def unregister():
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)
    bpy.utils.unregister_class(EXPORT_OT_armature_topology_json)


if __name__ == "__main__":
    armature = get_active_armature()
    if armature is None:
        raise RuntimeError("Select exactly one Armature or make an Armature active before running this script.")

    path = export_armature_topology(armature)
    print(f"Exported armature topology: {path}")
