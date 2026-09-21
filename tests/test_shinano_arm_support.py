"""Run with blender --background --factory-startup --python this_file.py."""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from kk_vrc_cloth_tools import graft, vrc_bone_rules as rules


class ShinanoArmSupportTests(unittest.TestCase):
    def test_shinano_breast_chain_is_body_not_clothing(self):
        for side in ('L','R'):
            for base,parent in [('Breast_root','Chest'),('Breast_1',f'Breast_root.{side}'),('Breast_2',f'Breast_1.{side}')]:
                name=f'{base}.{side}'
                rule=rules.VRC_STANDARD_BODY_BONES[name]
                self.assertEqual(rule.avatars,frozenset({rules.AVATAR_SHINANO}))
                self.assertFalse(rules.is_vrc_humanoid_bone(name))
                self.assertTrue(rules.is_vrc_graft_stop_bone(name))
                self.assertIn(name,graft.VRC_HUMANOID_BONES)
                self.assertFalse(graft.is_candidate_root(SimpleNamespace(name=name,parent=SimpleNamespace(name=parent)),{name:[]}))
                self.assertEqual(rules.VRC_WEIGHT_POLICIES[name].source_role,'BODY')
                self.assertEqual(rules.VRC_WEIGHT_POLICIES[name].budget_region,'TORSO')

    def test_body_helpers_are_not_clothing_roots(self):
        for base in ("Upper_arm", "Lower_arm"):
            for side in ("L", "R"):
                name = f"{base}_support.{side}"
                with self.subTest(name=name):
                    rule = rules.VRC_STANDARD_BODY_BONES[name]
                    self.assertEqual(rule.avatars, frozenset({rules.AVATAR_SHINANO}))
                    self.assertEqual(rule.role, rules.ROLE_ASSIST)
                    self.assertIn(rules.TAG_VRC_SHINANO_SUPPORT, rule.tags)
                    self.assertTrue(rules.is_vrc_graft_stop_bone(name))
                    self.assertFalse(rules.is_vrc_humanoid_bone(name))
                    bone = SimpleNamespace(name=name, parent=SimpleNamespace(name=f"{base}.{side}"))
                    self.assertFalse(graft.is_candidate_root(bone, {name: []}))

    def test_sleeve_and_jacket_chains_remain_candidates(self):
        for name, parent in (("Arm_String_L", "Lower_arm.L"), ("Jacket_Root", "Chest")):
            with self.subTest(name=name):
                bone = SimpleNamespace(name=name, parent=SimpleNamespace(name=parent))
                self.assertTrue(graft.is_candidate_root(bone, {name: []}))


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(ShinanoArmSupportTests)
    if not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful():
        raise RuntimeError("Shinano arm-support regression failed")
