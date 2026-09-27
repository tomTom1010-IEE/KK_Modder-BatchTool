"""Profile regression against two read-only scene observations; no bpy needed."""
import importlib
import json
from pathlib import Path
import sys
import types
import unittest

pkg = types.ModuleType('chocolat_rules_test_package')
pkg.__path__ = [str(Path(__file__).resolve().parents[1] / 'kk_vrc_cloth_tools')]
sys.modules[pkg.__name__] = pkg
rules = importlib.import_module(pkg.__name__ + '.vrc_bone_rules')
FIXTURE = json.loads((Path(__file__).parent / 'fixtures/chocolat_rigs.json').read_text())['rigs']


class ChocolatRulesTests(unittest.TestCase):
    def test_shared_names_extend_avatar_membership(self):
        for name in ('Hips', 'Spine', 'Chest', 'Neck', 'Head', 'Shoulder.L', 'Hand.R', 'Foot.L', 'Toe.R', 'LeftEye'):
            avatars = rules.vrc_bone_avatars(name)
            self.assertIn(rules.AVATAR_SHINANO, avatars)
            self.assertIn(rules.AVATAR_CHOCOLAT, avatars)
        for name in ('Breast_L.001', 'ThumbProximal.R'):
            self.assertEqual(rules.vrc_bone_avatars(name), {rules.AVATAR_CHOCOLAT})
        self.assertEqual(rules.vrc_bone_avatars('Breast_1.L'), {rules.AVATAR_SHINANO})
        self.assertNotIn(rules.AVATAR_CHOCOLAT, rules.vrc_bone_avatars('Upper_arm.L'))

    def test_observed_body_weights_have_body_policies(self):
        for rig, data in FIXTURE.items():
            body = 'Body_base.001' if rig.endswith('kaihen') else 'Body_base'
            for name in data['weighted_groups'][body]:
                with self.subTest(rig=rig, bone=name):
                    policy = rules.VRC_WEIGHT_POLICIES[name]
                    self.assertEqual(policy.source_role, 'BODY')
                    self.assertIsNotNone(policy.budget_region)
                    self.assertTrue(policy.preserve_source_deformation)
                    self.assertFalse(policy.graft_source_bone)

    def test_profile_parents_match_both_imported_rigs(self):
        for rig, data in FIXTURE.items():
            known = set(data['parents']) & rules.VRC_BONES_BY_AVATAR[rules.AVATAR_CHOCOLAT]
            rows = [{n: 1. for n in known}]
            bones = {n: {'parent': p, 'use_deform': True} for n, p in data['parents'].items()}
            audit = rules.audit_vrc_weight_roles(rows, bones, {}, avatar=rules.AVATAR_CHOCOLAT)
            self.assertEqual(audit['profile_parent_mismatches'], [], rig)
            self.assertEqual(rules.audit_vrc_weight_roles(rows, bones, {})['profile_parent_mismatches'], [], rig)

    def test_same_name_different_parent_does_not_overwrite_shinano(self):
        self.assertEqual(rules.VRC_STANDARD_BONE_PARENTS['Hand.L'], 'Lower_arm.L')
        self.assertEqual(rules.vrc_bone_parents('Hand.L', rules.AVATAR_SHINANO), {'Lower_arm.L'})
        self.assertEqual(rules.vrc_bone_parents('Hand.L', rules.AVATAR_CHOCOLAT), {'LowerArm.L'})
        audit = rules.audit_vrc_weight_roles([{'Hand.L': 1}], {'Hand.L': {'parent': 'Chest'}}, {})
        self.assertEqual(audit['profile_parent_mismatches'], ['Hand.L'])

    def test_breasts_are_body_helpers_not_humanoid_or_clothing(self):
        for side in ('L', 'R'):
            for name in (f'Breast_{side}_Root', f'Breast_{side}.001', f'Breast_{side}.002'):
                r = rules.VRC_STANDARD_BODY_BONES[name]
                self.assertEqual(r.side, side)
                self.assertEqual(r.role, rules.ROLE_ASSIST)
                self.assertFalse(rules.is_vrc_humanoid_bone(name))
                self.assertTrue(rules.is_vrc_graft_stop_bone(name))
                p = rules.VRC_WEIGHT_POLICIES[name]
                self.assertEqual((p.source_role, p.budget_region), ('BODY', 'TORSO'))
                self.assertEqual(p.reference_anchor, name)

    def test_clothing_hair_and_appendages_are_not_promoted_to_body(self):
        for name in ('Skirt_Root', 'Skirt_1_L', 'Sleeve_L', 'SailorCollar_L', 'Ribbon_Root', 'Choker', 'Hair_Root', 'Tail', 'Ear_L', 'Wing_L'):
            self.assertNotIn(name, rules.VRC_STANDARD_BODY_BONES)
            self.assertFalse(rules.is_vrc_graft_stop_bone(name))

    def test_unweighted_endpoints_are_not_distal_fingers_or_toes(self):
        for name in ('ThumbIntermediate.L_end', 'Foot.R_end', 'Breast_L.002_end', 'LeftEye_end'):
            self.assertEqual(rules.VRC_STANDARD_BODY_BONES[name].role, rules.ROLE_ANCHOR)
            self.assertEqual(rules.VRC_WEIGHT_POLICIES[name].source_role, 'REVIEW')
            self.assertTrue(rules.is_vrc_graft_stop_bone(name))
            for data in FIXTURE.values():
                self.assertFalse(any(name in groups for groups in data['weighted_groups'].values()))
        kaihen = FIXTURE['Chocolat_kaihen']
        self.assertNotIn('ThumbDistal.L', kaihen['parents'])
        self.assertNotIn('Toe.L', kaihen['parents'])

    def test_unverified_underscore_spelling_is_not_globally_guessed(self):
        self.assertNotIn('Breast_R_001', rules.VRC_STANDARD_BODY_BONES)
        self.assertNotIn('Breast_MyClothing', rules.VRC_STANDARD_BODY_BONES)


if __name__ == '__main__':
    unittest.main()
