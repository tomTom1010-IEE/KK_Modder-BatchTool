"""Run in background Blender; never opens or modifies the user's scene."""
import json
from pathlib import Path
import sys
import unittest
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bpy
import kk_vrc_cloth_tools as addon
from kk_vrc_cloth_tools import graft, workflow as w, vrc_bone_rules as rules
from kk_vrc_cloth_tools import vrc_kk_mapping as mapping, weights_body

FIXTURE = json.loads((Path(__file__).parent / 'fixtures/chocolat_rigs.json').read_text())['rigs']


def armature(name, parents):
    arm = bpy.data.objects.new(name, bpy.data.armatures.new(name))
    bpy.context.collection.objects.link(arm)
    bpy.context.view_layer.objects.active = arm
    arm.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    for i, name in enumerate(parents):
        b = arm.data.edit_bones.new(name)
        b.head = (i * .01, 0, 0)
        b.tail = (i * .01, 0, 1)
    for name, parent in parents.items():
        if parent:
            arm.data.edit_bones[name].parent = arm.data.edit_bones[parent]
    bpy.ops.object.mode_set(mode='OBJECT')
    arm.select_set(False)
    return arm


def mesh(name, rig, groups):
    data = bpy.data.meshes.new(name)
    data.from_pydata([(0, 0, 0), (1, 0, 0), (0, 0, 1)], [], [(0, 1, 2)])
    obj = bpy.data.objects.new(name, data)
    bpy.context.collection.objects.link(obj)
    obj.modifiers.new('Armature', 'ARMATURE').object = rig
    for group in groups:
        obj.vertex_groups.new(name=group).add([0, 1, 2], 1. / len(groups), 'REPLACE')
    return obj


class ChocolatBlenderTests(unittest.TestCase):
    def test_shared_maps_reach_weight_and_graft_consumers(self):
        self.assertEqual(weights_body.VRC_TO_KK_BODY_GROUPS, mapping.VRC_TO_KK_LIMB_TARGETS)
        self.assertEqual(graft.VRC_TO_KK_LIMB_PARENT_MAP, mapping.VRC_TO_KK_LIMB_TARGETS)
        for mode in ('PELVIS', 'WAIST', 'HIGH_WAIST'):
            self.assertEqual(graft.get_parent_attachment_target('Breast_L_Root', mode), graft.get_parent_attachment_target('Breast_root.L', mode))
        self.assertEqual(graft.get_parent_attachment_target('ThumbProximal.L', 'WAIST'), 'cf_j_thumb01_L')

    def test_profile_scan_fills_all_non_breast_body_mappings(self):
        addon.register()
        try:
            target_names = set(mapping.VRC_TO_KK_BODY_TARGETS.values())
            dst = armature('KKMappingTest', {n: None for n in sorted(target_names)})
            for name, data in FIXTURE.items():
                src = armature(name + 'MappingTest', data['parents'])
                body_mesh = 'Body_base.001' if name.endswith('kaihen') else 'Body_base'
                groups = [n for n in data['weighted_groups'][body_mesh] if rules.TAG_VRC_BREAST_CHAIN not in rules.vrc_bone_tags(n)]
                p = bpy.context.scene.kkvrc_weight_workflow
                p.bones.clear(); p.targets.clear(); p.regions.clear(); p.motions.clear()
                p.source = mesh('SourceMappingTest', src, groups)
                p.target = mesh('FittedMappingTest', dst, ['cf_j_spine03'])
                p.body = mesh('BodyMappingTest', dst, sorted(target_names))
                w.scan(p)
                for x in p.bones:
                    self.assertEqual(x.role, 'BODY', x.name)
                    self.assertEqual(x.weight_target, mapping.VRC_TO_KK_BODY_TARGETS[x.name])
                    self.assertEqual(x.pose_target, mapping.VRC_TO_KK_BODY_TARGETS[x.name])
                    if x.finger != 'NONE': x.enabled = True
                config = w.config(p)
                self.assertEqual(set(config['body_map']), set(groups))
                self.assertEqual(w.influence_blender.settings(p)['max_influences'], 4)
        finally:
            addon.unregister()

    def test_body_and_endpoint_bones_never_become_graft_roots(self):
        for data in FIXTURE.values():
            for name, parent in data['parents'].items():
                if rules.is_vrc_graft_stop_bone(name):
                    bone = SimpleNamespace(name=name, parent=SimpleNamespace(name=parent) if parent else None)
                    self.assertFalse(graft.is_candidate_root(bone, {}), name)
        for name, parent in [('Sleeve_L', 'UpperArm.L'), ('Skirt_Root', 'Hips'), ('SailorCollar_L', 'Shoulder.L')]:
            self.assertTrue(graft.is_candidate_root(SimpleNamespace(name=name, parent=SimpleNamespace(name=parent)), {}))

    def test_scanner_uses_chocolat_policy_and_finger_names(self):
        addon.register()
        try:
            src = armature('ChocolatTest', FIXTURE['Chocolat']['parents'])
            dst = armature('KKTest', {'cf_j_spine03': None})
            groups = ['Breast_R.001', 'Breast_R.002', 'UpperArm.L', 'ThumbProximal.L', 'Sleeve_L']
            p = bpy.context.scene.kkvrc_weight_workflow
            p.bones.clear(); p.targets.clear(); p.regions.clear(); p.motions.clear()
            p.source = mesh('Source', src, groups)
            p.target = mesh('Fitted', dst, ['cf_j_spine03'])
            p.body = mesh('Body', dst, ['cf_j_spine03'])
            w.scan(p)
            rows = {x.name: x for x in p.bones}
            for name in groups[:-1]:
                self.assertEqual(rows[name].role, 'BODY', name)
            self.assertEqual(rows['Breast_R.001'].region, 'TORSO')
            self.assertEqual(rows['UpperArm.L'].region, 'ARM_L')
            self.assertEqual(rows['ThumbProximal.L'].finger, 'THUMB_L')
            self.assertEqual(rows['Sleeve_L'].role, 'REVIEW')
        finally:
            addon.unregister()


if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(ChocolatBlenderTests)
    if not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful():
        raise RuntimeError('Chocolat integration tests failed')
