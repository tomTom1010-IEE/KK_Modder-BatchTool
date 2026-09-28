"""Factory-startup tests for persistence, float32 writes and lace compression."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bpy
import numpy as np
import kk_vrc_cloth_tools as addon
from kk_vrc_cloth_tools import influence_blender as ui, shoe_workflow as shoe, weights_features as wf
from kk_vrc_cloth_tools import workflow
addon.register()
p=bpy.context.scene.kkvrc_weight_workflow;s=bpy.context.scene.kkvrc_shoes
assert p.total_influences==s.total_influences=='FOUR'
assert not p.compress_dynamic and not s.compress_dynamic
# Simulate ID properties stored by the previous add-on, then run the load handler.
old=bpy.data.scenes.new('legacy-policy-fixture')
old['kkvrc_weight_workflow']={'run':'previous-run'}
old['kkvrc_shoes']={'scan_stamp':'old-source'}
ui.migrate_existing()
assert old.kkvrc_weight_workflow.total_influences=='UNLIMITED'
assert old.kkvrc_shoes.total_influences=='UNLIMITED'
old.kkvrc_weight_workflow.total_influences='FOUR';ui.migrate_existing()
assert old.kkvrc_weight_workflow.total_influences=='FOUR'
ui.load_settings(p,None);assert p.total_influences=='UNLIMITED' and not p.compress_dynamic
ui.load_settings(p,{'max_influences':4});assert p.total_influences=='FOUR'
stamp=workflow.fingerprint(p);p.compress_dynamic=True
assert workflow.fingerprint(p)!=stamp
p.compress_dynamic=False

# Panels must draw even before a new scene's policy has been initialized.
# Match Blender's draw-time ID write guard instead of silently allowing writes.
from types import SimpleNamespace
class ReadOnlySettings:
    def __getattr__(self,name):
        if name=='influence_version':return 0
        return getattr(p,name)
    def __setattr__(self,name,value):
        raise AssertionError('Panel draw attempted to write '+name)
class LayoutProbe:
    def __init__(self):self.props=[]
    def box(self):return self
    def row(self,**kwargs):return self
    def label(self,**kwargs):pass
    def prop(self,settings,name):self.props.append(name)
    def operator(self,*args,**kwargs):return SimpleNamespace()
for mode in ('FOUR','UNLIMITED'):
    p.total_influences=mode
    layout=LayoutProbe();ui.draw(layout,ReadOnlySettings())
    assert 'total_influences' in layout.props
    assert ('compress_dynamic' in layout.props)==(mode=='FOUR')
assert ui.migrate_existing in bpy.app.handlers.load_post
p.total_influences='FOUR'

names=['B0','B1','B2','D0','D1','D2','D3']
data=bpy.data.armatures.new('rig');rig=bpy.data.objects.new('rig',data);bpy.context.collection.objects.link(rig)
bpy.context.view_layer.objects.active=rig;rig.select_set(True);bpy.ops.object.mode_set(mode='EDIT')
for name in names:
    bone=data.edit_bones.new(name);bone.head=(0,0,0);bone.tail=(0,0,1)
    if name!='B0':bone.parent=data.edit_bones['B0']
bpy.ops.object.mode_set(mode='OBJECT')
xyz=np.array([[0.,0.,.1],[.2,0,.1],[0,.2,.1]])
def mesh(name,points):
    data=bpy.data.meshes.new(name);data.from_pydata(points.tolist(),[],[(0,1,2)])
    ob=bpy.data.objects.new(name,data);bpy.context.collection.objects.link(ob)
    ob.modifiers.new('skin','ARMATURE').object=rig
    return ob
baseline=mesh('garment',xyz)
body=mesh('body',np.array([[-2.,-2.,-2.],[2.,-2.,-2.],[0,2.,-2.]]))
for n in names[:3]:body.vertex_groups.new(name=n).add([0,1,2],1/3,'REPLACE')
output=np.tile([.05,.05,.1,.2,.2,.2,.2],(3,1));shoe.write(baseline,names,output)
cfg={'sides':[{'name':'L','target_body':names[:3],'dynamic':names[3:]}],
     'influence_policy':{'max_influences':4},'smoothing':.7}
def contexts():
    return [dict(ids=np.arange(3),j=np.arange(3),p=np.tile([.25,.25,.5],(3,1)),
                 edges=np.array([[0,1],[1,2],[2,0]]),confidence=np.ones(3),
                 budget=np.full(3,.2),allowed=np.ones((3,3),bool))]
before=wf.stamp(baseline);body_before=wf.stamp(body)
tri=np.array([[0,1,2]])
out,rep=shoe.constrain_field(output,names,cfg,contexts(),baseline,body,xyz,tri,tri)
np.testing.assert_array_equal(out,output);assert rep['over_limit_vertices']==[0,1,2]
cfg['influence_policy'].update(compress_dynamic=True,dynamic_error_limit=.1)
out,rep=shoe.constrain_field(output,names,cfg,contexts(),baseline,body,xyz,tri,tri)
assert rep['strict_compatible'],rep
assert rep['compressed_vertices']==[0,1,2],rep
assert rep['dynamic_validation']['constraints_ok'] and rep['dynamic_validation']['contact_ok']
np.testing.assert_allclose(out[:,:3].sum(1),.2,atol=1e-10)
np.testing.assert_allclose(out[:,3:].sum(1),.8,atol=1e-10)
assert wf.stamp(baseline)==before and wf.stamp(body)==body_before
shoe.write(baseline,names,out)
assert max(sum(v>0 for v in row.values()) for row in wf.read_weights(baseline))<=4
addon.unregister();addon.register();addon.unregister()
print('INFLUENCE_BLENDER_OK: default migration, fingerprints, exceptions, probes, immutable scene and float32 output')
