from typing import NamedTuple

from .bone_rules import (
    ROLE_ANCHOR,
    ROLE_ASSIST,
    ROLE_MOTION,
    ROLE_OTHER,
    ROLE_SHAPE,
    REGION_ARM,
    REGION_BREAST,
    REGION_BUTT,
    REGION_HAND,
    REGION_LEG,
    REGION_LOWER_BODY,
    REGION_TORSO,
    TAG_LOWER_BODY_LIMB,
    TAG_LOWER_BODY_WITH_SIRI,
    TAG_TRANSFER_SAFE_ARM,
    TAG_TRANSFER_SAFE_LEG,
    TAG_TRANSFER_SAFE_TORSO,
)


class VrcBoneRule(NamedTuple):
    name: str
    role: str
    regions: frozenset[str]
    side: str | None
    parent: str | None
    tags: frozenset[str]
    avatars: frozenset[str]


AVATAR_GENERIC = "generic"
AVATAR_SHINANO = "shinano"

REGION_EYE = "eye"
REGION_TAIL = "tail"

TAG_VRC_HUMANOID = "vrc_humanoid"
TAG_VRC_SHINANO_BODY = "vrc_shinano_body"
TAG_VRC_SHINANO_SUPPORT = "vrc_shinano_support"
TAG_VRC_AVATAR_APPENDAGE = "vrc_avatar_appendage"
TAG_VRC_REPLACEABLE_BODY = "vrc_replaceable_body"
TAG_VRC_GRAFT_STOP = "vrc_graft_stop"
TAG_VRC_EYE = "vrc_eye"
TAG_VRC_BREAST_CHAIN = "vrc_breast_chain"
TAG_VRC_BUTT = "vrc_butt"
TAG_VRC_ARM_SUPPORT = "vrc_arm_support"


def _vrc_side(name):
    if name.endswith(".L"):
        return "L"
    if name.endswith(".R"):
        return "R"
    return None


def _vrc_rule(role, regions, parent, tags=(), avatars=(AVATAR_SHINANO,), side=None):
    return {
        "role": role,
        "regions": tuple(regions),
        "side": side,
        "parent": parent,
        "tags": tuple(tags),
        "avatars": tuple(avatars),
    }


_VRC_BONE_RULE_DATA = {}


def _add_vrc_bone(name, role, regions, parent, tags=(), avatars=(AVATAR_SHINANO,), side=None):
    _VRC_BONE_RULE_DATA[name] = _vrc_rule(
        role,
        regions,
        parent,
        tags,
        avatars,
        _vrc_side(name) if side is None else side,
    )


def _add_vrc_pair(base_left, base_right, role, regions, parent_left, parent_right, tags=(), avatars=(AVATAR_SHINANO,)):
    _add_vrc_bone(base_left, role, regions, parent_left, tags, avatars, "L")
    _add_vrc_bone(base_right, role, regions, parent_right, tags, avatars, "R")


_GENERIC_VRC_AVATARS = (AVATAR_GENERIC, AVATAR_SHINANO)
_GENERIC_TAGS = (TAG_VRC_HUMANOID, TAG_VRC_REPLACEABLE_BODY, TAG_VRC_GRAFT_STOP)

_add_vrc_bone("Hips", ROLE_MOTION, (REGION_TORSO, REGION_LOWER_BODY), None, _GENERIC_TAGS + (TAG_TRANSFER_SAFE_TORSO, TAG_TRANSFER_SAFE_LEG), _GENERIC_VRC_AVATARS)
_add_vrc_bone("Spine", ROLE_MOTION, (REGION_TORSO,), "Hips", _GENERIC_TAGS + (TAG_TRANSFER_SAFE_TORSO,), _GENERIC_VRC_AVATARS)
_add_vrc_bone("Chest", ROLE_MOTION, (REGION_TORSO,), "Spine", _GENERIC_TAGS + (TAG_TRANSFER_SAFE_TORSO,), _GENERIC_VRC_AVATARS)
_add_vrc_bone("Neck", ROLE_MOTION, (REGION_TORSO,), "Chest", _GENERIC_TAGS + (TAG_TRANSFER_SAFE_TORSO,), _GENERIC_VRC_AVATARS)
_add_vrc_bone("Head", ROLE_MOTION, (REGION_TORSO,), "Neck", _GENERIC_TAGS, _GENERIC_VRC_AVATARS)
_add_vrc_bone("LeftEye", ROLE_MOTION, (REGION_EYE,), "Head", (TAG_VRC_EYE, TAG_VRC_GRAFT_STOP), (AVATAR_SHINANO,), "L")
_add_vrc_bone("RightEye", ROLE_MOTION, (REGION_EYE,), "Head", (TAG_VRC_EYE, TAG_VRC_GRAFT_STOP), (AVATAR_SHINANO,), "R")

for _side in ("L", "R"):
    _add_vrc_bone(f"Shoulder.{_side}", ROLE_MOTION, (REGION_ARM,), "Chest", _GENERIC_TAGS + (TAG_TRANSFER_SAFE_ARM, TAG_TRANSFER_SAFE_TORSO), _GENERIC_VRC_AVATARS, _side)
    _add_vrc_bone(f"Upper_arm.{_side}", ROLE_MOTION, (REGION_ARM,), f"Shoulder.{_side}", _GENERIC_TAGS + (TAG_TRANSFER_SAFE_ARM,), _GENERIC_VRC_AVATARS, _side)
    _add_vrc_bone(f"UpperArm.{_side}", ROLE_MOTION, (REGION_ARM,), f"Shoulder.{_side}", _GENERIC_TAGS + (TAG_TRANSFER_SAFE_ARM,), (AVATAR_GENERIC,), _side)
    _add_vrc_bone(f"Lower_arm.{_side}", ROLE_MOTION, (REGION_ARM,), f"Upper_arm.{_side}", _GENERIC_TAGS + (TAG_TRANSFER_SAFE_ARM,), _GENERIC_VRC_AVATARS, _side)
    _add_vrc_bone(f"LowerArm.{_side}", ROLE_MOTION, (REGION_ARM,), f"UpperArm.{_side}", _GENERIC_TAGS + (TAG_TRANSFER_SAFE_ARM,), (AVATAR_GENERIC,), _side)
    _add_vrc_bone(f"Hand.{_side}", ROLE_MOTION, (REGION_HAND,), f"Lower_arm.{_side}", _GENERIC_TAGS + (TAG_TRANSFER_SAFE_ARM,), _GENERIC_VRC_AVATARS, _side)
    _add_vrc_bone(f"Upper_leg.{_side}", ROLE_MOTION, (REGION_LEG, REGION_LOWER_BODY), "Hips", _GENERIC_TAGS + (TAG_LOWER_BODY_LIMB, TAG_LOWER_BODY_WITH_SIRI, TAG_TRANSFER_SAFE_LEG), _GENERIC_VRC_AVATARS, _side)
    _add_vrc_bone(f"UpperLeg.{_side}", ROLE_MOTION, (REGION_LEG, REGION_LOWER_BODY), "Hips", _GENERIC_TAGS + (TAG_LOWER_BODY_LIMB, TAG_LOWER_BODY_WITH_SIRI, TAG_TRANSFER_SAFE_LEG), (AVATAR_GENERIC,), _side)
    _add_vrc_bone(f"Lower_leg.{_side}", ROLE_MOTION, (REGION_LEG, REGION_LOWER_BODY), f"Upper_leg.{_side}", _GENERIC_TAGS + (TAG_LOWER_BODY_LIMB, TAG_LOWER_BODY_WITH_SIRI, TAG_TRANSFER_SAFE_LEG), _GENERIC_VRC_AVATARS, _side)
    _add_vrc_bone(f"LowerLeg.{_side}", ROLE_MOTION, (REGION_LEG, REGION_LOWER_BODY), f"UpperLeg.{_side}", _GENERIC_TAGS + (TAG_LOWER_BODY_LIMB, TAG_LOWER_BODY_WITH_SIRI, TAG_TRANSFER_SAFE_LEG), (AVATAR_GENERIC,), _side)
    _add_vrc_bone(f"Foot.{_side}", ROLE_MOTION, (REGION_LEG, REGION_LOWER_BODY), f"Lower_leg.{_side}", _GENERIC_TAGS + (TAG_LOWER_BODY_LIMB, TAG_LOWER_BODY_WITH_SIRI, TAG_TRANSFER_SAFE_LEG), _GENERIC_VRC_AVATARS, _side)
    _add_vrc_bone(f"Toe.{_side}", ROLE_MOTION, (REGION_LEG, REGION_LOWER_BODY), f"Foot.{_side}", _GENERIC_TAGS + (TAG_LOWER_BODY_LIMB, TAG_LOWER_BODY_WITH_SIRI, TAG_TRANSFER_SAFE_LEG), _GENERIC_VRC_AVATARS, _side)

    _add_vrc_bone(f"Upper_arm_support.{_side}", ROLE_ASSIST, (REGION_ARM,), f"Upper_arm.{_side}", (TAG_VRC_SHINANO_BODY, TAG_VRC_SHINANO_SUPPORT, TAG_VRC_ARM_SUPPORT, TAG_VRC_REPLACEABLE_BODY, TAG_VRC_GRAFT_STOP, TAG_TRANSFER_SAFE_ARM), (AVATAR_SHINANO,), _side)
    _add_vrc_bone(f"Lower_arm_support.{_side}", ROLE_ASSIST, (REGION_ARM,), f"Lower_arm.{_side}", (TAG_VRC_SHINANO_BODY, TAG_VRC_SHINANO_SUPPORT, TAG_VRC_ARM_SUPPORT, TAG_VRC_REPLACEABLE_BODY, TAG_VRC_GRAFT_STOP, TAG_TRANSFER_SAFE_ARM), (AVATAR_SHINANO,), _side)
    _add_vrc_bone(f"Butt.{_side}", ROLE_ASSIST, (REGION_BUTT, REGION_LOWER_BODY), "Hips", (TAG_VRC_SHINANO_BODY, TAG_VRC_BUTT, TAG_VRC_REPLACEABLE_BODY, TAG_VRC_GRAFT_STOP, TAG_LOWER_BODY_WITH_SIRI, TAG_TRANSFER_SAFE_TORSO, TAG_TRANSFER_SAFE_LEG), (AVATAR_SHINANO,), _side)
    _add_vrc_bone(f"Breast_root.{_side}", ROLE_ASSIST, (REGION_BREAST,), "Chest", (TAG_VRC_SHINANO_BODY, TAG_VRC_BREAST_CHAIN, TAG_VRC_REPLACEABLE_BODY, TAG_VRC_GRAFT_STOP, TAG_TRANSFER_SAFE_TORSO), (AVATAR_SHINANO,), _side)
    _add_vrc_bone(f"Breast_1.{_side}", ROLE_ASSIST, (REGION_BREAST,), f"Breast_root.{_side}", (TAG_VRC_SHINANO_BODY, TAG_VRC_BREAST_CHAIN, TAG_VRC_REPLACEABLE_BODY, TAG_VRC_GRAFT_STOP, TAG_TRANSFER_SAFE_TORSO), (AVATAR_SHINANO,), _side)
    _add_vrc_bone(f"Breast_2.{_side}", ROLE_ASSIST, (REGION_BREAST,), f"Breast_1.{_side}", (TAG_VRC_SHINANO_BODY, TAG_VRC_BREAST_CHAIN, TAG_VRC_REPLACEABLE_BODY, TAG_VRC_GRAFT_STOP, TAG_TRANSFER_SAFE_TORSO), (AVATAR_SHINANO,), _side)

for _side in ("L", "R"):
    _parents = {
        "Thumb Proximal": f"Hand.{_side}",
        "Thumb Intermediate": f"Thumb Proximal.{_side}",
        "Thumb Distal": f"Thumb Intermediate.{_side}",
        "Index Proximal": f"Hand.{_side}",
        "Index Intermediate": f"Index Proximal.{_side}",
        "Index Distal": f"Index Intermediate.{_side}",
        "Middle Proximal": f"Hand.{_side}",
        "Middle Intermediate": f"Middle Proximal.{_side}",
        "Middle Distal": f"Middle Intermediate.{_side}",
        "Ring Proximal": f"Hand.{_side}",
        "Ring Intermediate": f"Ring Proximal.{_side}",
        "Ring Distal": f"Ring Intermediate.{_side}",
        "Little Proximal": f"Hand.{_side}",
        "Little Intermediate": f"Little Proximal.{_side}",
        "Little Distal": f"Little Intermediate.{_side}",
    }
    for _base, _parent in _parents.items():
        _add_vrc_bone(f"{_base}.{_side}", ROLE_MOTION, (REGION_HAND,), _parent, _GENERIC_TAGS + (TAG_TRANSFER_SAFE_ARM,), _GENERIC_VRC_AVATARS, _side)

def _make_vrc_rule(name, data):
    return VrcBoneRule(
        name=name,
        role=data["role"],
        regions=frozenset(data["regions"]),
        side=data["side"],
        parent=data["parent"],
        tags=frozenset(data["tags"]),
        avatars=frozenset(data["avatars"]),
    )


VRC_STANDARD_BODY_BONES = {name: _make_vrc_rule(name, data) for name, data in _VRC_BONE_RULE_DATA.items()}
VRC_STANDARD_BODY_BONE_NAMES = frozenset(VRC_STANDARD_BODY_BONES)
VRC_STANDARD_BONE_PARENTS = {name: rule.parent for name, rule in VRC_STANDARD_BODY_BONES.items()}
VRC_BONES_BY_AVATAR = {
    avatar: frozenset(name for name, rule in VRC_STANDARD_BODY_BONES.items() if avatar in rule.avatars)
    for avatar in (AVATAR_GENERIC, AVATAR_SHINANO)
}
VRC_BONES_BY_REGION = {
    region: frozenset(name for name, rule in VRC_STANDARD_BODY_BONES.items() if region in rule.regions)
    for region in (
        REGION_TORSO,
        REGION_ARM,
        REGION_LEG,
        REGION_BREAST,
        REGION_HAND,
        REGION_LOWER_BODY,
        REGION_BUTT,
        REGION_EYE,
        REGION_TAIL,
    )
}
VRC_BONES_BY_ROLE = {
    role: frozenset(name for name, rule in VRC_STANDARD_BODY_BONES.items() if rule.role == role)
    for role in (ROLE_MOTION, ROLE_SHAPE, ROLE_ASSIST, ROLE_ANCHOR, ROLE_OTHER)
}
VRC_SPECIAL_GROUPS = {
    TAG_VRC_HUMANOID: frozenset(name for name, rule in VRC_STANDARD_BODY_BONES.items() if TAG_VRC_HUMANOID in rule.tags),
    TAG_VRC_SHINANO_BODY: frozenset(name for name, rule in VRC_STANDARD_BODY_BONES.items() if TAG_VRC_SHINANO_BODY in rule.tags),
    TAG_VRC_SHINANO_SUPPORT: frozenset(name for name, rule in VRC_STANDARD_BODY_BONES.items() if TAG_VRC_SHINANO_SUPPORT in rule.tags),
    TAG_VRC_AVATAR_APPENDAGE: frozenset(name for name, rule in VRC_STANDARD_BODY_BONES.items() if TAG_VRC_AVATAR_APPENDAGE in rule.tags),
    TAG_VRC_REPLACEABLE_BODY: frozenset(name for name, rule in VRC_STANDARD_BODY_BONES.items() if TAG_VRC_REPLACEABLE_BODY in rule.tags),
    TAG_VRC_GRAFT_STOP: frozenset(name for name, rule in VRC_STANDARD_BODY_BONES.items() if TAG_VRC_GRAFT_STOP in rule.tags),
    TAG_VRC_BREAST_CHAIN: frozenset(name for name, rule in VRC_STANDARD_BODY_BONES.items() if TAG_VRC_BREAST_CHAIN in rule.tags),
    TAG_VRC_BUTT: frozenset(name for name, rule in VRC_STANDARD_BODY_BONES.items() if TAG_VRC_BUTT in rule.tags),
    TAG_VRC_ARM_SUPPORT: frozenset(name for name, rule in VRC_STANDARD_BODY_BONES.items() if TAG_VRC_ARM_SUPPORT in rule.tags),
}


def is_vrc_standard_body_bone(name, avatar=None):
    rule = VRC_STANDARD_BODY_BONES.get(name)
    if rule is None:
        return False
    return avatar is None or avatar in rule.avatars


def is_vrc_humanoid_bone(name):
    rule = VRC_STANDARD_BODY_BONES.get(name)
    return rule is not None and TAG_VRC_HUMANOID in rule.tags


def is_vrc_replaceable_body_bone(name):
    rule = VRC_STANDARD_BODY_BONES.get(name)
    return rule is not None and TAG_VRC_REPLACEABLE_BODY in rule.tags


def is_vrc_graft_stop_bone(name):
    rule = VRC_STANDARD_BODY_BONES.get(name)
    return rule is not None and TAG_VRC_GRAFT_STOP in rule.tags


def is_vrc_avatar_appendage_bone(name):
    rule = VRC_STANDARD_BODY_BONES.get(name)
    return rule is not None and TAG_VRC_AVATAR_APPENDAGE in rule.tags


def vrc_bone_regions(name):
    rule = VRC_STANDARD_BODY_BONES.get(name)
    return rule.regions if rule else frozenset()


def vrc_bone_tags(name):
    rule = VRC_STANDARD_BODY_BONES.get(name)
    return rule.tags if rule else frozenset()


def vrc_bone_avatars(name):
    rule = VRC_STANDARD_BODY_BONES.get(name)
    return rule.avatars if rule else frozenset()

