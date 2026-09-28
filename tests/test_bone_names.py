"""Pure suffix compatibility contracts, independent of Blender and rig type."""
import importlib
from pathlib import Path
import sys
import types
import unittest

pkg = types.ModuleType('bone_name_tests')
pkg.__path__ = [str(Path(__file__).resolve().parents[1] / 'kk_vrc_cloth_tools')]
sys.modules[pkg.__name__] = pkg
n = importlib.import_module(pkg.__name__ + '.bone_names')
vrc = importlib.import_module(pkg.__name__ + '.vrc_bone_rules')
kk = importlib.import_module(pkg.__name__ + '.bone_rules')
mmd = importlib.import_module(pkg.__name__ + '.mmd_weight_profiles')


class NameTests(unittest.TestCase):
    def test_only_terminal_separator_changes(self):
        self.assertEqual(n.alternate('Breast_R.001'), 'Breast_R_001')
        self.assertEqual(n.alternate('cf_s_bust03_R'), 'cf_s_bust03.R')
        self.assertEqual(n.alternate('Something.L.001'), 'Something.L_001')
        for name in ('Breast_R_Root', 'Upper_arm', 'Bone_1', 'Bone_01', 'Arm_Left', '左腕', 'Bone.1000'):
            self.assertIsNone(n.alternate(name))
        self.assertIsNone(n.key('Breast_R_002', {'Breast_R.001'}, 'AUTO'))
        self.assertIsNone(n.key('Unknown_L', vrc.VRC_STANDARD_BODY_BONES, 'AUTO'))

    def test_modes_are_directional_and_exact_names_remain_valid(self):
        self.assertEqual(n.key('Hand_L', {'Hand.L'}, 'AUTO'), 'Hand.L')
        self.assertEqual(n.key('Hand_L', {'Hand.L'}, 'UNDERSCORE'), 'Hand.L')
        self.assertIsNone(n.key('Hand_L', {'Hand.L'}, 'DOT'))
        self.assertEqual(n.key('cf_j_hand.L', {'cf_j_hand_L'}, 'DOT'), 'cf_j_hand_L')
        self.assertIsNone(n.key('cf_j_hand.L', {'cf_j_hand_L'}, 'UNDERSCORE'))
        self.assertEqual(n.key('Hand.L', {'Hand.L'}, 'UNDERSCORE'), 'Hand.L')
        for mode in n.MODES:
            self.assertEqual(n.resolve('Hips', {'Hips'}, name_mode=mode), 'Hips')
            self.assertIsNone(n.resolve(None, {'Hips'}, name_mode=mode))

    def test_lookup_returns_canonical_rule_resolve_returns_actual_name(self):
        self.assertEqual(n.lookup(vrc.VRC_WEIGHT_POLICIES,'Breast_R_001').source_role,'BODY')
        self.assertEqual(n.lookup(kk.KK_STANDARD_BODY_BONES,'cf_s_bust03.R').side,'R')
        self.assertEqual(n.resolve('cf_j_hand_L', {'cf_j_hand.L'}), 'cf_j_hand.L')
        self.assertEqual(n.first(['cf_j_hand_L','cf_s_hand_L'], {'cf_s_hand.L'}), 'cf_s_hand.L')
        self.assertNotIn('Breast_R_001',vrc.VRC_STANDARD_BODY_BONES)
        self.assertNotIn('cf_s_bust03.R',kk.KK_STANDARD_BODY_BONES)

    def test_ambiguous_inventories_abort_even_with_exact_hit(self):
        for pair in ({'Hand.L','Hand_L'}, {'Breast_R.001','Breast_R_001'}):
            with self.assertRaisesRegex(ValueError,'Ambiguous'):n.assert_unique(pair)
            for value in pair:
                with self.assertRaisesRegex(ValueError,'Ambiguous'):n.resolve(value,pair)
        n.assert_unique({'Hand.L','Hand.R','Breast_R.001','Breast_R.002'})

    def test_vrc_audit_keeps_real_names_and_checks_real_parent(self):
        rows=[{'LowerArm_L':.8,'Hand_L':.2}]
        bones={'LowerArm_L':{'parent':'UpperArm_L','use_deform':True},
               'Hand_L':{'parent':'LowerArm_L','use_deform':True}}
        roles={'LowerArm_L':'BODY','Hand_L':'IGNORE'}
        report=n.audit_roles(vrc.audit_vrc_weight_roles,rows,bones,roles,vrc.VRC_STANDARD_BODY_BONES)
        self.assertEqual(report['discarded_deform_bones'],['Hand_L'])
        self.assertEqual(report['profile_parent_mismatches'],[])
        self.assertEqual(set(report['known_weighted_bones']),set(roles))

    def test_mmd_japanese_sides_and_numbered_profile_entries(self):
        table,_,_=mmd.load('MMD')
        records=[{'name':'腕_L','parent':'肩_L'}, {'name':'腕_R','parent':'肩_R'}]
        result=mmd.recognize(records,table)
        self.assertEqual(result['腕_L']['budget_region'],'ARM_L')
        self.assertEqual(result['腕_R']['budget_region'],'ARM_R')
        self.assertTrue(all(x['role']=='BODY' for x in result.values()))
        conflict=mmd.recognize(records+[{'name':'腕.L','parent':'肩.L'}],table)
        self.assertEqual(conflict['腕_L']['role'],'REVIEW')
        self.assertEqual(conflict['腕.L']['role'],'REVIEW')
        custom={'entries':{'custom.001':{'kind':'BODY','budget_region':'TORSO'}}}
        self.assertEqual(mmd.recognize([{'name':'custom_001'}],custom)['custom_001']['role'],'BODY')


if __name__ == '__main__':unittest.main()
