"""Factory-startup integration; no user scene or installed add-on is touched."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parent))
from test_chocolat_blender import armature, mesh, FIXTURE
import bpy
import kk_vrc_cloth_tools as addon
from kk_vrc_cloth_tools import workflow as w, bone_names as n, weights_features as wf
from kk_vrc_cloth_tools import vrc_kk_mapping as mapping, vrc_bone_rules as vr
from kk_vrc_cloth_tools import graft, weights_body, weights_transfer, shoe_ui
from kk_vrc_cloth_tools import export_cleanup, glove_align


def underscored(name):
    return n.alternate(name) if name and (name.endswith(('.L','.R')) or name.endswith(('.001','.002'))) else name


def dotted_target(name):
    return n.alternate(name) if name and name.endswith(('_L','_R')) else name


class NameBlenderTests(unittest.TestCase):
    def setUp(self):
        bpy.context.window.scene=bpy.data.scenes.new('SuffixTest')
        addon.register()
        self.p=bpy.context.scene.kkvrc_weight_workflow

    def tearDown(self):addon.unregister()

    def inputs(self, source_parents, source_groups, target_names):
        src=armature('SuffixSource',source_parents)
        dst=armature('SuffixTarget',{x:None for x in sorted(target_names)})
        self.p.source=mesh('SuffixGarment',src,source_groups)
        self.p.target=mesh('SuffixFitted',dst,[sorted(target_names)[0]])
        self.p.body=mesh('SuffixBody',dst,sorted(target_names))
        return src,dst

    def test_chocolat_scan_and_six_budget_write_use_actual_names(self):
        fixture=FIXTURE['Chocolat']
        parents={underscored(b):underscored(p) for b,p in fixture['parents'].items()}
        # Include thumb and bilateral chains; preserve numbered breast recognition
        # separately since existing breast mappings still require manual review.
        groups=['UpperArm_L','LowerArm_L','Hand_L','ThumbProximal_L','UpperLeg_R','Foot_R']
        target_names={dotted_target(x) for x in mapping.VRC_TO_KK_BODY_TARGETS.values()}
        src,dst=self.inputs(parents,groups,target_names)
        before=wf.read_weights(self.p.source)
        w.scan(self.p)
        for row in self.p.bones:
            self.assertEqual(row.role,'BODY',row.name)
            self.assertIn(row.weight_target,target_names)
            self.assertIn(row.pose_target,dst.data.bones)
            if row.finger!='NONE':row.enabled=True
        c=w.config(self.p)
        self.assertEqual(set(c['body_map']),set(groups))
        snap=wf.capture_snapshot(self.p.source,c['roles'])
        before_target=wf.stamp(self.p.target)
        proposal=wf.prepare_from_body(self.p.target,snap,self.p.body,c['body_map'],c['dynamic_map'],
            set(c['target_regions']),dict.fromkeys(range(3),1.),source_regions=c['source_regions'],target_regions=c['target_regions'],
            finger_policy=c['finger_policy'],region_modes=c['region_modes'])
        self.assertEqual(wf.stamp(self.p.target),before_target)
        wf.apply_plan(self.p.target,proposal)
        self.assertEqual(wf.read_weights(self.p.source),before)
        for row in wf.read_weights(self.p.target):
            self.assertTrue(set(row)<=target_names)
            self.assertAlmostEqual(sum(row.values()),1.,places=5)
        self.assertEqual(w.dump_settings(self.p)['bone_name_mode'],'AUTO')
        # No canonical phantom group may be created on the target.
        self.assertNotIn('cf_j_arm00_L',self.p.target.vertex_groups)
        old=w.fingerprint(self.p)
        bpy.context.scene.kkvrc_bone_name_mode='DOT'
        self.assertNotEqual(w.fingerprint(self.p),old)

    def test_breast_recognition_and_graft_stop(self):
        src,dst=self.inputs({'Chest':None,'Breast_R_001':'Chest','Breast_R_002':'Breast_R_001',
                             'UpperArm_L':'Chest','Sleeve_L':'UpperArm_L'},
                            ['Breast_R_001','Breast_R_002'],{'cf_s_bust03.R','cf_j_arm00.L'})
        w.scan(self.p)
        self.assertTrue(all(x.role=='BODY' and x.region=='TORSO' for x in self.p.bones))
        self.assertFalse(graft.is_candidate_root(src.data.bones['Breast_R_001'],{}))
        candidates=graft.scan_candidates(src,dst)
        sleeve=next(x for x in candidates if x['name']=='Sleeve_L')
        self.assertEqual(sleeve['target'],'cf_j_arm00.L')
        self.assertTrue(sleeve['target_exists'])

    def test_mmd_underscore_to_dotted_kk_targets(self):
        self.inputs({'腕_L':None,'ひじ_L':'腕_L'},['腕_L','ひじ_L'],{'cf_s_arm01.L','cf_s_forearm01.L','cf_j_arm00.L','cf_j_forearm01.L'})
        self.p.source_profile='MMD'
        w.scan(self.p)
        self.assertEqual(self.p.bones['腕_L'].semantic,'UPPER_ARM_L')
        self.assertTrue(all(x.role=='BODY' and x.region=='ARM_L' for x in self.p.bones))
        self.assertEqual(self.p.bones['腕_L'].pose_target,'cf_j_arm00.L')
        self.assertEqual(set(w.config(self.p)['body_map']),{'腕_L','ひじ_L'})

    def test_manual_mode_and_collision_preflight(self):
        self.inputs({'Hand_L':None},['Hand_L'],{'cf_j_hand_L'})
        bpy.context.scene.kkvrc_bone_name_mode='DOT'
        w.scan(self.p)
        self.assertEqual(self.p.bones['Hand_L'].role,'REVIEW')
        self.p.bones.clear();self.p.targets.clear()
        bpy.context.scene.kkvrc_bone_name_mode='UNDERSCORE'
        w.scan(self.p)
        self.assertEqual(self.p.bones['Hand_L'].role,'BODY')
        self.p.bones.clear();self.p.targets.clear()
        self.inputs({'Hand.L':None,'Hand_L':None},['Hand_L'],{'cf_j_hand_L'})
        with self.assertRaisesRegex(ValueError,'Ambiguous'):w.scan(self.p)
        self.assertEqual(len(self.p.bones),0)

    def test_shoe_targets_and_legacy_remap(self):
        src,dst=self.inputs({'Foot_L':None},['Foot_L'],{'cf_j_leg03.L','cf_j_foot.L','cf_j_toes.L'})
        p=bpy.context.scene.kkvrc_shoes
        p.source=self.p.source;p.target=self.p.target;p.body=self.p.body;p.manual_direction=True
        shoe_ui.scan(p)
        self.assertEqual(p.source_bones['Foot_L'].role,'BODY')
        self.assertEqual(p.sides['L'].foot,'cf_j_foot.L')
        self.assertTrue(p.target_bones['cf_j_foot.L'].enabled)
        self.assertTrue(weights_transfer.is_bnip_group_name('cf_s_bnip025.L'))
        report=weights_body.remap_mesh_vertex_groups(self.p.source,set(dst.data.bones.keys()),False)
        self.assertIn('Foot_L -> cf_j_foot.L',report['remapped'])

    def test_cleanup_and_glove_lookup_preserve_target_body_identity(self):
        target=armature('SuffixCleanup',{'cf_j_hand.L':None,'Ribbon_L':'cf_j_hand.L'})
        self.assertEqual(export_cleanup.discover_roots(target),['Ribbon_L'])
        self.assertIsNotNone(glove_align.get_bone_head_world(target,'cf_j_hand_L'))
        chain,index=glove_align.find_finger_chain('cf_j_thumb01.L')
        self.assertEqual(chain[0],'cf_j_thumb01_L')
        self.assertEqual(index,0)


if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(NameBlenderTests))
    if not result.wasSuccessful():raise RuntimeError('Suffix compatibility tests failed')
