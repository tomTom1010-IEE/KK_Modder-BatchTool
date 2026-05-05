import fnmatch
from collections import deque

import bpy


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
}

TORSO_SOURCE_PARENTS = {
    "Hips",
    "Spine",
    "Chest",
    "Breast_root.L",
    "Breast_root.R",
}


def is_armature(obj):
    return obj is not None and obj.type == "ARMATURE"


def get_selected_armatures():
    kk_armature = bpy.context.view_layer.objects.active
    if not is_armature(kk_armature):
        raise RuntimeError("Make the KK target Armature the active object.")

    selected = [obj for obj in bpy.context.selected_objects if is_armature(obj)]
    if len(selected) != 2:
        raise RuntimeError("Select exactly two Armatures: active = KK target, other selected = VRC source.")

    vrc_armatures = [obj for obj in selected if obj != kk_armature]
    if len(vrc_armatures) != 1:
        raise RuntimeError("Could not identify the VRC source Armature.")

    return kk_armature, vrc_armatures[0]


def get_bone_map(armature_obj):
    return {bone.name: bone for bone in armature_obj.data.bones}


def get_children_map(armature_obj):
    children = {}
    for bone in armature_obj.data.bones:
        children.setdefault(bone.name, [])
        if bone.parent:
            children.setdefault(bone.parent.name, []).append(bone.name)
    return children


def has_descendants(children_map, bone_name):
    return bool(children_map.get(bone_name))


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
    return PARENT_ATTACHMENT_MAPS.get(attachment_mode, PARENT_ATTACHMENT_MAPS["WAIST"]).get(parent_name)


def classify_candidate(name, parent_name, attachment_mode):
    if name in PRIORITY_1_NAME_OVERRIDES:
        return 1, PRIORITY_1_NAME_OVERRIDES[name], "priority 1 name override"
    if name in PRIORITY_2_NAME_OVERRIDES:
        return 2, PRIORITY_2_NAME_OVERRIDES[name], "priority 2 name override"
    if matches_any_pattern(name, REPORT_ONLY_PATTERNS):
        return 3, None, "priority 3 report-only"
    parent_target = get_parent_attachment_target(parent_name, attachment_mode)
    if parent_target:
        if parent_name in {"Breast_root.L", "Breast_root.R"}:
            return 2, parent_target, "priority 2 parent-derived"
        return 1, parent_target, "priority 1 parent-derived"
    return 0, None, "unmapped"


def is_candidate_root(bone, children_map):
    if bone.name in VRC_HUMANOID_BONES:
        return False
    if is_priority_root(bone.name):
        return True
    if matches_any_pattern(bone.name, REPORT_ONLY_PATTERNS):
        return True
    if bone.parent and bone.parent.name in TORSO_SOURCE_PARENTS and has_descendants(children_map, bone.name):
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

    roots = []
    root_names = set()

    for bone in vrc_armature.data.bones:
        if not is_candidate_root(bone, children_map):
            continue

        root_names.add(bone.name)

    for bone_name in sorted(root_names):
        bone = vrc_armature.data.bones.get(bone_name)
        if bone is None:
            continue

        parent_name = bone.parent.name if bone.parent else None
        if parent_is_inside_candidate(parent_name, root_names - {bone_name}, children_map):
            continue

        priority, target_name, reason = classify_candidate(bone_name, parent_name, attachment_mode)
        chain = collect_chain_names(children_map, bone_name)
        target_exists = target_name in kk_bones if target_name else False
        already_exists = any(name in kk_bones for name in chain)

        roots.append(
            {
                "name": bone_name,
                "source_parent": parent_name,
                "priority": priority,
                "target": target_name,
                "target_exists": target_exists,
                "already_exists": already_exists,
                "chain_count": len(chain),
                "reason": reason,
                "chain": chain,
            }
        )

    return roots


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

    return copied, name_map


def retarget_armature_modifiers(vrc_armature, kk_armature):
    changed = []
    for obj in bpy.data.objects:
        if obj.type != "MESH":
            continue

        for modifier in obj.modifiers:
            if modifier.type == "ARMATURE" and modifier.object == vrc_armature:
                modifier.object = kk_armature
                changed.append(obj.name)

    return sorted(set(changed))


def reparent_vrc_meshes_to_kk(vrc_armature, kk_armature):
    changed = []
    for obj in bpy.data.objects:
        if obj.type != "MESH" or obj.parent != vrc_armature:
            continue

        world_matrix = obj.matrix_world.copy()
        obj.parent = kk_armature
        obj.matrix_world = world_matrix
        changed.append(obj.name)

    return sorted(changed)


def delete_source_armature(vrc_armature):
    bpy.data.objects.remove(vrc_armature, do_unlink=True)


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


def report_to_console(title, lines):
    print("\n" + title)
    print("=" * len(title))
    if not lines:
        print("(none)")
        return

    for line in lines:
        print(line)


class KKMODS_OT_auto_graft_vrc_to_kk(bpy.types.Operator):
    bl_idname = "kkmods.auto_graft_vrc_to_kk"
    bl_label = "Auto Graft VRC Clothes Bones To KK"
    bl_description = "Copy selected VRC clothes bone chains into the active KK Armature"
    bl_options = {"REGISTER", "UNDO"}

    include_priority_1: bpy.props.BoolProperty(
        name="Priority 1: torso/skirt roots",
        default=True,
    )
    include_priority_2: bpy.props.BoolProperty(
        name="Priority 2: breast/upper-clothes roots",
        default=False,
    )
    delete_vrc_armature: bpy.props.BoolProperty(
        name="Delete VRC source Armature after graft",
        default=True,
    )
    attachment_mode: bpy.props.EnumProperty(
        name="Parent-derived attach mode",
        items=(
            ("PELVIS", "Pelvis / Low Skirt", "Attach Hips-parented clothes roots to cf_j_hips"),
            ("WAIST", "Waist Skirt", "Attach Hips-parented clothes roots to lower KK waist"),
            ("HIGH_WAIST", "High Waist / Dress", "Attach Hips-parented clothes roots to upper KK waist"),
        ),
        default="WAIST",
    )

    action: bpy.props.EnumProperty(
        name="Action",
        items=(
            ("SCAN", "Scan Preview", "Preview candidates without changing the scene"),
            ("APPLY", "Apply Selected Priorities", "Copy selected priority chains to KK and retarget mesh modifiers"),
            ("REPORT", "Report Unattached Roots", "Print top-level roots that were not grafted"),
        ),
        default="SCAN",
    )

    def execute(self, context):
        try:
            kk_armature, vrc_armature = get_selected_armatures()
            candidates = scan_candidates(vrc_armature, kk_armature, self.attachment_mode)
        except Exception as ex:
            self.report({"ERROR"}, str(ex))
            return {"CANCELLED"}

        selected = [
            candidate
            for candidate in candidates
            if (
                (candidate["priority"] == 1 and self.include_priority_1)
                or (candidate["priority"] == 2 and self.include_priority_2)
            )
        ]

        selected = [
            candidate
            for candidate in selected
            if candidate["target"] and candidate["target_exists"] and not candidate["already_exists"]
        ]

        if self.action == "SCAN":
            lines = [format_candidate(candidate) for candidate in candidates]
            report_to_console("Auto Graft Preview", lines)
            self.report({"INFO"}, f"Found {len(candidates)} candidate root(s). See console.")
            return {"FINISHED"}

        if self.action == "REPORT":
            selected_names = {candidate["name"] for candidate in selected}
            lines = [
                format_candidate(candidate)
                for candidate in candidates
                if candidate["name"] not in selected_names
            ]
            report_to_console("Unattached Top-Level Clothes Roots", lines)
            self.report({"INFO"}, f"Reported {len(lines)} unattached top-level root(s). See console.")
            return {"FINISHED"}

        if not selected:
            self.report({"WARNING"}, "No selected candidates to graft. Run Scan Preview first.")
            return {"CANCELLED"}

        try:
            copied, _name_map = copy_chains_to_kk(kk_armature, vrc_armature, selected)
            changed_meshes = retarget_armature_modifiers(vrc_armature, kk_armature)
            reparented_meshes = reparent_vrc_meshes_to_kk(vrc_armature, kk_armature)
            if self.delete_vrc_armature:
                delete_source_armature(vrc_armature)
        except Exception as ex:
            self.report({"ERROR"}, str(ex))
            return {"CANCELLED"}

        report_to_console(
            "Auto Graft Applied",
            [
                f"Grafted roots: {', '.join(candidate['name'] for candidate in selected)}",
                f"Copied bones: {len(copied)}",
                f"Retargeted meshes: {', '.join(changed_meshes) if changed_meshes else '(none)'}",
                f"Reparented meshes: {', '.join(reparented_meshes) if reparented_meshes else '(none)'}",
                f"Deleted source Armature: {self.delete_vrc_armature}",
            ],
        )
        self.report({"INFO"}, f"Grafted {len(selected)} root(s), copied {len(copied)} bone(s).")
        return {"FINISHED"}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=520)


class KKMODS_MT_auto_tools(bpy.types.Menu):
    bl_idname = "KKMODS_MT_auto_tools"
    bl_label = "KK Mods"

    def draw(self, context):
        self.layout.operator(KKMODS_OT_auto_graft_vrc_to_kk.bl_idname)


def menu_func(self, context):
    self.layout.menu(KKMODS_MT_auto_tools.bl_idname)


def register():
    bpy.utils.register_class(KKMODS_OT_auto_graft_vrc_to_kk)
    bpy.utils.register_class(KKMODS_MT_auto_tools)
    bpy.types.TOPBAR_MT_editor_menus.append(menu_func)
    bpy.types.VIEW3D_MT_object.append(menu_func)


def safe_unregister_class(cls):
    try:
        bpy.utils.unregister_class(cls)
    except Exception:
        pass


def unregister():
    try:
        bpy.types.TOPBAR_MT_editor_menus.remove(menu_func)
    except Exception:
        pass

    try:
        bpy.types.VIEW3D_MT_object.remove(menu_func)
    except Exception:
        pass

    safe_unregister_class(KKMODS_MT_auto_tools)
    safe_unregister_class(KKMODS_OT_auto_graft_vrc_to_kk)


if __name__ == "__main__":
    unregister()
    register()
    bpy.ops.kkmods.auto_graft_vrc_to_kk("INVOKE_DEFAULT")
