"""Shared engineering-level VRC -> KK hints, independent of bpy and solvers.

Names and profile membership are maintained in vrc_bone_rules. One target table
serves both Shinano and Chocolat; no per-avatar transfer implementation. These
are default hints, not proof of target positive-weight admission or equivalent
motion. Breast helpers deliberately retain the existing manual weight/motion
mapping boundary. Graft attachment is a separate operation from weight mapping.
"""
from . import vrc_bone_rules as rules


KK_BODY_SEMANTIC_TARGETS = {
    'HIPS': 'cf_j_hips', 'SPINE': 'cf_j_spine01', 'CHEST': 'cf_j_spine03',
    'NECK': 'cf_j_neck', 'HEAD': 'cf_j_head',
}
for _side in ('L', 'R'):
    for _semantic, _base in {
        'SHOULDER': 'shoulder', 'UPPER_ARM': 'arm00', 'LOWER_ARM': 'forearm01',
        'HAND': 'hand', 'UPPER_LEG': 'thigh00', 'LOWER_LEG': 'leg01',
        'FOOT': 'foot', 'TOES': 'toes',
    }.items():
        KK_BODY_SEMANTIC_TARGETS[f'{_semantic}_{_side}'] = f'cf_j_{_base}_{_side}'
    for _finger in ('THUMB', 'INDEX', 'MIDDLE', 'RING', 'LITTLE'):
        for _index, _joint in enumerate(('PROXIMAL', 'INTERMEDIATE', 'DISTAL'), 1):
            KK_BODY_SEMANTIC_TARGETS[f'{_finger}_{_joint}_{_side}'] = f'cf_j_{_finger.lower()}{_index:02d}_{_side}'

VRC_TO_KK_BODY_TARGETS = {
    name: KK_BODY_SEMANTIC_TARGETS[semantic]
    for name, semantic in rules.VRC_BODY_SEMANTICS.items()
    if name in rules.VRC_STANDARD_BODY_BONES
}
# Preserve the legacy body-remap operator's scope. Torso has separate operators
# and attachment modes; the six-budget scanner opts into the full table.
VRC_TO_KK_LIMB_TARGETS = {
    name: target for name, target in VRC_TO_KK_BODY_TARGETS.items()
    if rules.VRC_BODY_SEMANTICS[name] not in {'HIPS', 'SPINE', 'CHEST'}
}
VRC_BREAST_ROOT_ATTACHMENTS = {
    name: 'cf_d_bust00' for name, rule in rules.VRC_STANDARD_BODY_BONES.items()
    if rules.TAG_VRC_BREAST_CHAIN in rule.tags and rule.parent == 'Chest'
}
