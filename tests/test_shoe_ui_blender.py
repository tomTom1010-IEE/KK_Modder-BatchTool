"""Integration: blender --background --factory-startup --python this.py -- fixture.blend output_dir.

Loads a disposable fixture, never saves it. Executes the actual UI operators.
"""
import json
import sys
from pathlib import Path
import bpy

repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(repo))
fixture,directory=sys.argv[sys.argv.index('--')+1:]
bpy.ops.wm.open_mainfile(filepath=fixture)
import kk_vrc_cloth_tools as addon
addon.register()
from kk_vrc_cloth_tools import shoe_ui as ui, weights_features as wf,shoe_workflow as engine

p=bpy.context.scene.kkvrc_shoes
cfg=json.loads((repo/'examples/flat_shoe_neon_vertex.json').read_text(encoding='utf-8-sig'))
source,target,body=[bpy.data.objects[cfg[k]] for k in ['source','target','body']]
stamps={o.name:wf.stamp(o) for o in [source,target,body]}
p.source=source;p.target=target;p.body=body
assert bpy.ops.kkvrc.shoe_action(action='SCAN')=={'FINISHED'}
assert len(p.roots)==8 and not any(r.reviewed for r in p.roots)
assert {x.name for x in p.target_bones}==wf.body_weight_support(body,target)
try:ui.config(p)
except ValueError:pass
else:raise AssertionError('Unreviewed scan was accepted')
ui.load_config(p,cfg,trust_review=True)
assert bpy.ops.kkvrc.shoe_action(action='CHECK')=={'FINISHED'}
p.prefix='Shoe.UI.Integration';p.directory=directory
assert bpy.ops.kkvrc.shoe_action(action='A')=={'FINISHED'}
assert p.baseline and not p.optimized
assert (Path(p.last_directory)/'field-context.npz').exists()
value=p.smoothing;p.smoothing=value+.1
try:engine.resume_gap(source,target,body,ui.config(p),p.last_directory)
except ValueError as e:assert 'configuration changed' in str(e)
else:raise AssertionError('Stale field config accepted')
p.smoothing=value
assert bpy.ops.kkvrc.shoe_action(action='B')=={'FINISHED'}
assert p.baseline and 'baseline_validation' in json.loads(p.report)
assert bpy.ops.kkvrc.shoe_action(action='SHOW_A')=={'FINISHED'}
assert bpy.context.object==p.baseline and not p.baseline.hide_get()
if p.optimized:
    assert bpy.ops.kkvrc.shoe_action(action='SHOW_B')=={'FINISHED'}
    assert bpy.context.object==p.optimized and p.baseline.hide_get()
assert all(wf.stamp(bpy.data.objects[n])==v for n,v in stamps.items())
data={'status':'passed','registered':True,'scan_roots':len(p.roots),'stage_A':p.baseline.name,
      'stage_B':p.optimized.name if p.optimized else None,'stale_config_rejected':True,
      'protected_unchanged':True,'round_directory':p.last_directory,'result':json.loads(p.report)}
Path(directory).mkdir(parents=True,exist_ok=True)
(Path(directory)/'integration.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
addon.unregister()
assert not hasattr(bpy.types.Scene,'kkvrc_shoes')
print('SHOE_UI_TEST_OK')
