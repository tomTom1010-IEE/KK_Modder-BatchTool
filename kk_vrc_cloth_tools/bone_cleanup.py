import fnmatch
from collections import deque

import bpy
from mathutils import Vector

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


def filter_selected_root_bones(selected_names, parent_map):
    selected_set = set(selected_names)
    roots = []

    for name in selected_names:
        parent_name = parent_map.get(name)
        has_selected_ancestor = False
        while parent_name:
            if parent_name in selected_set:
                has_selected_ancestor = True
                break
            parent_name = parent_map.get(parent_name)

        if not has_selected_ancestor:
            roots.append(name)

    return roots


def collect_linear_chain(children_map, root_name):
    chain = []
    current = root_name

    while current:
        chain.append(current)
        children = children_map.get(current, [])
        if len(children) > 1:
            raise RuntimeError(f"Parallel merge expects unbranched chains. Branch found at: {current}")
        current = children[0] if children else None

    return chain


def choose_parallel_target_root(selected_roots, active_name, mode):
    if not selected_roots:
        raise RuntimeError("Select at least two parallel chain roots.")

    if mode == "ACTIVE":
        if active_name not in selected_roots:
            raise RuntimeError("The active bone must be one of the selected parallel chain roots.")
        return active_name

    if mode == "LAST":
        return selected_roots[-1]

    return selected_roots[0]


def map_parallel_chain_index(source_index, source_count, target_count, match_mode):
    if target_count <= 1:
        return 0

    if match_mode == "BOTTOM":
        source_from_tip = source_count - 1 - source_index
        return max(0, target_count - 1 - source_from_tip)

    if match_mode == "RATIO":
        if source_count <= 1:
            return 0
        return round((source_index / (source_count - 1)) * (target_count - 1))

    return min(source_index, target_count - 1)


def build_parallel_merge_pairs(source_chain, target_chain, match_mode):
    pairs = []
    for source_index, source_name in enumerate(source_chain):
        target_index = map_parallel_chain_index(source_index, len(source_chain), len(target_chain), match_mode)
        pairs.append((source_name, target_chain[target_index]))
    return pairs


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


def ensure_nonzero_edit_bone_length(edit_bone):
    if edit_bone.length > 0.0001:
        return False

    edit_bone.tail = edit_bone.head + Vector((0.0, 0.0, 0.01))
    return True


def reconnect_simplified_chain_tails(armature_obj, root_name, connect_single_children):
    if bpy.context.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")

    bpy.ops.object.select_all(action="DESELECT")
    armature_obj.select_set(True)
    bpy.context.view_layer.objects.active = armature_obj
    bpy.ops.object.mode_set(mode="EDIT")

    adjusted = 0
    connected = 0
    branch_adjusted = 0
    fixed_zero_length = 0

    try:
        edit_bones = armature_obj.data.edit_bones
        root = edit_bones.get(root_name)
        if root is None:
            return adjusted, connected, branch_adjusted, fixed_zero_length

        bones = []
        queue = deque([root])
        while queue:
            bone = queue.popleft()
            bones.append(bone)
            queue.extend(list(bone.children))

        for bone in bones:
            children = list(bone.children)
            if not children:
                if ensure_nonzero_edit_bone_length(bone):
                    fixed_zero_length += 1
                continue

            if len(children) == 1:
                child = children[0]
                bone.tail = child.head.copy()
                adjusted += 1
                if connect_single_children:
                    child.use_connect = True
                    connected += 1
                continue

            average_head = children[0].head.copy()
            for child in children[1:]:
                average_head += child.head
            average_head /= len(children)

            if (average_head - bone.head).length <= 0.0001:
                if ensure_nonzero_edit_bone_length(bone):
                    fixed_zero_length += 1
            else:
                bone.tail = average_head
                adjusted += 1
                branch_adjusted += 1

            for child in children:
                child.use_connect = False
    finally:
        bpy.ops.object.mode_set(mode="OBJECT")

    return adjusted, connected, branch_adjusted, fixed_zero_length


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


def simplify_bone_chain(armature_obj, root_name, keep_every, reconnect_tails, connect_single_children, do_apply):
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
            "reconnect_tails": reconnect_tails,
            "connect_single_children": connect_single_children,
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

    adjusted_tails = 0
    connected_children = 0
    branch_adjusted = 0
    fixed_zero_length = 0
    if reconnect_tails:
        adjusted_tails, connected_children, branch_adjusted, fixed_zero_length = reconnect_simplified_chain_tails(
            armature_obj,
            root_name,
            connect_single_children,
        )

    return {
        "mesh": armature_obj.name,
        "root": root_name,
        "deleted_bones": delete_names,
        "merged_groups": sorted(merged_groups),
        "branch_nodes": branch_nodes,
        "adjusted_tails": adjusted_tails,
        "connected_children": connected_children,
        "branch_adjusted": branch_adjusted,
        "fixed_zero_length": fixed_zero_length,
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


def merge_parallel_bone_chains(armature_obj, selected_names, active_name, target_mode, match_mode, length_tolerance, do_apply):
    children_map = get_children_map(armature_obj)
    parent_map = get_parent_map(armature_obj)
    selected_roots = filter_selected_root_bones(selected_names, parent_map)

    if len(selected_roots) < 2:
        raise RuntimeError("Select at least two parallel chain roots.")

    target_root = choose_parallel_target_root(selected_roots, active_name, target_mode)
    chains = {root_name: collect_linear_chain(children_map, root_name) for root_name in selected_roots}
    target_chain = chains[target_root]
    target_len = len(target_chain)

    skipped_roots = []
    merge_pairs = []
    source_roots = []

    for root_name in selected_roots:
        if root_name == target_root:
            continue

        source_chain = chains[root_name]
        if abs(len(source_chain) - target_len) > length_tolerance:
            skipped_roots.append(root_name)
            continue

        source_roots.append(root_name)
        merge_pairs.extend(build_parallel_merge_pairs(source_chain, target_chain, match_mode))

    if not merge_pairs:
        raise RuntimeError("No compatible source chains found for parallel merge.")

    if not do_apply:
        return {
            "mesh": armature_obj.name,
            "root": target_root,
            "selected_roots": selected_roots,
            "source_roots": source_roots,
            "skipped_roots": skipped_roots,
            "target_chain": target_chain,
            "merge_pairs": [f"{source} -> {target}" for source, target in merge_pairs],
            "deleted_bones": [bone_name for root_name in source_roots for bone_name in chains[root_name]],
            "affected_vertices": 0,
        }

    affected_vertices = 0
    merged_groups = set()
    for source_name, target_name in merge_pairs:
        groups, affected = merge_groups_to_target(armature_obj, [source_name], target_name)
        merged_groups.update(groups)
        affected_vertices += affected

    deleted_bones = remove_bones_subtree(armature_obj, source_roots)

    return {
        "mesh": armature_obj.name,
        "root": target_root,
        "selected_roots": selected_roots,
        "source_roots": source_roots,
        "skipped_roots": skipped_roots,
        "target_chain": target_chain,
        "merge_pairs": [f"{source} -> {target}" for source, target in merge_pairs],
        "merged_groups": sorted(merged_groups),
        "deleted_bones": deleted_bones,
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
            report = simplify_bone_chain(
                armature_obj,
                root_name,
                props.cleanup_simplify_keep_every,
                props.cleanup_reconnect_simplified_chain,
                props.cleanup_connect_single_child_bones,
                do_apply,
            )
        except Exception as ex:
            self.report({"ERROR"}, str(ex))
            common.set_status(context, f"Bone simplify failed: {ex}")
            return {"CANCELLED"}

        title = "Simplify Physical Bone Chain Applied" if do_apply else "Simplify Physical Bone Chain Preview"
        print_bone_report(
            title,
            report,
            (
                ("deleted_bones", "Deleted bones"),
                ("merged_groups", "Merged groups"),
                ("branch_nodes", "Preserved branch nodes"),
                ("adjusted_tails", "Adjusted bone tails"),
                ("connected_children", "Connected single-child bones"),
                ("branch_adjusted", "Adjusted branch display bones"),
                ("fixed_zero_length", "Fixed zero-length bones"),
            ),
        )
        self.report({"INFO"}, f"{'Simplified' if do_apply else 'Previewed'} {len(report['deleted_bones'])} removable bone(s).")
        common.set_status(context, f"Bone simplify {'applied' if do_apply else 'preview'}: {len(report['deleted_bones'])} bone(s)")
        return {"FINISHED"}


class KKVRC_OT_merge_selected_parallel_bone_chains(bpy.types.Operator):
    bl_idname = "kkvrc.merge_selected_parallel_bone_chains"
    bl_label = "Merge Selected Parallel Bone Chains"
    bl_description = "Merge selected parallel physical bone chains and their weights into one selected target chain"
    bl_options = {"REGISTER", "UNDO"}

    action: bpy.props.EnumProperty(items=(("PREVIEW", "Preview", ""), ("APPLY", "Apply", "")), default="PREVIEW", options={"HIDDEN"})

    def execute(self, context):
        props = context.scene.kkvrc_cloth_tools
        do_apply = self.action == "APPLY"
        try:
            armature_obj = get_active_armature(context)
            selected_names = get_selected_bone_names(context, armature_obj)
            active_name = get_active_bone_name(context, armature_obj)
            report = merge_parallel_bone_chains(
                armature_obj,
                selected_names,
                active_name,
                props.cleanup_parallel_merge_target,
                props.cleanup_parallel_merge_match,
                props.cleanup_parallel_merge_tolerance,
                do_apply,
            )
        except Exception as ex:
            self.report({"ERROR"}, str(ex))
            common.set_status(context, f"Parallel chain merge failed: {ex}")
            return {"CANCELLED"}

        title = "Parallel Bone Chain Merge Applied" if do_apply else "Parallel Bone Chain Merge Preview"
        print_bone_report(
            title,
            report,
            (
                ("selected_roots", "Selected roots"),
                ("source_roots", "Merged source roots"),
                ("skipped_roots", "Skipped roots"),
                ("target_chain", "Target chain"),
                ("merge_pairs", "Merge pairs"),
                ("merged_groups", "Merged groups"),
                ("deleted_bones", "Deleted bones"),
            ),
        )
        self.report({"INFO"}, f"{'Merged' if do_apply else 'Previewed'} {len(report['source_roots'])} parallel chain(s).")
        common.set_status(context, f"Parallel chain merge {'applied' if do_apply else 'preview'}: {len(report['source_roots'])} chain(s)")
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
