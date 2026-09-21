"""UI, transactions and independent results; -- source.blend output_directory."""
from pathlib import Path
import sys,json
import bpy,addon_utils
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
fixture,out=sys.argv[sys.argv.index('--')+1:]
addon_utils.enable('bl_ext.blender_org.mmd_tools',default_set=False,persistent=True)
bpy.ops.wm.open_mainfile(filepath=fixture)
import kk_vrc_cloth_tools as addon
addon.register()
from kk_vrc_cloth_tools import accessory_preprocess as engine,accessory_ui as ui,mmd_preprocess as base
p=bpy.context.scene.kkvrc_accessory
p.source=bpy.data.objects['003_耳环'];p.owned_roots='RingBoneL01, RingBoneR01';p.directory=out
source=p.source;stamp=base.stamp(source)
assert bpy.ops.kkvrc.accessory_preprocess(action='SCAN')=={'FINISHED'}
job=json.loads(p.job);assert len(job['mapping'])==1
p.external='PendantBone'
try:bpy.ops.kkvrc.accessory_preprocess(action='APPLY')
except RuntimeError:pass
else:raise AssertionError('Stale config accepted')
p.external=''
collections=len(bpy.data.collections);old=engine.validate_motion
def fail(*args):raise ValueError('Injected failure')
engine.validate_motion=fail
try:
    try:engine.apply(source,ui.config(p),stamp,out)
    except ValueError as e:assert 'Injected' in str(e)
    else:raise AssertionError('Failed validation accepted')
finally:engine.validate_motion=old
assert len(bpy.data.collections)==collections
assert base.stamp(source)==stamp
assert bpy.ops.kkvrc.accessory_preprocess(action='APPLY')=={'FINISHED'}
job=json.loads(p.job);obj=bpy.data.objects[job['result']];rig=obj.modifiers[0].object
assert rig is not source.modifiers[0].object
assert rig.data is not source.modifiers[0].object.data
assert '頭' not in rig.data.bones and '頭' not in obj.vertex_groups
assert set(rig.data.bones.keys())=={'ACC_Root','ACC_Attach_001','RingBoneL01','RingBoneL02','RingBoneR01','RingBoneR02'}
assert all(not c.target or c.target==rig for pb in rig.pose.bones for c in pb.constraints if hasattr(c,'target'))
assert base.stamp(source)==stamp
try:engine.scan(obj,{})
except ValueError:pass
else:raise AssertionError('Processed input accepted')
assert ui.KKVRC_PT_accessory_preprocess.bl_category=='model preprocess'
p.source=None;assert not p.job and not p.owned_roots
addon.unregister();addon.register();addon.unregister()
print('ACCESSORY_UI_TRANSACTION_TEST_OK')
