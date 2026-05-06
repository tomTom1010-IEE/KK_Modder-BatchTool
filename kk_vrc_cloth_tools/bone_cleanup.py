import fnmatch
from collections import deque

import bpy

from . import common


DEFAULT_HAIR_TIP_PATTERNS = "CYCRHair*_tip,*Hair*_tip,*_tip"


def get_active_armature(context):
    obj = context.view_layer.objects.active
    if not common.is_armature(obj):
        raise RuntimeError("Make the target Armature active.")
    return obj


def get_active_bone_name(context, armature_obj):
    active_pose = getattr(context, "active_pose_bone", None)
    if active_pose and active_pose.name in armature_obj.data.bones:
        return active_pose.name

    active_bone = armature_obj.data.bones.active
    if active_bone:
        return active_bone.name

    selected = get_selected_bone_names(context, armature_obj)
    if len(selected) == 1:
        return selected[0]

    raise RuntimeError("Select one active bone in Pose Mode or Edit Mode.")


def get_selected_bone_names(context, armature_obj):
    if context.mode == "POSE":
        return [bone.name for bone in context.selected_pose_bones or [] if bone.name in armature_obj.data.bones]

    if context.mode == "EDIT_ARMATURE":
        return [bone.name for bone in context.selected_bones or [] if bone.name in armature_obj.data.bones]

    active = armature_obj.data.bones.active
    return [active.name] if active else []


def get_children_map(armature_obj):
    children = {}
    for bone in armature_obj.data.bones:
        children.setdefault(bone.name, [])
        if bone.parent:
            children.setdefault(bone.parent.name, []).append(bone.name)
    return children


def get_parent_map(armature_obj):
    return {bone.name: bone.parent.name if bone.parent else None for bone in armature_obj.data.bones}


def collect_subtree_names(children_map, root_name):
    names = []
    queue = deque([root_name])
    while queue:
        name = queue.popleft()
        names.append(name)
        queue.extend(children_map.get(name, []))
    return names


def get_depths(children_map, root_name):
    depths = {}
    queue = deque([(root_name, 0)])
    while queue:
        name, depth = queue.popleft()
        depths[name] = depth
        for child_name in children_map.get(name, []):
            queue.append((child_name, depth + 1))
    return depths


def get_armature_meshes(armature_obj):
    meshes = []
    for obj in bpy.data.objects:
        if not common.is_mesh(obj):
            continue
        if obj.parent == armature_obj:
            meshes.append(obj)
            continue
        for modifier in obj.modifiers:
            if modifier.type == "ARMATURE" and modifier.object == armature_obj:
                meshes.append(obj)
                break
    return sorted(set(meshes), key=lambda obj: obj.name)


def merge_vertex_group_to_parent(mesh_obj, source_name, target_name):
    source_group = mesh_obj.vertex_groups.get(source_name)
    if source_group is None:
        return 0

    target_group = common.get_or_create_group(mesh_obj, target_name)
    affected = 0

    for vertex in mesh_obj.data.vertices:
        source_weight = common.get_vertex_weight(vertex, source_group.index)
        if source_weight <= 0.0:
            continue

        target_weight = common.get_vertex_weight(vertex, target_group.index)
        target_group.add([vertex.index], min(source_weight + target_weight, 1.0), "REPLACE")
        affected += 1

    mesh_obj.vertex_groups.remove(source_group)
    return affected


def merge_groups_to_target(armature_obj, source_names, target_name):
    merged_groups = set()
    affected_vertices = 0

    for mesh in get_armature_meshes(armature_obj):
        for source_name in source_names:
            affected = merge_vertex_group_to_parent(mesh, source_name, target_name)
            if affected:
                merged_groups.add(source_name)
                affected_vertices += affected

    return sorted(merged_groups), affected_vertices


def remove_bones_subtree(armature_obj, root_names):
    if bpy.context.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")

    bpy.ops.object.select_all(action="DESELECT")
    armature_obj.select_set(True)
    bpy.context.view_layer.objects.active = armature_obj
    bpy.ops.object.mode_set(mode="EDIT")

    removed = []
    try:
        edit_bones = armature_obj.data.edit_bones
        for root_name in root_names:
            root_bone = edit_bones.get(root_name)
            if root_bone is None:
                continue

            subtree = []
            queue = deque([root_bone])
            while queue:
                bone = queue.popleft()
                subtree.append(bone.name)
                queue.extend(list(bone.children))

            for bone_name in reversed(subtree):
                bone = edit_bones.get(bone_name)
                if bone is None:
                    continue
                edit_bones.remove(bone)
                removed.append(bone_name)
    finally:
        bpy.ops.object.mode_set(mode="OBJECT")

    return removed


def remove_single_bone_graft_children(armature_obj, bone_name):
    if bpy.context.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")

    bpy.ops.object.select_all(action="DESELECT")
    armature_obj.select_set(True)
    bpy.context.view_layer.objects.active = armature_obj
    bpy.ops.object.mode_set(mode="EDIT")

    removed = False
    parent_name = None
    child_names = []

    try:
        edit_bones = armature_obj.data.edit_bones
        bone = edit_bones.get(bone_name)
        if bone is None:
            return False, None, []

        parent = bone.parent
        parent_name = parent.name if parent else None
        child_names = [child.name for child in bone.children]

        if parent is not None:
            for child in list(bone.children):
                child.parent = parent
                child.use_connect = False

        edit_bones.remove(bone)
        removed = True
    finally:
        bpy.ops.object.mode_set(mode="OBJECT")

    return removed, parent_name, child_names


def delete_bone_tree(armature_obj, root_name, mode, do_apply):
    children_map = get_children_map(armature_obj)
    parent_map = get_parent_map(armature_obj)
    if root_name not in parent_map:
        raise RuntimeError(f"Bone not found: {root_name}")

    parent_name = parent_map[root_name]
    if parent_name is None:
        raise RuntimeError("Selected bone has no parent outside the chain.")

    subtree = collect_subtree_names(children_map, root_name)
    is_leaf = len(children_map.get(root_name, [])) == 0

    if mode == "SUBTREE_TO_PARENT" or is_leaf:
        merge_sources = subtree
        delete_roots = [root_name]
        grafted_children = []
    else:
        merge_sources = [root_name]
        delete_roots = [root_name]
        grafted_children = list(children_map.get(root_name, []))

    if not do_apply:
        return {
            "mesh": armature_obj.name,
            "root": root_name,
            "parent": parent_name,
            "mode": mode,
            "is_leaf": is_leaf,
            "deleted_bones": subtree if mode == "SUBTREE_TO_PARENT" or is_leaf else [root_name],
            "merged_groups": merge_sources,
            "affected_vertices": 0,
            "grafted_children": grafted_children,
        }

    merged_groups, affected_vertices = merge_groups_to_target(armature_obj, merge_sources, parent_name)
    if mode == "SUBTREE_TO_PARENT" or is_leaf:
        remove_bones_subtree(armature_obj, delete_roots)
    else:
        remove_single_bone_graft_children(armature_obj, root_name)

    return {
        "mesh": armature_obj.name,
        "root": root_name,
        "parent": parent_name,
        "mode": mode,
        "is_leaf": is_leaf,
        "deleted_bones": subtree if mode == "SUBTREE_TO_PARENT" or is_leaf else [root_name],
        "merged_groups": merged_groups,
        "affected_vertices": affected_vertices,
        "grafted_children": grafted_children,
    }


def compute_simplify_delete_set(children_map, root_name, keep_every):
    keep_every = max(1, keep_every)
    delete_set = set()

    def walk(name, steps_since_keep):
        children = children_map.get(name, [])
        is_root = name == root_name
        is_leaf = len(children) == 0
        is_branch = len(children) > 1
        must_keep = is_root or is_leaf or is_branch or steps_since_keep >= keep_every

        if must_keep:
            next_steps = 0
        else:
            delete_set.add(name)
            next_steps = steps_since_keep + 1

        if is_branch:
            next_steps = 0

        for child_name in children:
            walk(child_name, next_steps + 1)

    walk(root_name, 0)
    return delete_set


def simplify_bone_chain(armature_obj, root_name, keep_every, do_apply):
    children_map = get_children_map(armature_obj)
    parent_map = get_parent_map(armature_obj)
    if root_name not in parent_map:
        raise RuntimeError(f"Bone not found: {root_name}")

    subtree = collect_subtree_names(children_map, root_name)
    branch_nodes = [name for name in subtree if len(children_map.get(name, [])) > 1]
    delete_set = compute_simplify_delete_set(children_map, root_name, keep_every)
    depths = get_depths(children_map, root_name)
    delete_names = sorted(delete_set, key=lambda name: depths.get(name, 0))

    if not do_apply:
        return {
            "mesh": armature_obj.name,
            "root": root_name,
            "deleted_bones": delete_names,
            "branch_nodes": branch_nodes,
            "affected_vertices": 0,
        }

    affected_vertices = 0
    merged_groups = set()
    for bone_name in delete_names:
        current_parent = armature_obj.data.bones.get(bone_name).parent.name if armature_obj.data.bones.get(bone_name) and armature_obj.data.bones.get(bone_name).parent else None
        if current_parent is None:
            continue
        groups, affected = merge_groups_to_target(armature_obj, [bone_name], current_parent)
        merged_groups.update(groups)
        affected_vertices += affected
        remove_single_bone_graft_children(armature_obj, bone_name)

    return {
        "mesh": armature_obj.name,
        "root": root_name,
        "deleted_bones": delete_names,
        "merged_groups": sorted(merged_groups),
        "branch_nodes": branch_nodes,
        "affected_vertices": affected_vertices,
    }


def parse_patterns(raw):
    return [item.strip() for item in raw.replace("\n", ",").replace(";", ",").split(",") if item.strip()]


def matches_patterns(name, patterns):
    return any(fnmatch.fnmatchcase(name, pattern) for pattern in patterns)


def cleanup_hair_tip_placeholders(armature_obj, patterns, merge_weighted, mode, do_apply):
    children_map = get_children_map(armature_obj)
    candidates = [
        bone.name
        for bone in armature_obj.data.bones
        if not children_map.get(bone.name) and matches_patterns(bone.name, patterns)
    ]

    weighted = []
    unweighted = []
    for bone_name in candidates:
        has_weights = False
        for mesh in get_armature_meshes(armature_obj):
            group = mesh.vertex_groups.get(bone_name)
            if group is not None and common.group_has_weights(mesh, group.index):
                has_weights = True
                break
        if has_weights:
            weighted.append(bone_name)
        else:
            unweighted.append(bone_name)

    skipped_weighted = [] if merge_weighted else weighted
    to_delete = list(unweighted) + (weighted if merge_weighted else [])

    if not do_apply:
        return {
            "mesh": armature_obj.name,
            "deleted_bones": to_delete,
            "unweighted_tips": unweighted,
            "weighted_tips": weighted,
            "skipped_weighted": skipped_weighted,
            "affected_vertices": 0,
        }

    affected_vertices = 0
    merged_groups = set()
    for bone_name in to_delete:
        if bone_name not in armature_obj.data.bones:
            continue
        parent_name = armature_obj.data.bones[bone_name].parent.name if armature_obj.data.bones[bone_name].parent else None
        if parent_name and bone_name in weighted and merge_weighted:
            groups, affected = merge_groups_to_target(armature_obj, [bone_name], parent_name)
            merged_groups.update(groups)
            affected_vertices += affected
        elif bone_name in weighted and not merge_weighted:
            continue
        remove_single_bone_graft_children(armature_obj, bone_name)

    return {
        "mesh": armature_obj.name,
        "deleted_bones": to_delete,
        "merged_groups": sorted(merged_groups),
        "unweighted_tips": unweighted,
        "weighted_tips": weighted,
        "skipped_weighted": skipped_weighted,
        "affected_vertices": affected_vertices,
    }


def print_bone_report(title, report, sections):
    common.print_report(title, [report], sections)
    if "root" in report:
        print(f"  Root bone: {report['root']}")
    if "parent" in report:
        print(f"  Parent bone: {report['parent']}")
    if "is_leaf" in report:
        print(f"  Is leaf: {report['is_leaf']}")


class KKVRC_OT_delete_selected_bone_tree(bpy.types.Operator):
    bl_idname = "kkvrc.delete_selected_bone_tree"
    bl_label = "Delete Selected Bone Chain/Subtree"
    bl_description = "Delete the active bone or subtree and merge weights to the outside parent"
    bl_options = {"REGISTER", "UNDO"}

    action: bpy.props.EnumProperty(items=(("PREVIEW", "Preview", ""), ("APPLY", "Apply", "")), default="PREVIEW", options={"HIDDEN"})

    def execute(self, context):
        props = context.scene.kkvrc_cloth_tools
        do_apply = self.action == "APPLY"
        try:
            armature_obj = get_active_armature(context)
            root_name = get_active_bone_name(context, armature_obj)
            report = delete_bone_tree(armature_obj, root_name, props.cleanup_delete_mode, do_apply)
        except Exception as ex:
            self.report({"ERROR"}, str(ex))
            common.set_status(context, f"Bone delete failed: {ex}")
            return {"CANCELLED"}

        title = "Delete Bone Chain/Subtree Applied" if do_apply else "Delete Bone Chain/Subtree Preview"
        print_bone_report(title, report, (("deleted_bones", "Deleted bones"), ("merged_groups", "Merged groups"), ("grafted_children", "Grafted children")))
        self.report({"INFO"}, f"{'Deleted' if do_apply else 'Previewed'} {len(report['deleted_bones'])} bone(s).")
        common.set_status(context, f"Bone delete {'applied' if do_apply else 'preview'}: {len(report['deleted_bones'])} bone(s)")
        return {"FINISHED"}


class KKVRC_OT_simplify_selected_bone_chain(bpy.types.Operator):
    bl_idname = "kkvrc.simplify_selected_bone_chain"
    bl_label = "Simplify Selected Physical Bone Chain"
    bl_description = "Keep every Nth bone in the selected subtree while preserving branch and leaf nodes"
    bl_options = {"REGISTER", "UNDO"}

    action: bpy.props.EnumProperty(items=(("PREVIEW", "Preview", ""), ("APPLY", "Apply", "")), default="PREVIEW", options={"HIDDEN"})

    def execute(self, context):
        props = context.scene.kkvrc_cloth_tools
        do_apply = self.action == "APPLY"
        try:
            armature_obj = get_active_armature(context)
            root_name = get_active_bone_name(context, armature_obj)
            report = simplify_bone_chain(armature_obj, root_name, props.cleanup_simplify_keep_every, do_apply)
        except Exception as ex:
            self.report({"ERROR"}, str(ex))
            common.set_status(context, f"Bone simplify failed: {ex}")
            return {"CANCELLED"}

        title = "Simplify Physical Bone Chain Applied" if do_apply else "Simplify Physical Bone Chain Preview"
        print_bone_report(title, report, (("deleted_bones", "Deleted bones"), ("merged_groups", "Merged groups"), ("branch_nodes", "Preserved branch nodes")))
        self.report({"INFO"}, f"{'Simplified' if do_apply else 'Previewed'} {len(report['deleted_bones'])} removable bone(s).")
        common.set_status(context, f"Bone simplify {'applied' if do_apply else 'preview'}: {len(report['deleted_bones'])} bone(s)")
        return {"FINISHED"}


class KKVRC_OT_cleanup_hair_tip_placeholders(bpy.types.Operator):
    bl_idname = "kkvrc.cleanup_hair_tip_placeholders"
    bl_label = "Clean VRC Hair Tip Placeholders"
    bl_description = "Delete VRC-only hair placeholder leaf bones, optionally merging weighted tips to their parents"
    bl_options = {"REGISTER", "UNDO"}

    action: bpy.props.EnumProperty(items=(("PREVIEW", "Preview", ""), ("APPLY", "Apply", "")), default="PREVIEW", options={"HIDDEN"})

    def execute(self, context):
        props = context.scene.kkvrc_cloth_tools
        do_apply = self.action == "APPLY"
        try:
            armature_obj = get_active_armature(context)
            patterns = parse_patterns(props.cleanup_hair_tip_patterns)
            report = cleanup_hair_tip_placeholders(
                armature_obj,
                patterns,
                props.cleanup_merge_weighted_hair_tips,
                props.cleanup_delete_mode,
                do_apply,
            )
        except Exception as ex:
            self.report({"ERROR"}, str(ex))
            common.set_status(context, f"Hair tip cleanup failed: {ex}")
            return {"CANCELLED"}

        title = "Hair Tip Placeholder Cleanup Applied" if do_apply else "Hair Tip Placeholder Cleanup Preview"
        print_bone_report(
            title,
            report,
            (
                ("deleted_bones", "Deleted hair tip bones"),
                ("weighted_tips", "Weighted tips"),
                ("skipped_weighted", "Skipped weighted tips"),
                ("merged_groups", "Merged groups"),
            ),
        )
        self.report({"INFO"}, f"{'Cleaned' if do_apply else 'Previewed'} {len(report['deleted_bones'])} hair tip bone(s).")
        common.set_status(context, f"Hair tip cleanup {'applied' if do_apply else 'preview'}: {len(report['deleted_bones'])} bone(s)")
        return {"FINISHED"}
