import math

import bpy
from mathutils import Matrix, Vector

from . import common


LEFT_HAND_MAP = {
    "Hand.L": "cf_j_hand_L",
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
}

RIGHT_HAND_MAP = {
    source.replace(".L", ".R"): target.replace("_L", "_R")
    for source, target in LEFT_HAND_MAP.items()
}

LEFT_FINGER_CHAINS = (
    (("Thumb Proximal.L", "Thumb Intermediate.L", "Thumb Distal.L"), ("cf_j_thumb01_L", "cf_j_thumb02_L", "cf_j_thumb03_L")),
    (("Index Proximal.L", "Index Intermediate.L", "Index Distal.L"), ("cf_j_index01_L", "cf_j_index02_L", "cf_j_index03_L")),
    (("Middle Proximal.L", "Middle Intermediate.L", "Middle Distal.L"), ("cf_j_middle01_L", "cf_j_middle02_L", "cf_j_middle03_L")),
    (("Ring Proximal.L", "Ring Intermediate.L", "Ring Distal.L"), ("cf_j_ring01_L", "cf_j_ring02_L", "cf_j_ring03_L")),
    (("Little Proximal.L", "Little Intermediate.L", "Little Distal.L"), ("cf_j_little01_L", "cf_j_little02_L", "cf_j_little03_L")),
)

RIGHT_FINGER_CHAINS = tuple(
    (
        tuple(source.replace(".L", ".R") for source in source_chain),
        tuple(target.replace("_L", "_R") for target in target_chain),
    )
    for source_chain, target_chain in LEFT_FINGER_CHAINS
)

FINGER_CHAINS = LEFT_FINGER_CHAINS + RIGHT_FINGER_CHAINS

PALM_FINGER_ROOTS = {
    "Hand.L": tuple(source_chain[0] for source_chain, _target_chain in LEFT_FINGER_CHAINS),
    "Hand.R": tuple(source_chain[0] for source_chain, _target_chain in RIGHT_FINGER_CHAINS),
    "cf_j_hand_L": tuple(target_chain[0] for _source_chain, target_chain in LEFT_FINGER_CHAINS),
    "cf_j_hand_R": tuple(target_chain[0] for _source_chain, target_chain in RIGHT_FINGER_CHAINS),
}


def get_side_mapping(side):
    if side == "LEFT":
        return LEFT_HAND_MAP
    if side == "RIGHT":
        return RIGHT_HAND_MAP

    mapping = {}
    mapping.update(LEFT_HAND_MAP)
    mapping.update(RIGHT_HAND_MAP)
    return mapping


def get_pose_bone_world_matrix(armature_obj, bone_name):
    pose_bone = armature_obj.pose.bones.get(bone_name)
    if pose_bone is not None:
        return armature_obj.matrix_world @ pose_bone.matrix

    bone = armature_obj.data.bones.get(bone_name)
    if bone is None:
        return None

    return armature_obj.matrix_world @ bone.matrix_local


def get_bone_head_tail_world(armature_obj, bone_name):
    matrix = get_pose_bone_world_matrix(armature_obj, bone_name)
    bone = armature_obj.data.bones.get(bone_name)
    if matrix is None or bone is None:
        return None, None

    head = matrix @ Vector((0.0, 0.0, 0.0))
    tail = matrix @ Vector((0.0, bone.length, 0.0))
    return head, tail


def get_bone_head_world(armature_obj, bone_name):
    matrix = get_pose_bone_world_matrix(armature_obj, bone_name)
    if matrix is None:
        return None
    return matrix.translation


def average_points(points):
    points = [point for point in points if point is not None]
    if not points:
        return None

    total = Vector((0.0, 0.0, 0.0))
    for point in points:
        total += point
    return total / len(points)


def find_finger_chain(bone_name):
    for source_chain, target_chain in FINGER_CHAINS:
        if bone_name in source_chain:
            return source_chain, source_chain.index(bone_name)
        if bone_name in target_chain:
            return target_chain, target_chain.index(bone_name)
    return None, -1


def get_joint_chain_vector(armature_obj, bone_name):
    head = get_bone_head_world(armature_obj, bone_name)
    if head is None:
        return None

    palm_roots = PALM_FINGER_ROOTS.get(bone_name)
    if palm_roots:
        root_center = average_points(get_bone_head_world(armature_obj, root_name) for root_name in palm_roots)
        if root_center is None:
            return None
        vector = root_center - head
        return vector if vector.length > 0.0 else None

    chain, index = find_finger_chain(bone_name)
    if chain is None:
        return None

    if index < len(chain) - 1:
        next_head = get_bone_head_world(armature_obj, chain[index + 1])
        if next_head is None:
            return None
        vector = next_head - head
    elif index > 0:
        previous_head = get_bone_head_world(armature_obj, chain[index - 1])
        if previous_head is None:
            return None
        vector = head - previous_head
    else:
        return None

    return vector if vector.length > 0.0 else None


def get_direction_delta_degrees(vrc_armature, kk_armature, source_name, target_name):
    source_vector = get_joint_chain_vector(vrc_armature, source_name)
    target_vector = get_joint_chain_vector(kk_armature, target_name)
    if source_vector is None or target_vector is None:
        return None

    if source_vector.length <= 0.0 or target_vector.length <= 0.0:
        return None

    return math.degrees(source_vector.angle(target_vector))


def get_head_distance(vrc_armature, kk_armature, source_name, target_name):
    source_head = get_bone_head_world(vrc_armature, source_name)
    target_head = get_bone_head_world(kk_armature, target_name)
    if source_head is None or target_head is None:
        return None
    return (source_head - target_head).length


def build_target_matrix(vrc_armature, kk_armature, source_name, target_name, transform_mode, influence):
    source_matrix_world = get_pose_bone_world_matrix(vrc_armature, source_name)
    source_vector = get_joint_chain_vector(vrc_armature, source_name)
    target_vector = get_joint_chain_vector(kk_armature, target_name)
    target_head = get_bone_head_world(kk_armature, target_name)

    if source_matrix_world is None or source_vector is None or target_vector is None:
        return None

    source_head = source_matrix_world.translation
    delta_rotation = source_vector.rotation_difference(target_vector)
    if influence < 1.0:
        identity = delta_rotation.copy()
        identity.identity()
        delta_rotation = identity.slerp(delta_rotation, influence)

    rotate_around_head = (
        Matrix.Translation(source_head)
        @ delta_rotation.to_matrix().to_4x4()
        @ Matrix.Translation(-source_head)
    )

    target_matrix_world = rotate_around_head @ source_matrix_world
    if transform_mode == "ROTATION_LOCATION" and target_head is not None:
        translation = (target_head - source_head) * influence
        target_matrix_world = Matrix.Translation(translation) @ target_matrix_world

    return vrc_armature.matrix_world.inverted() @ target_matrix_world


def apply_glove_pose_alignment(vrc_armature, kk_armature, mapping, transform_mode, influence):
    influence = max(0.0, min(1.0, influence))
    changed = []
    skipped = []

    if bpy.context.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")

    bpy.ops.object.select_all(action="DESELECT")
    vrc_armature.select_set(True)
    bpy.context.view_layer.objects.active = vrc_armature
    bpy.ops.object.mode_set(mode="POSE")

    for source_name, target_name in mapping.items():
        source_pose = vrc_armature.pose.bones.get(source_name)
        if source_pose is None:
            skipped.append(f"{source_name} missing")
            continue

        if kk_armature.data.bones.get(target_name) is None:
            skipped.append(f"{source_name} -> {target_name} missing")
            continue

        target_matrix = build_target_matrix(
            vrc_armature,
            kk_armature,
            source_name,
            target_name,
            transform_mode,
            influence,
        )
        if target_matrix is None:
            skipped.append(f"{source_name} -> {target_name} unavailable joint vector")
            continue

        source_pose.matrix = target_matrix
        changed.append(f"{source_name} -> {target_name}")

    bpy.ops.object.mode_set(mode="OBJECT")
    return changed, skipped


def reset_glove_pose(vrc_armature, mapping):
    reset = []
    skipped = []

    if bpy.context.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")

    bpy.ops.object.select_all(action="DESELECT")
    vrc_armature.select_set(True)
    bpy.context.view_layer.objects.active = vrc_armature
    bpy.ops.object.mode_set(mode="POSE")

    for source_name in mapping:
        pose_bone = vrc_armature.pose.bones.get(source_name)
        if pose_bone is None:
            skipped.append(source_name)
            continue

        pose_bone.matrix_basis.identity()
        reset.append(source_name)

    bpy.ops.object.mode_set(mode="OBJECT")
    return reset, skipped


def build_report(vrc_armature, kk_armature, mapping):
    mapped = []
    missing_sources = []
    missing_targets = []
    angle_deltas = []
    head_distances = []

    for source_name, target_name in mapping.items():
        if vrc_armature.data.bones.get(source_name) is None:
            missing_sources.append(source_name)
            continue

        if kk_armature.data.bones.get(target_name) is None:
            missing_targets.append(f"{source_name} -> {target_name}")
            continue

        mapped.append(f"{source_name} -> {target_name}")
        angle_delta = get_direction_delta_degrees(vrc_armature, kk_armature, source_name, target_name)
        head_distance = get_head_distance(vrc_armature, kk_armature, source_name, target_name)
        if angle_delta is not None:
            angle_deltas.append(angle_delta)
        if head_distance is not None:
            head_distances.append(head_distance)

    average_angle = sum(angle_deltas) / len(angle_deltas) if angle_deltas else 0.0
    average_distance = sum(head_distances) / len(head_distances) if head_distances else 0.0

    return {
        "vrc": vrc_armature.name,
        "kk": kk_armature.name,
        "mapped": mapped,
        "missing_sources": missing_sources,
        "missing_targets": missing_targets,
        "average_angle": average_angle,
        "average_distance": average_distance,
    }


def print_report(title, report):
    print("\n" + title)
    print("=" * len(title))
    print(f"KK Armature: {report['kk']}")
    print(f"VRC Armature: {report['vrc']}")
    print(f"Mapped bones: {len(report['mapped'])}")
    print(f"Average joint-chain direction delta: {report['average_angle']:.2f} degrees")
    print(f"Average head distance: {report['average_distance']:.6f}")

    if report["mapped"]:
        print("  Mapping:")
        for item in report["mapped"]:
            print(f"    {item}")

    if report["missing_sources"]:
        print(f"  Missing VRC bones: {', '.join(report['missing_sources'])}")

    if report["missing_targets"]:
        print(f"  Missing KK targets: {', '.join(report['missing_targets'])}")


class KKVRC_OT_align_vrc_glove_pose_to_kk(bpy.types.Operator):
    bl_idname = "kkvrc.align_vrc_glove_pose_to_kk"
    bl_label = "Align VRC Glove Hand Pose To KK"
    bl_description = "Pose VRC hand and finger bones toward the matching KK hand bones for glove fitting"
    bl_options = {"REGISTER", "UNDO"}

    action: bpy.props.EnumProperty(
        name="Action",
        items=(
            ("PREVIEW", "Preview", "Report glove hand pose alignment without changing bones"),
            ("APPLY", "Apply", "Apply pose alignment to VRC hand bones"),
            ("RESET", "Reset Hand Pose", "Reset mapped VRC hand pose bones"),
        ),
        default="PREVIEW",
    )

    def execute(self, context):
        props = context.scene.kkvrc_cloth_tools

        try:
            kk_armature, vrc_armature = common.get_selected_armatures(context)
        except Exception as ex:
            self.report({"ERROR"}, str(ex))
            common.set_status(context, str(ex))
            return {"CANCELLED"}

        mapping = get_side_mapping(props.glove_align_side)
        report = build_report(vrc_armature, kk_armature, mapping)

        if self.action == "PREVIEW":
            print_report("VRC Glove Pose Align Preview", report)
            message = f"Previewed glove pose align: {len(report['mapped'])} mapped bone(s)."
            self.report({"INFO"}, message)
            common.set_status(context, message)
            return {"FINISHED"}

        if self.action == "RESET":
            reset, skipped = reset_glove_pose(vrc_armature, mapping)
            print_report("VRC Glove Pose Reset Report", report)
            if skipped:
                print(f"Skipped reset bones: {', '.join(skipped)}")
            message = f"Reset {len(reset)} VRC glove pose bone(s)."
            self.report({"INFO"}, message)
            common.set_status(context, message)
            return {"FINISHED"}

        changed, skipped = apply_glove_pose_alignment(
            vrc_armature,
            kk_armature,
            mapping,
            props.glove_align_transform_mode,
            props.glove_align_influence,
        )
        print_report("VRC Glove Pose Align Applied", report)
        if skipped:
            print(f"Skipped apply bones: {', '.join(skipped)}")

        message = f"Aligned {len(changed)} VRC glove pose bone(s)."
        self.report({"INFO"}, message)
        common.set_status(context, message)
        return {"FINISHED"}
