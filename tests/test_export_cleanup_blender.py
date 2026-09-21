"""Run with Blender --background --factory-startup --python this_file."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bpy
import kk_vrc_cloth_tools as addon
from kk_vrc_cloth_tools import export_cleanup as ec

addon.register()
data = bpy.data.armatures.new('CleanupTest')
arm = bpy.data.objects.new('CleanupTest', data)
bpy.context.collection.objects.link(arm)
bpy.context.view_layer.objects.active = arm
arm.select_set(True)
bpy.ops.object.mode_set(mode='EDIT')
for name, parent in [('unused', None), ('unused_tip', 'unused'), ('weighted', None), ('weighted_tip', 'weighted'), ('unused_branch', 'weighted'), ('constrained', None), ('parented', None), ('cf_j_hips', None)]:
    bone = data.edit_bones.new(name)
    bone.head = (0, 0, 0); bone.tail = (0, 0, 1)
    if parent: bone.parent = data.edit_bones[parent]
bpy.ops.object.mode_set(mode='OBJECT')
meshdata = bpy.data.meshes.new('Fixture')
meshdata.from_pydata([(0, 0, 0)], [], [])
mesh = bpy.data.objects.new('HiddenWeightedMesh', meshdata)
bpy.context.collection.objects.link(mesh)
mesh.hide_set(True)
mesh.modifiers.new('Armature', 'ARMATURE').object = arm
mesh.vertex_groups.new(name='weighted').add([0], 0.001, 'REPLACE')
target = bpy.data.objects.new('Dependent', None)
bpy.context.collection.objects.link(target)
c = target.constraints.new('COPY_LOCATION'); c.target = arm; c.subtarget = 'constrained'
child = bpy.data.objects.new('BoneChild', None)
bpy.context.collection.objects.link(child)
child.parent = arm; child.parent_type = 'BONE'; child.parent_bone = 'parented'
roots = ['unused', 'weighted', 'constrained', 'parented', 'cf_j_hips']
report = ec.plan(arm, roots)
assert {r['root'] for r in report['rows'] if r['eligible']} == {'unused'}, report
assert next(r for r in report['rows'] if r['root']=='weighted')['bones'] == ['unused_branch','weighted','weighted_tip']
bpy.ops.object.select_all(action='DESELECT')
mesh.hide_set(False); mesh.select_set(True)
bpy.context.view_layer.objects.active=mesh
assert ec.selected_armature(bpy.context)==arm
assert set(ec.discover_roots(arm))==set(roots)-{'cf_j_hips'}
assert bpy.ops.kkvrc.export_dynamic_cleanup(action='SCAN') == {'FINISHED'}
p = bpy.context.scene.kkvrc_export_cleanup
assert {r.name for r in p.rows if r.remove}=={'unused'}
row = next(r for r in p.rows if r.name=='unused'); row.remove=True
p.external_checked=True
# Apply rechecks live weights and rejects stale eligibility.
vg = mesh.vertex_groups.new(name='unused'); vg.add([0], 0.5, 'REPLACE')
try:
    bpy.ops.kkvrc.export_dynamic_cleanup(action='APPLY')
except RuntimeError: pass
assert 'unused' in data.bones and 'changed' in p.status
vg.remove([0])
assert bpy.ops.kkvrc.export_dynamic_cleanup(action='APPLY') == {'FINISHED'}
assert 'unused' not in data.bones and 'unused_tip' not in data.bones
assert 'weighted_tip' in data.bones and 'unused_branch' in data.bones and 'cf_j_hips' in data.bones
backups = [d for d in bpy.data.armatures if '.BeforeExportCleanup' in d.name]
assert len(backups)==1 and 'unused_tip' in backups[0].bones and backups[0].use_fake_user
assert mesh.vertex_groups['weighted'].weight(0)>0
addon.unregister()
print('EXPORT_CLEANUP_TEST_OK')

