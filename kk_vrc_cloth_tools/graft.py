import fnmatch
from collections import deque

import bpy

from . import common


PRIORITY_1_NAME_OVERRIDES = {
    "CYCRLegRoot": "cf_j_waist02",
    "CYCRBowknotRoot": "cf_j_spine03",
}

PRIORITY_2_NAME_OVERRIDES = {
    "Breast_root.L": "cf_d_bust00",
    "Breast_root.R": "cf_d_bust00",
}

PARENT_ATTACHMENT_MAPS = {
    "PELVIS": {
        "Hips": "cf_j_hips",
        "Spine": "cf_j_spine01",
        "Chest": "cf_j_spine03",
        "Breast_root.L": "cf_d_bust00",
        "Breast_root.R": "cf_d_bust00",
    },
    "WAIST": {
        "Hips": "cf_j_waist02",
        "Spine": "cf_j_waist01",
        "Chest": "cf_j_spine03",
        "Breast_root.L": "cf_d_bust00",
        "Breast_root.R": "cf_d_bust00",
    },
    "HIGH_WAIST": {
        "Hips": "cf_j_waist01",
        "Spine": "cf_j_spine01",
        "Chest": "cf_j_spine03",
        "Breast_root.L": "cf_d_bust00",
        "Breast_root.R": "cf_d_bust00",
    },
}

VRC_TO_KK_LIMB_PARENT_MAP = {
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

REPORT_ONLY_PATTERNS = (
    "CYCRGlove_*",
    "CYCRBoots_*",
    "CRYCRCrownRoot",
    "*_support.*",
    "*support*",
    "Thumb Proximal.*",
    "Index Proximal.*",
    "Middle Proximal.*",
    "Ring Proximal.*",
    "Little Proximal.*",
    "Toe.*",
)

VRC_HUMANOID_BONES = {
    "Hips",
    "Spine",
    "Chest",
    "Neck",
    "Head",
    "Shoulder.L",
    "Shoulder.R",
    "Upper_arm.L",
    "Upper_arm.R",
    "Lower_arm.L",
    "Lower_arm.R",
    "Upper_arm_support.L",
    "Upper_arm_support.R",
    "Lower_arm_support.L",
    "Lower_arm_support.R",
    "Hand.L",
    "Hand.R",
    "Upper_leg.L",
    "Upper_leg.R",
    "Lower_leg.L",
    "Lower_leg.R",
    "Foot.L",
    "Foot.R",
    "Toe.L",
    "Toe.R",
    "Thumb Proximal.L",
    "Thumb Intermediate.L",
    "Thumb Distal.L",
    "Index Proximal.L",
    "Index Intermediate.L",
    "Index Distal.L",
    "Middle Proximal.L",
    "Middle Intermediate.L",
    "Middle Distal.L",
    "Ring Proximal.L",
    "Ring Intermediate.L",
    "Ring Distal.L",
    "Little Proximal.L",
    "Little Intermediate.L",
    "Little Distal.L",
    "Thumb Proximal.R",
    "Thumb Intermediate.R",
    "Thumb Distal.R",
    "Index Proximal.R",
    "Index Intermediate.R",
    "Index Distal.R",
    "Middle Proximal.R",
    "Middle Intermediate.R",
    "Middle Distal.R",
    "Ring Proximal.R",
    "Ring Intermediate.R",
    "Ring Distal.R",
    "Little Proximal.R",
    "Little Intermediate.R",
    "Little Distal.R",
}

GRAFTABLE_SOURCE_PARENTS = set(PARENT_ATTACHMENT_MAPS["WAIST"]) | set(VRC_TO_KK_LIMB_PARENT_MAP)


def get_bone_map(armature_obj):
    return {bone.name: bone for bone in armature_obj.data.bones}


def get_children_map(armature_obj):
    children = {}
    for bone in armature_obj.data.bones:
        children.setdefault(bone.name, [])
        if bone.parent:
            children.setdefault(bone.parent.name, []).append(bone.name)
    return children


def collect_chain_names(children_map, root_name):
    names = []
    queue = deque([root_name])
    while queue:
        name = queue.popleft()
        names.append(name)
        for child_name in children_map.get(name, []):
            queue.append(child_name)
    return names


def matches_any_pattern(name, patterns):
    return any(fnmatch.fnmatchcase(name, pattern) for pattern in patterns)


def is_priority_root(name):
    return name in PRIORITY_1_NAME_OVERRIDES or name in PRIORITY_2_NAME_OVERRIDES


def get_parent_attachment_target(parent_name, attachment_mode):
    torso_target = PARENT_ATTACHMENT_MAPS.get(attachment_mode, PARENT_ATTACHMENT_MAPS["WAIST"]).get(parent_name)
    if torso_target:
        return torso_target
    return VRC_TO_KK_LIMB_PARENT_MAP.get(parent_name)


def classify_candidate(name, parent_name, attachment_mode):
    if name in PRIORITY_1_NAME_OVERRIDES:
        return 1, PRIORITY_1_NAME_OVERRIDES[name], "priority 1 name override"
    if name in PRIORITY_2_NAME_OVERRIDES:
        return 2, PRIORITY_2_NAME_OVERRIDES[name], "priority 2 name override"
    parent_target = get_parent_attachment_target(parent_name, attachment_mode)
    if parent_target:
        if parent_name in {"Breast_root.L", "Breast_root.R"}:
            return 2, parent_target, "priority 2 parent-derived"
        if parent_name in VRC_TO_KK_LIMB_PARENT_MAP:
            return 1, parent_target, "priority 1 limb parent-derived"
        return 1, parent_target, "priority 1 parent-derived"
    if matches_any_pattern(name, REPORT_ONLY_PATTERNS):
        return 3, None, "priority 3 report-only"
    return 0, None, "unmapped"


def is_candidate_root(bone, children_map):
    if bone.name in VRC_HUMANOID_BONES:
        return False
    if is_priority_root(bone.name):
        return True
    if matches_any_pattern(bone.name, REPORT_ONLY_PATTERNS):
        return True
    if bone.parent and bone.parent.name in GRAFTABLE_SOURCE_PARENTS:
        return True
    return False


def parent_is_inside_candidate(parent_name, candidate_roots, children_map):
    if not parent_name:
        return False
    for root_name in candidate_roots:
        if parent_name in collect_chain_names(children_map, root_name):
            return True
    return False


def scan_candidates(vrc_armature, kk_armature, attachment_mode="WAIST"):
    children_map = get_children_map(vrc_armature)
    kk_bones = get_bone_map(kk_armature)
    root_names = {bone.name for bone in vrc_armature.data.bones if is_candidate_root(bone, children_map)}
    roots = []

    for bone_name in sorted(root_names):
        bone = vrc_armature.data.bones.get(bone_name)
        if bone is None:
            continue
        parent_name = bone.parent.name if bone.parent else None
        if parent_is_inside_candidate(parent_name, root_names - {bone_name}, children_map):
            continue
        priority, target_name, reason = classify_candidate(bone_name, parent_name, attachment_mode)
        chain = collect_chain_names(children_map, bone_name)
        roots.append(
            {
                "name": bone_name,
                "source_parent": parent_name,
                "priority": priority,
                "target": target_name,
                "target_exists": target_name in kk_bones if target_name else False,
                "already_exists": any(name in kk_bones for name in chain),
                "chain_count": len(chain),
                "reason": reason,
                "chain": chain,
            }
        )
    return roots


def get_selected_meshes_for_graft(context):
    meshes = [obj for obj in context.selected_objects if common.is_mesh(obj)]
    if not meshes:
        raise RuntimeError("Select at least one clothing mesh when using selected-mesh-only graft.")
    return meshes


def mesh_uses_armature(mesh_obj, armature_obj):
    if mesh_obj.parent == armature_obj:
        return True
    for modifier in mesh_obj.modifiers:
        if modifier.type == "ARMATURE" and modifier.object == armature_obj:
            return True
    return False


def collect_weighted_vertex_group_names(meshes):
    names = set()
    for mesh in meshes:
        for vertex_group in mesh.vertex_groups:
            if common.group_has_weights(mesh, vertex_group.index):
                names.add(vertex_group.name)
    return names


def filter_candidates_by_mesh_weights(candidates, weighted_group_names):
    if not weighted_group_names:
        return []

    filtered = []
    for candidate in candidates:
        if any(name in weighted_group_names for name in candidate["chain"]):
            filtered.append(candidate)
    return filtered


def copy_chains_to_kk(kk_armature, vrc_armature, candidates):
    if bpy.context.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")

    source_bones = vrc_armature.data.bones
    source_to_kk_world = kk_armature.matrix_world.inverted() @ vrc_armature.matrix_world

    bpy.ops.object.select_all(action="DESELECT")
    kk_armature.select_set(True)
    bpy.context.view_layer.objects.active = kk_armature
    bpy.ops.object.mode_set(mode="EDIT")

    edit_bones = kk_armature.data.edit_bones
    copied = []
    name_map = {}

    try:
        for candidate in candidates:
            root_name = candidate["name"]
            target_name = candidate["target"]
            if target_name not in edit_bones:
                raise RuntimeError(f"Target KK bone not found: {target_name} for {root_name}")

            for source_name in candidate["chain"]:
                source_bone = source_bones.get(source_name)
                if source_bone is None:
                    raise RuntimeError(f"Source VRC bone not found: {source_name}")
                if source_name in edit_bones:
                    raise RuntimeError(f"KK Armature already has a bone named {source_name}; vertex groups would become ambiguous.")

                new_bone = edit_bones.new(source_name)
                new_bone.head = source_to_kk_world @ source_bone.head_local
                new_bone.tail = source_to_kk_world @ source_bone.tail_local
                if (new_bone.tail - new_bone.head).length < 0.0001:
                    fallback = source_to_kk_world.to_3x3() @ source_bone.vector
                    if fallback.length < 0.0001:
                        fallback = source_to_kk_world.to_3x3() @ source_bone.y_axis
                    new_bone.tail = new_bone.head + fallback.normalized() * 0.01
                new_bone.roll = getattr(source_bone, "roll", 0.0)
                new_bone.use_connect = False
                new_bone.use_deform = source_bone.use_deform
                name_map[source_name] = source_name
                copied.append(source_name)

            for source_name in candidate["chain"]:
                source_bone = source_bones.get(source_name)
                new_bone = edit_bones[name_map[source_name]]
                if source_name == root_name:
                    new_bone.parent = edit_bones[target_name]
                elif source_bone.parent and source_bone.parent.name in name_map:
                    new_bone.parent = edit_bones[name_map[source_bone.parent.name]]
    finally:
        bpy.ops.object.mode_set(mode="OBJECT")

    return copied


def retarget_armature_modifiers(vrc_armature, kk_armature, meshes=None):
    changed = []
    objects = meshes if meshes is not None else bpy.data.objects
    for obj in objects:
        if obj.type != "MESH":
            continue
        for modifier in obj.modifiers:
            if modifier.type == "ARMATURE" and modifier.object == vrc_armature:
                modifier.object = kk_armature
                changed.append(obj.name)
    return sorted(set(changed))


def reparent_vrc_meshes_to_kk(vrc_armature, kk_armature, meshes=None):
    changed = []
    objects = meshes if meshes is not None else bpy.data.objects
    for obj in objects:
        if obj.type != "MESH" or obj.parent != vrc_armature:
            continue
        world_matrix = obj.matrix_world.copy()
        obj.parent = kk_armature
        obj.matrix_world = world_matrix
        changed.append(obj.name)
    return sorted(changed)


def format_candidate(candidate):
    target = candidate["target"] or "(report only)"
    status = []
    if candidate["target"] and not candidate["target_exists"]:
        status.append("missing target")
    if candidate["already_exists"]:
        status.append("already exists in KK")
    suffix = f" [{', '.join(status)}]" if status else ""
    return (
        f"P{candidate['priority']} {candidate['name']} -> {target} "
        f"({candidate['chain_count']} bones, parent={candidate['source_parent']}, {candidate['reason']}){suffix}"
    )


def report_candidates(title, candidates):
    print("\n" + title)
    print("=" * len(title))
    if not candidates:
        print("(none)")
        return
    for candidate in candidates:
        print(format_candidate(candidate))


class KKVRC_OT_graft_clothes_bones(bpy.types.Operator):
    bl_idname = "kkvrc.graft_clothes_bones"
    bl_label = "Graft Clothes Bones"
    bl_description = "Copy selected VRC clothes bone chains into the active KK Armature"
    bl_options = {"REGISTER", "UNDO"}

    action: bpy.props.EnumProperty(
        items=(
            ("SCAN", "Scan Preview", ""),
            ("APPLY", "Apply", ""),
            ("REPORT", "Report Unattached Roots", ""),
        ),
        default="SCAN",
        options={"HIDDEN"},
    )

    def execute(self, context):
        props = context.scene.kkvrc_cloth_tools
        try:
            kk_armature, vrc_armature = common.get_selected_armatures(context)
            candidates = scan_candidates(vrc_armature, kk_armature, props.graft_attachment_mode)
            selected_meshes = []
            weighted_group_names = set()
            if props.graft_selected_meshes_only:
                selected_meshes = get_selected_meshes_for_graft(context)
                selected_meshes = [mesh for mesh in selected_meshes if mesh_uses_armature(mesh, vrc_armature)]
                if not selected_meshes:
                    raise RuntimeError("Selected mesh(es) are not parented to, or modified by, the VRC source Armature.")
                weighted_group_names = collect_weighted_vertex_group_names(selected_meshes)
                candidates = filter_candidates_by_mesh_weights(candidates, weighted_group_names)
        except Exception as ex:
            self.report({"ERROR"}, str(ex))
            common.set_status(context, f"Graft failed: {ex}")
            return {"CANCELLED"}

        selected = [
            candidate
            for candidate in candidates
            if (
                (candidate["priority"] == 1 and props.graft_include_priority_1)
                or (candidate["priority"] == 2 and props.graft_include_priority_2)
            )
        ]
        selected = [
            candidate
            for candidate in selected
            if candidate["target"] and candidate["target_exists"] and not candidate["already_exists"]
        ]

        if self.action == "SCAN":
            report_candidates("Auto Graft Preview", candidates)
            if props.graft_selected_meshes_only:
                print(f"Selected-mesh-only mode: ON")
                print(f"Selected meshes: {', '.join(mesh.name for mesh in selected_meshes)}")
                print(f"Weighted groups on selected meshes: {len(weighted_group_names)}")
            self.report({"INFO"}, f"Found {len(candidates)} candidate root(s). See console.")
            common.set_status(context, f"Graft preview: {len(candidates)} candidate root(s)")
            return {"FINISHED"}

        if self.action == "REPORT":
            selected_names = {candidate["name"] for candidate in selected}
            lines = [candidate for candidate in candidates if candidate["name"] not in selected_names]
            report_candidates("Unattached Top-Level Clothes Roots", lines)
            self.report({"INFO"}, f"Reported {len(lines)} unattached top-level root(s). See console.")
            common.set_status(context, f"Graft report: {len(lines)} unattached root(s)")
            return {"FINISHED"}

        if not selected:
            if not props.graft_selected_meshes_only:
                self.report({"WARNING"}, "No selected candidates to graft. Run Scan Preview first.")
                common.set_status(context, "Graft apply skipped: no selected candidates")
                return {"CANCELLED"}

        try:
            copied = copy_chains_to_kk(kk_armature, vrc_armature, selected) if selected else []
            scope_meshes = selected_meshes if props.graft_selected_meshes_only else None
            changed_meshes = retarget_armature_modifiers(vrc_armature, kk_armature, scope_meshes)
            reparented_meshes = reparent_vrc_meshes_to_kk(vrc_armature, kk_armature, scope_meshes)
            if props.graft_delete_vrc_armature:
                bpy.data.objects.remove(vrc_armature, do_unlink=True)
        except Exception as ex:
            self.report({"ERROR"}, str(ex))
            common.set_status(context, f"Graft failed: {ex}")
            return {"CANCELLED"}

        print("\nAuto Graft Applied")
        print("==================")
        print(f"Grafted roots: {', '.join(candidate['name'] for candidate in selected)}")
        print(f"Copied bones: {len(copied)}")
        print(f"Retargeted meshes: {', '.join(changed_meshes) if changed_meshes else '(none)'}")
        print(f"Reparented meshes: {', '.join(reparented_meshes) if reparented_meshes else '(none)'}")
        print(f"Deleted source Armature: {props.graft_delete_vrc_armature}")
        print(f"Selected-mesh-only mode: {props.graft_selected_meshes_only}")
        self.report({"INFO"}, f"Grafted {len(selected)} root(s), copied {len(copied)} bone(s).")
        common.set_status(context, f"Grafted {len(selected)} root(s), copied {len(copied)} bone(s)")
        return {"FINISHED"}
