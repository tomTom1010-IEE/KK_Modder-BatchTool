"""Run in a disposable factory-startup Blender process."""
from pathlib import Path
import sys
import bpy
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from kk_vrc_cloth_tools import mmd_preprocess as prep

data=bpy.data.armatures.new('RoundoffTest')
rig=bpy.data.objects.new('RoundoffTest',data);bpy.context.collection.objects.link(rig)
prep.activate(rig);bpy.ops.object.mode_set(mode='EDIT')
b=data.edit_bones.new('test');b.head=(0,0,0);b.tail=(0,0,1)
bpy.ops.object.mode_set(mode='OBJECT')
mesh=bpy.data.meshes.new('RoundoffMesh');mesh.from_pydata([(0,0,0),(1,0,0),(0,1,0)],[],[(0,1,2)])
obj=bpy.data.objects.new('RoundoffMesh',mesh);bpy.context.collection.objects.link(obj)
mod=obj.modifiers.new('Armature','ARMATURE');mod.object=rig;mod.use_bone_envelopes=False
obj.vertex_groups.new(name='test').add([0,1,2],1,'REPLACE')
target=prep.evaluate(obj)
rig.pose.bones['test'].location.x=1e-5
report=prep.compensate_rebase_roundoff(obj,target,1.)
assert report['before_max_error']>5e-6
assert report['after_max_error']<1e-6
assert report['max_rest_vertex_correction']<3e-5
before=np.array([v.co[:] for v in mesh.vertices])
try:prep.compensate_rebase_roundoff(obj,target+.1,1.)
except ValueError as exc:assert 'exceeds' in str(exc)
else:raise AssertionError('Large deformation silently compensated')
assert np.array_equal(before,np.array([v.co[:] for v in mesh.vertices]))
data.bones['test'].bbone_segments=2
rig.pose.bones['test'].location.x=2e-5
try:prep.compensate_rebase_roundoff(obj,target,1.)
except ValueError as exc:assert 'B-Bone' in str(exc)
else:raise AssertionError('Segmented skinning silently approximated')
assert np.array_equal(before,np.array([v.co[:] for v in mesh.vertices]))
print('MMD_REBASE_ROUNDOFF_TEST_OK')
