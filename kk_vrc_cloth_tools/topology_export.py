import json
import os
from datetime import datetime

import bpy

from . import common


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


def get_active_armature(context=None):
    context = context or bpy.context
    obj = context.object
    if common.is_armature(obj):
        return obj
    selected = [item for item in context.selected_objects if common.is_armature(item)]
    if len(selected) == 1:
        return selected[0]
    return None


def collect_armature_data(armature_obj):
    if not common.is_armature(armature_obj):
        raise ValueError("Expected an Armature object.")
    armature_data = armature_obj.data
    world_matrix = armature_obj.matrix_world.copy()
    bones = []
    for bone in armature_data.bones:
        head_local = bone.head_local.copy()
        tail_local = bone.tail_local.copy()
        bones.append(
            {
                "name": bone.name,
                "basename": bone.basename,
                "parent": bone.parent.name if bone.parent else None,
                "children": [child.name for child in bone.children],
                "index": len(bones),
                "use_connect": bool(bone.use_connect),
                "use_deform": bool(bone.use_deform),
                "head_local": vector_to_list(head_local),
                "tail_local": vector_to_list(tail_local),
                "head_world": vector_to_list(world_matrix @ head_local),
                "tail_world": vector_to_list(world_matrix @ tail_local),
                "length": float(bone.length),
                "roll": float(getattr(bone, "roll", 0.0)),
                "matrix_local": matrix_to_rows(bone.matrix_local),
            }
        )
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
        "root_bones": [bone.name for bone in armature_data.bones if bone.parent is None],
        "bones": bones,
    }


def export_armature_topology(armature_obj, output_path=None):
    data = collect_armature_data(armature_obj)
    if output_path is None:
        safe_name = bpy.path.clean_name(armature_obj.name)
        output_path = os.path.join(get_blend_dir(), f"{safe_name}_armature_topology.json")
    output_path = make_unique_path(bpy.path.abspath(output_path))
    with open(output_path, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)
    return output_path


class KKVRC_OT_export_armature_topology(bpy.types.Operator):
    bl_idname = "kkvrc.export_armature_topology"
    bl_label = "Export Armature Topology JSON"
    bl_description = "Export the active or singly selected Armature topology JSON beside the .blend file"
    bl_options = {"REGISTER"}

    def execute(self, context):
        armature_obj = get_active_armature(context)
        if armature_obj is None:
            self.report({"ERROR"}, "Select exactly one Armature or make an Armature active.")
            common.set_status(context, "Topology export failed: no Armature")
            return {"CANCELLED"}
        try:
            exported = export_armature_topology(armature_obj)
        except Exception as ex:
            self.report({"ERROR"}, str(ex))
            common.set_status(context, f"Topology export failed: {ex}")
            return {"CANCELLED"}
        print(f"Exported armature topology: {exported}")
        self.report({"INFO"}, f"Exported armature topology: {exported}")
        common.set_status(context, f"Exported topology: {exported}")
        return {"FINISHED"}

