"""Background Blender end-to-end checks: UI registration, plans, both stages."""
import sys,json,subprocess,os,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bpy
import kk_vrc_cloth_tools as addon
from kk_vrc_cloth_tools import workflow as w, weights_features as wf

def rig(name,root):
    data=bpy.data.armatures.new(name);obj=bpy.data.objects.new(name,data);bpy.context.collection.objects.link(obj)
    bpy.context.view_layer.objects.active=obj;obj.select_set(True);bpy.ops.object.mode_set(mode='EDIT')
    b=data.edit_bones.new(root);b.head=(0,0,0);b.tail=(0,0,1)
    c=data.edit_bones.new('Cloth');c.head=(0,0,1);c.tail=(0,0,2);c.parent=b
    bpy.ops.object.mode_set(mode='OBJECT');return obj

def mesh(name,arm,root,body=False):
    data=bpy.data.meshes.new(name);z=-2 if body else 1
    data.from_pydata([(0,0,z),(.2,0,z),(0,.2,z)],[],[(0,1,2)])
    obj=bpy.data.objects.new(name,data);bpy.context.collection.objects.link(obj);obj.modifiers.new('Armature','ARMATURE').object=arm
    obj.vertex_groups.new(name=root).add([0,1,2],1 if body else .6,'REPLACE')
    if not body:obj.vertex_groups.new(name='Cloth').add([0,1,2],.4,'REPLACE')
    return obj

addon.register()
p=bpy.context.scene.kkvrc_weight_workflow
srig=rig('SourceRig','Torso');trig=rig('TargetRig','Spine')
p.source=mesh('SourceCloth',srig,'Torso');p.target=mesh('FittedCloth',trig,'Spine');p.body=mesh('TargetBody',trig,'Spine',True)
w.scan(p)
for x in p.bones:
    if x.name=='Torso':x.role='BODY';x.region='TORSO';x.weight_target='Spine';x.pose_target='Spine'
    else:x.role='DYNAMIC'
for x in p.targets:x.region='TORSO';x.reviewed=True
p.regions.clear()
r=p.regions.add();r.name='connection';r.root='Cloth';r.mode='EDGE_GRADIENT'
w.confirm_region(p)
approved=r.reviewed_stamp;w.analyze_regions(p)
assert r.reviewed_stamp==approved and r.mode=='EDGE_GRADIENT'
m=p.motions.add();m.name='bend';m.source='Torso';m.target='Spine';m.angle=12
c=w.config(p);assert c['region_modes']==dict.fromkeys(range(3),'EDGE_GRADIENT')
# Automatic suggestions never grant approval; stale source weights invalidate it.
saved_review=r.reviewed_stamp
p.source.vertex_groups['Torso'].add([0],.5,'REPLACE')
try:w.config(p)
except ValueError:pass
else:raise AssertionError('Stale region approval accepted')
p.source.vertex_groups['Torso'].add([0],.6,'REPLACE');assert r.reviewed_stamp==saved_review
r.mode='UNIFORM'
w.analyze_regions(p)
assert not r.reviewed_stamp # A statistic cannot grant approval.
try:w.config(p)
except ValueError:pass
else:raise AssertionError('Changed mode accepted without review')
r.mode='EDGE_GRADIENT';w.confirm_region(p)
stamp_preview=wf.stamp(p.target);w.preview_motion(p);w.restore_preview()
assert wf.stamp(p.target)==stamp_preview
# Target split is serialized and used by generated poses, not only displayed.
part=m.target_parts.add();part.name='Spine';part.factor=1
assert w.poses(p,False)[0]['controls'][0]['target']==[('Spine',1.)]
assert w.dump_settings(p)['motions'][0]['target_parts']==[{'name':'Spine','factor':1.0}]
p.initial_mode='MAP';p.contacts=False
root=Path(tempfile.mkdtemp(prefix='kkvrc-workflow-test-'));p.output=str(root)
before_native=wf.stamp(p.target)
p.initial_mode='NATIVE';w.prepare(p)
assert wf.stamp(p.target)==before_native # Native sampling must remain a preview.
p.initial_mode='MAP'
before=wf.stamp(p.target);w.prepare(p);w.write_initial(p)
assert p.initial and wf.stamp(p.target)==before
old=w.fingerprint(p);p.confidence=.8
try:w.fresh(p)
except ValueError:pass
else:raise AssertionError('Changed initial config accepted')
p.confidence=1;assert w.fingerprint(p)==old
exe=os.environ.get('KKVRC_TEST_PYTHON','python')
cli=Path(w.__file__).with_name('optimizer_cli.py')
for stage in ['macro','terminal']:
    if stage=='terminal':
        m=p.motions.add();m.name='end';m.source='Torso';m.target='Spine';m.endpoint=True;m.angle=15
        p.local_vertices='[0]';p.local_topology=wf.topology(p.source);p.targets[0].local=True
        assert w.fresh(p) # Endpoint choices must not invalidate initial/body stage.
    path=w.export_stage(p,stage)
    result=subprocess.run([exe,str(cli),str(path)],capture_output=True,text=True)
    assert result.returncode==0,result.stderr
    w.validate_stage(p,stage)
    v=json.loads((path/'validation.json').read_text());assert v['accepted'],v
    w.write_stage(p,stage)
assert p.final and wf.stamp(p.target)==before
assert all(abs(row['Cloth']-.4)<1e-6 for row in wf.read_weights(p.final))
# The panel can be drawn using registered data; every visible operator exists.
class Layout:
    def __getattr__(self,n):
        def call(*args,**kwargs):
            if n=='operator':
                prefix,name=args[0].split('.');assert hasattr(getattr(bpy.ops,prefix),name)
            return self
        return call
w.draw(Layout(),bpy.context)
addon.unregister();addon.register();addon.unregister()
print('WORKFLOW_BLENDER_OK: registration, explicit regions, two stages, stamps, protected source, draw')
