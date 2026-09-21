import importlib,sys,types,unittest
from pathlib import Path

pkg=types.ModuleType('policy_test_package')
pkg.__path__=[str(Path(__file__).resolve().parents[1]/'kk_vrc_cloth_tools')]
sys.modules[pkg.__name__]=pkg
rules=importlib.import_module(pkg.__name__+'.vrc_bone_rules')


class PolicyTests(unittest.TestCase):
    def test_support_is_body_not_grafted_and_uses_parent_frame(self):
        for side in ['L','R']:
            for part in ['Upper','Lower']:
                n=f'{part}_arm_support.{side}'
                p=rules.VRC_WEIGHT_POLICIES[n]
                self.assertEqual(p.source_role,'BODY')
                self.assertEqual(p.budget_region,'ARM_'+side)
                self.assertEqual(p.reference_anchor,f'{part}_arm.{side}')
                self.assertTrue(p.preserve_source_deformation)
                self.assertFalse(p.graft_source_bone)
                self.assertFalse(rules.is_vrc_humanoid_bone(n))

    def test_discard_and_wrong_parent_are_reported(self):
        name='Lower_arm_support.L'
        a=rules.audit_vrc_weight_roles([{name:.8,'Hand.L':.1,'CustomRibbon':.1}],
            {name:{'parent':'Hand.L','use_deform':True}}, {name:'DROP'})
        self.assertEqual(a['discarded_deform_bones'],[name])
        self.assertEqual(a['profile_parent_mismatches'],[name])
        self.assertEqual(a['unknown_weighted_names'],['CustomRibbon'])

    def test_known_breast_chain_preserves_body_influence(self):
        for side in ('L', 'R'):
            policy = rules.VRC_WEIGHT_POLICIES[f'Breast_1.{side}']
            self.assertEqual(policy.source_role, 'BODY')
            self.assertEqual(policy.budget_region, 'TORSO')
            self.assertTrue(policy.preserve_source_deformation)
            self.assertFalse(policy.graft_source_bone)

    def test_source_hand_share_is_not_inflated_by_helper_removal(self):
        rows=[{'Lower_arm.L':.045313,'Lower_arm_support.L':.522921,'Hand.L':.0196639}]
        roles={n:rules.VRC_WEIGHT_POLICIES[n].source_role for n in rows[0]}
        total=sum(w for n,w in rows[0].items() if roles[n]=='BODY')
        self.assertAlmostEqual(rows[0]['Hand.L']/total,.0334478,places=5)

if __name__=='__main__':unittest.main()
