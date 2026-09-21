"""Blender --background --factory-startup --python tests/test_weight_features.py"""
import sys
import json
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bpy
from kk_vrc_cloth_tools import weight_features as core, weights_features as api


class FeatureWeightsTests(unittest.TestCase):
    def test_reserved_components_cannot_silently_execute(self):
        with self.assertRaises(NotImplementedError):
            core.plan_regions(None,None,None,None,None,None,protected_components={})
        with self.assertRaises(NotImplementedError):
            api.prepare_plan(None,None,None,None,None,protected_components={})
        with self.assertRaises(NotImplementedError):
            api.prepare_from_body(None,None,None,None,None,None,None,protected_components={})

    def fingers(self, rows, enabled=('THUMB_L',)):
        source=core.snapshot(rows,[],{'T':'BODY','A':'BODY','F':'BODY','D':'DYNAMIC'},'topology')
        return core.plan_regions(source,{'T':{'Nt':1},'A':{'Na':1},'F':{'Thumb':1}},
            {'D':{'D':1}},{'Nt','Na','Thumb','Index'},
            {'T':'TORSO','A':'ARM_L','F':'ARM_L'},
            {'Nt':'TORSO','Na':'ARM_L','Thumb':'ARM_L','Index':'ARM_L'},
            {i:{'Thumb':.8,'Index':.1,'Na':.1} for i in range(len(rows))},
            {i:1 for i in range(len(rows))},finger_policy={
                'source_fingers':{'F':'THUMB_L'},
                'target_fingers':{'Thumb':'THUMB_L','Index':'INDEX_L'},
                'enabled':list(enabled),'disabled_map':{'F':{'Na':1}}})

    def test_finger_reservation_and_no_sampled_fingers(self):
        p=self.fingers([{'T':.4,'A':.6,'F':.2,'D':.8}])
        w=p['writes'][0]
        self.assertAlmostEqual(w['Nt'],.2)
        self.assertAlmostEqual(w['Na'],.3)
        self.assertAlmostEqual(w['Thumb'],.1)
        self.assertAlmostEqual(w['D'],.4)
        self.assertNotIn('Index',w)
        self.assertAlmostEqual(p['region_budgets'][0]['ARM_L'],.4)

    def test_disabled_finger_redistributes_without_changing_dynamic(self):
        w=self.fingers([{'A':.3,'F':.1,'D':.6}],enabled=())['writes'][0]
        self.assertAlmostEqual(w['Na'],.4)
        self.assertAlmostEqual(w['D'],.6)
        self.assertNotIn('Thumb',w)

    def test_finger_only_and_zero_source_finger(self):
        p=self.fingers([{'F':2},{'A':1},{'D':1}])
        self.assertEqual(p['writes'][0],{'Thumb':1})
        self.assertEqual(p['writes'][1],{'Na':1})
        self.assertEqual(p['writes'][2],{'D':1})

    def regional(self, rows, samples, **kwargs):
        source=core.snapshot(rows, [], {'T':'BODY','A':'BODY','D':'DYNAMIC'}, 'topology')
        return core.plan_regions(source, {'T':{'Nt':1},'A':{'Na':1}}, {'D':{'D':1}},
                                 {'Nt','Na','St','Sa'}, {'T':'TORSO','A':'ARM_L'},
                                 {'Nt':'TORSO','St':'TORSO','Na':'ARM_L','Sa':'ARM_L'},
                                 samples, {i:1 for i in range(len(rows))}, **kwargs)

    def test_collar_rejects_arm_sample(self):
        p=self.regional([{'T':1}], {0:{'Sa':1}})
        self.assertEqual(p['writes'][0],{'Nt':1})
        self.assertEqual(p['regional_fallback'][0],['TORSO'])

    def test_axilla_separate_budgets_and_dynamic(self):
        p=self.regional([{'T':.6,'A':.4,'D':1}], {0:{'St':.01,'Sa':.99}})
        self.assertAlmostEqual(p['writes'][0]['Nt'],.3)
        self.assertAlmostEqual(p['writes'][0]['Sa'],.2)
        self.assertAlmostEqual(p['writes'][0]['D'],.5)
        self.assertNotIn('St',p['writes'][0])
        q=self.regional([{'T':.6,'A':.4,'D':1}], {0:{'St':.2,'Sa':.8}})
        self.assertAlmostEqual(q['writes'][0]['St'],.3)
        self.assertAlmostEqual(q['writes'][0]['Sa'],.2)

    def test_regions_reject_invalid_semantic_map(self):
        s=core.snapshot([{'T':1}],[],{'T':'BODY'},'topology')
        with self.assertRaises(ValueError):
            core.plan_regions(s,{'T':{'A':1}},{},{'A'},{'T':'TORSO'},{'A':'ARM_R'})
        with self.assertRaises(ValueError):
            core.plan_regions(s,{'T':{'A':1}},{},{'A'},{},{'A':'TORSO'})

    def test_regional_pure_dynamic_and_json(self):
        p=self.regional([{'D':2}], {0:{'Sa':1}})
        self.assertEqual(p['writes'][0],{'D':1})
        self.assertEqual(core.digest(p),core.digest(json.loads(json.dumps(p))))

    def source(self, rows, edges=()):
        return core.snapshot(rows, edges, {'B':'BODY', 'D':'DYNAMIC', 'Mask':'IGNORE', 'Helper':'DROP'}, 'topology')

    def plan(self, source, **kwargs):
        return core.plan(source, {'B':{'NewB':1}}, {'D':{'D':1}}, {'NewB','SampleB'}, **kwargs)

    def test_unnormalized_mass_and_mask(self):
        p=self.plan(self.source([{'B':.6,'D':.8,'Mask':1,'Helper':.5}]))
        self.assertAlmostEqual(p['writes'][0]['NewB'],3/7)
        self.assertAlmostEqual(p['writes'][0]['D'],4/7)
        self.assertNotIn('Mask',p['managed_groups'])

    def test_zero_body_stays_zero(self):
        p=self.plan(self.source([{'D':.7}]),samples={0:{'SampleB':1}},confidence={0:1})
        self.assertEqual(p['writes'][0],{'D':1})

    def test_stable_feature_ignores_mesh_part_and_sampling(self):
        p=self.plan(self.source([{'B':.05,'D':.95}]*3,[(0,1),(1,2)]),
                    samples={i:{'SampleB':1} for i in range(3)},confidence={i:1 for i in range(3)})
        self.assertEqual(set(p['features'].values()),{'STABLE_MIXED'})
        self.assertAlmostEqual(p['writes'][1]['NewB'],.05)
        self.assertNotIn('SampleB',p['writes'][1])

    def test_normalize_candidates_before_blending(self):
        p=self.plan(self.source([{'B':.3,'D':.7}]),samples={0:{'SampleB':1}},confidence={0:.5})
        self.assertAlmostEqual(p['writes'][0]['NewB'],.15)
        self.assertAlmostEqual(p['writes'][0]['SampleB'],.15)

    def test_no_global_mass_substitution(self):
        p=self.plan(self.source([{'B':.2,'D':.8},{'B':.8,'D':.2}],[(0,1)]))
        self.assertAlmostEqual(p['writes'][0]['NewB'],.2)
        self.assertAlmostEqual(p['writes'][1]['NewB'],.8)

    def test_unclassified_and_unmapped_fail(self):
        with self.assertRaises(ValueError):self.source([{'Unknown':1}])
        with self.assertRaises(ValueError):core.plan(self.source([{'B':1}]),{}, {}, {'NewB'})

    def test_snapshot_tamper_and_json_roundtrip(self):
        s=self.source([{'B':1}]*12)
        self.assertEqual(core.digest(self.plan(s)),core.digest(json.loads(json.dumps(self.plan(s)))))
        s['rows'][0]['B']=.4
        with self.assertRaises(ValueError):self.plan(s)

    def test_blender_apply_and_stale_and_idempotence(self):
        m=bpy.data.meshes.new('feature_test');m.from_pydata([(0,0,0),(1,0,0)],[(0,1)],[])
        o=bpy.data.objects.new('feature_test',m);bpy.context.collection.objects.link(o)
        a=bpy.data.armatures.new('feature_rig');rig=bpy.data.objects.new('feature_rig',a);bpy.context.collection.objects.link(rig)
        bpy.context.view_layer.objects.active=rig;rig.select_set(True);bpy.ops.object.mode_set(mode='EDIT')
        for name in ['NewB','D','UnusedJoint']:
            b=a.edit_bones.new(name);b.head=(0,0,0);b.tail=(0,0,1)
        bpy.ops.object.mode_set(mode='OBJECT');o.modifiers.new('rig','ARMATURE').object=rig
        sm=bpy.data.meshes.new('sample_body');sm.from_pydata([(-2,-2,0),(2,-2,0),(0,2,0)],[],[(0,1,2)])
        source=bpy.data.objects.new('sample_body',sm);bpy.context.collection.objects.link(source)
        source.vertex_groups.new(name='NewB').add([0,1,2],1.,'REPLACE')
        for name,weight in [('B',.3),('D',.7),('Mask',.8)]:o.vertex_groups.new(name=name).add([0,1],weight,'REPLACE')
        s=api.capture_snapshot(o,{'B':'BODY','D':'DYNAMIC','Mask':'IGNORE'})
        with self.assertRaises(ValueError):
            api.prepare_plan(o,s,{'B':{'UnusedJoint':1}},{'D':{'D':1}},{'UnusedJoint'},indices=[0],body_source=source)
        p=api.prepare_plan(o,s,{'B':{'NewB':1}},{'D':{'D':1}},{'NewB'},indices=[0],
                           source_regions={'B':'TORSO'},target_regions={'NewB':'TORSO'},body_source=source)
        p=json.loads(json.dumps(p));before=api.read_weights(o)
        api.apply_plan(o,p);after=api.read_weights(o)
        self.assertEqual(after[1],before[1]);self.assertEqual(after[0]['Mask'],before[0]['Mask'])
        self.assertNotIn('B',after[0]);self.assertAlmostEqual(after[0]['NewB'],.3,places=6)
        with self.assertRaises(ValueError):api.apply_plan(o,p)
        p=api.prepare_plan(o,s,{'B':{'NewB':1}},{'D':{'D':1}},{'NewB'},indices=[0],body_source=source);api.apply_plan(o,p)
        self.assertEqual(api.read_weights(o),after)
        o.vertex_groups['D'].lock_weight=True
        p=api.prepare_plan(o,s,{'B':{'NewB':1}},{'D':{'D':1}},{'NewB'},indices=[0],body_source=source)
        with self.assertRaises(ValueError):api.apply_plan(o,p)
        o.vertex_groups['D'].lock_weight=False
        pure=core.snapshot([{'D':1,'Mask':.8}]*2,[(0,1)],{'D':'DYNAMIC','Mask':'IGNORE','B':'BODY'},api.topology(o))
        p=api.prepare_plan(o,pure,{}, {'D':{'D':1}}, {'NewB'},indices=[0],body_source=source);api.apply_plan(o,p)
        self.assertNotIn('NewB',api.read_weights(o)[0])
        self.assertEqual(api.read_weights(o)[0]['D'],1.)
        # Exercise the actual Blender nearest-face candidate, without overwriting
        # the source snapshot or letting it change the preserved body budget.
        before=api.read_weights(o)
        p=api.prepare_from_body(o,s,source,{'B':{'NewB':1}},{'D':{'D':1}},{'NewB'},{0:1.},indices=[0])
        self.assertEqual(api.read_weights(o),before)
        api.apply_plan(o,p)
        self.assertAlmostEqual(api.read_weights(o)[0]['NewB'],.3,places=6)
        p=api.prepare_from_body(o,s,source,{'B':{'NewB':1}},{'D':{'D':1}},{'NewB'},{0:1.},indices=[0])
        source.data.vertices[0].co.x-=.1
        with self.assertRaises(ValueError):api.apply_plan(o,p)


if __name__=='__main__':
    if not unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(FeatureWeightsTests)).wasSuccessful():
        raise RuntimeError('Weight feature tests failed')
