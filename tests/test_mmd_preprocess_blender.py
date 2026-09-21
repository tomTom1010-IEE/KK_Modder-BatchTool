"""Actual UI workflow in a disposable copy; -- fixture.blend output_directory."""
import json
from pathlib import Path
import sys
import bpy
import addon_utils

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
fixture,directory=sys.argv[sys.argv.index('--')+1:]
addon_utils.enable('bl_ext.blender_org.mmd_tools',default_set=False,persistent=True)
bpy.ops.wm.open_mainfile(filepath=fixture)
import kk_vrc_cloth_tools as addon
from kk_vrc_cloth_tools import mmd_preprocess as engine,mmd_preprocess_ui as ui,mmd_preprocess_rules as rules
addon.register()
p=bpy.context.scene.kkvrc_mmd_preprocess
source=bpy.data.objects['003_裙子.001'];p.source=source;p.directory=directory
p.preserve_tips=False
p.chains=', '.join(['q_0_'+str(i) for i in range(15)]+['TieBone01','RopeBoneBack01','RopeBoneL01','RopeBoneR01','BagBoneL01','BagBoneL03','BagBoneR01','BagBoneR03','胸上2.L','胸上2.R'])
p.excluded='带_0_1.L, 带_0_1.R'
source_stamp=engine.stamp(source)
assert bpy.ops.kkvrc.mmd_preprocess(action='SCAN')=={'FINISHED'}
plan=json.loads(p.job)['plan']
assert len(plan['keep'])>242
protected=set(plan['protected_body'])
assert protected-set(plan['weighted']), 'Fixture must exercise unweighted body bones'
assert {'親指０.L','親指０.R','足.L','足.R'} <= protected
assert protected <= set(plan['keep'])
assert plan['review_required'], 'Unknown bones must be retained pending review'
assert set(plan['review_required']) <= set(plan['keep'])
assert set(plan['remove']) <= set(plan['excluded'])
# Reproduce this already-reviewed fixture's old deletion decisions explicitly.
# This is test fixture evidence, never a production auto-approval algorithm.
reviewed_path=Path(fixture).parents[1]/'plugin-integration-body-protection'/'integration.json'
reviewed_plan=json.loads(reviewed_path.read_text(encoding='utf-8'))['result']['plan']
p.confirmed_removals=', '.join(sorted(set(reviewed_plan['remove'])-set(plan['excluded'])))
assert bpy.ops.kkvrc.mmd_preprocess(action='SCAN')=={'FINISHED'}
plan=json.loads(p.job)['plan']
assert set(plan['keep'])==set(reviewed_plan['keep'])
assert not plan['review_required']
# Standard bodies cannot be removed even when auto-T and optional tips are off.
cfg=ui.config(p);cfg.update(auto_tpose=False, mapping={}, excluded=['足.L'])
try:engine.scan(source,cfg)
except ValueError as exc:assert 'protected body bones' in str(exc)
else:raise AssertionError('Protected leg excluded')
# B-Bone handles are dependencies even when the handle itself has no weight.
rig=engine.rig_of(source);body=rig.data.bones['腕.L'];handle=rig.data.bones['足.L']
old_handle=body.bbone_custom_handle_start
body.bbone_custom_handle_start=handle
assert handle.name in next(b for b in engine.bones(rig) if b['name']==body.name)['dependencies']
body.bbone_custom_handle_start=old_handle
assert engine.stamp(source)==source_stamp
assert ui.KKVRC_PT_mmd_preprocess.bl_category=='model preprocess'
p.preserve_tips=True
try:bpy.ops.kkvrc.mmd_preprocess(action='PREPARE')
except RuntimeError:pass
else:raise AssertionError('Stale config accepted')
p.preserve_tips=False
assert bpy.ops.kkvrc.mmd_preprocess(action='PREPARE')=={'FINISHED'}
job=json.loads(p.job)
assert engine.stamp(source)==source_stamp
candidate=p.candidate
# Mutation outside Pose must be rejected before finalization creates output.
candidate.data.vertices[0].co.x+=.001
p.reviewed=True
try:bpy.ops.kkvrc.mmd_preprocess(action='FINALIZE')
except RuntimeError:pass
else:raise AssertionError('Edited mesh accepted')
candidate.data.vertices[0].co.x-=.001
# Float arithmetic may not round-trip; restore exact coordinate from the source.
candidate.data.vertices[0].co=source.data.vertices[0].co
# Transaction rollback on an injected validation failure must preserve source
# and candidate, and discard the incomplete result collection.
collection_count=len(bpy.data.collections)
original_check=engine.motion_check
def fail_check(*args):raise ValueError('injected motion failure')
engine.motion_check=fail_check
try:
    try:engine.finalize(job)
    except ValueError as exc:assert 'injected' in str(exc)
    else:raise AssertionError('Validation failure accepted')
finally:engine.motion_check=original_check
assert len(bpy.data.collections)==collection_count
assert engine.stamp(source)==source_stamp
assert engine.stamp(candidate,False)==job['candidate_stamp']
assert bpy.ops.kkvrc.mmd_preprocess(action='FINALIZE')=={'FINISHED'}
report=json.loads(p.job)
assert report['bones_after']==len(plan['keep']),report
assert protected <= set(engine.rig_of(p.result).data.bones.keys())
assert report['constraints_remaining']>=28
assert not report['optimizer_ready']
assert not protected.intersection(report['empty_groups_removed'])
assert len(report['empty_groups_removed'])<151
assert engine.stamp(source)==source_stamp
assert engine.attributes(p.result)==engine.attributes(source)
assert all(v['max_error']<1e-6 for v in report['motion_validation'])
assert p.result.get('kkvrc_mmd_preprocessed')
assert (Path(report['directory'])/'before.blend').exists()
assert (Path(report['directory'])/'result.blend').exists()
try:engine.finalize(job)
except ValueError:pass
else:raise AssertionError('Candidate finalized twice')
try:engine.scan(p.result,ui.config(p))
except ValueError:pass
else:raise AssertionError('Repeated preprocessing accepted')
# Unsupported inputs are rejected without silently stripping their features.
key=source.shape_key_add(name='Basis')
try:engine.scan(source,ui.config(p))
except ValueError as exc:assert 'Shape keys' in str(exc)
else:raise AssertionError('Shape keys silently accepted')
source.shape_key_remove(key)
assert engine.stamp(source)==source_stamp
Path(directory).mkdir(parents=True,exist_ok=True)
(Path(directory)/'integration.json').write_text(json.dumps({'status':'PASS','source_unchanged':True,'result':report},ensure_ascii=False,indent=2),encoding='utf-8')
# Asset changes via the pointer picker must clear deletion approvals as well.
p.source=None
assert not p.confirmed_removals and not p.excluded and not p.job and not p.stage
addon.unregister()
assert not hasattr(bpy.types.Scene,'kkvrc_mmd_preprocess')
addon.register();addon.unregister()
print('MMD_PREPROCESS_TEST_OK')
