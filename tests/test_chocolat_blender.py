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
