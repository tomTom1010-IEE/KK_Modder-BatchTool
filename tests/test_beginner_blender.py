"""Beginner preset, refusal gates, and real native-transfer/OSQP write path."""
import bpy,sys,os,tempfile,subprocess,json,shutil
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import kk_vrc_cloth_tools as addon
from kk_vrc_cloth_tools import workflow as w, workflow_beginner as b

def rig(name):
    a=bpy.data.armatures.new(name);o=bpy.data.objects.new(name,a);bpy.context.collection.objects.link(o)
    bpy.context.view_layer.objects.active=o;o.select_set(True);bpy.ops.object.mode_set(mode='EDIT')
    coords={'Spine':(0,0,1),'Chest':(0,0,1.3),'Neck':(0,0,1.5),
            'Upper_arm.L':(.2,0,1.4),'Upper_arm.R':(-.2,0,1.4),'Lower_arm.L':(.5,0,1.4),
            'Lower_arm.R':(-.5,0,1.4),'Hand.L':(.8,0,1.4),'Hand.R':(-.8,0,1.4),'Cloth':(0,0,1.2)}
    for n,co in coords.items():
        bone=a.edit_bones.new(n);bone.head=co;bone.tail=(co[0],co[1],co[2]+.1)
    a.edit_bones['Cloth'].parent=a.edit_bones['Chest']
    bpy.ops.object.mode_set(mode='OBJECT');return o

def mesh(name,arm,isbody=False):
    data=bpy.data.meshes.new(name);z=-3 if isbody else 1
    data.from_pydata([(x*.1,y*.1,z) for y in range(3) for x in range(4)],[],
                    [(y*4+x,y*4+x+1,(y+1)*4+x+1,(y+1)*4+x) for y in range(2) for x in range(3)])
    o=bpy.data.objects.new(name,data);bpy.context.collection.objects.link(o);o.modifiers.new('rig','ARMATURE').object=arm
    o.vertex_groups.new(name='Chest').add(list(range(12)),1 if isbody else .6,'REPLACE')
    if not isbody:o.vertex_groups.new(name='Cloth').add(list(range(12)),.4,'REPLACE')
    return o

addon.register();p=bpy.context.scene.kkvrc_weight_workflow
sr=rig('source');tr=rig('target');p.source=mesh('original',sr);p.target=mesh('fitted',tr);p.body=mesh('body',tr,True)
for name in ['Spine','Chest','Neck','Upper_arm.L','Upper_arm.R','Lower_arm.L','Lower_arm.R','Hand.L','Hand.R']:
    x=p.bones.add();x.name=name;x.role='BODY';x.region='TORSO';x.weight_target='Chest';x.pose_target=name;x.semantic=w.vr.VRC_MOTION_SEMANTICS[name]
x=p.bones.add();x.name='Cloth';x.role='REVIEW'
x=p.targets.add();x.name='Chest';x.region='TORSO';x.reviewed=True
p.output=tempfile.mkdtemp(prefix='kkvrc-beginner-');p.python=os.environ['KKVRC_TEST_PYTHON']
before={o.name:w.wf.stamp(o) for o in [p.source,p.target,p.body]}
b.apply_preset(p)
assert not p.contacts and p.collision_policy=='REVIEW' and p.initial_mode=='NATIVE' and len(p.motions)==9
assert len(p.regions)==1 and p.regions[0].suggestion=='UNIFORM' and not p.regions[0].reviewed_stamp
assert list(Path(p.output).glob('before-conservative-*.json'))
try:b.start(p)
except ValueError:pass
else:raise AssertionError('Unreviewed roles/region bypassed')
assert not p.initial
p.bones['Cloth'].role='DYNAMIC';w.confirm_region(p)
# An unsupported endpoint configuration must fail before producing a copy.
p.beginner_terminal=True;b.apply_preset(p)
try:b.start(p)
except ValueError as exc:assert 'Terminal' in str(exc),str(exc)
else:raise AssertionError('Missing local scope accepted')
assert not p.initial
p.beginner_terminal=False;b.apply_preset(p);b.start(p)
path=w.export_stage(p,'macro')
run=subprocess.run([p.python,str(Path(w.__file__).with_name('optimizer_cli.py')),str(path),'--contacts'],capture_output=True,text=True)
assert run.returncode==0,run.stderr
shutil.copyfile(path/'contact_report.json',path/'report.json');shutil.copyfile(path/'contact_candidate.npz',path/'candidate.npz')
b.finish_stage(p,'macro')
assert p.macro and not p.final
assert all(w.wf.stamp(o)==before[o.name] for o in [p.source,p.target,p.body])
assert json.loads((path/'validation.json').read_text())['accepted']
# A rejected independent validation never reaches the write helper.
from unittest.mock import patch
def rejected(props,stage):w.save(path/'validation.json',{'accepted':False})
with patch.object(w,'validate_stage',rejected),patch.object(w,'write_stage') as write:
    try:b.finish_stage(p,'macro')
    except ValueError:pass
    else:raise AssertionError('Rejected validation accepted')
    write.assert_not_called()
# Visible panel registers and all buttons reference real operators.
class Layout:
    def __getattr__(self,n):
        def call(*args,**kwargs):
            if n=='operator':
                prefix,name=args[0].split('.');assert hasattr(getattr(bpy.ops,prefix),name)
            return self
        return call
from types import SimpleNamespace
b.KKVRC_PT_beginner_weights.draw(SimpleNamespace(layout=Layout()),bpy.context)
# Actual modal completion dispatches automatic validation/writing and catches
# failures instead of letting an exception silently terminate the operator.
dummy=SimpleNamespace(scene=bpy.context.scene,stage='macro',automatic=True,include_terminal=False,
                      path=path,process=SimpleNamespace(poll=lambda:0,returncode=0),finish=lambda context,*args:None,report=lambda *args:None)
with patch.object(b,'finish_stage') as finish:
    assert w.KKVRC_OT_workflow_solve.modal(dummy,bpy.context,SimpleNamespace(type='TIMER'))=={'FINISHED'}
    finish.assert_called_once_with(p,'macro')
with patch.object(b,'finish_stage',side_effect=ValueError('validation refused')):
    assert w.KKVRC_OT_workflow_solve.modal(dummy,bpy.context,SimpleNamespace(type='TIMER'))=={'CANCELLED'}
    assert 'validation refused' in p.status
from unittest.mock import Mock
next_stage=Mock(return_value={'RUNNING_MODAL'});dummy.include_terminal=True
fake_bpy=SimpleNamespace(ops=SimpleNamespace(kkvrc=SimpleNamespace(weight_workflow_solve=next_stage)))
with patch.object(b,'finish_stage'),patch.object(w,'bpy',fake_bpy):
    assert w.KKVRC_OT_workflow_solve.modal(dummy,bpy.context,SimpleNamespace(type='TIMER'))=={'FINISHED'}
    next_stage.assert_called_once_with('INVOKE_DEFAULT',stage='terminal',automatic=True,include_terminal=False)
assert w.KKVRC_OT_workflow_solve.modal(dummy,bpy.context,SimpleNamespace(type='ESC'))=={'CANCELLED'}
addon.unregister();print('BEGINNER_BLENDER_OK: preset, review/scope gates, native transfer, contacts solve, independent validation, copy-only write')
