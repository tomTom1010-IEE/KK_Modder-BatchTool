import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bpy
import numpy as np
from mathutils import Matrix
from kk_vrc_cloth_tools import weights_optimization as api, weights_features as wf, weight_features as core
from kk_vrc_cloth_tools.optimizer_validation import check_surface, validate


def rig(name,bodyname):
    a=bpy.data.armatures.new(name);o=bpy.data.objects.new(name,a);bpy.context.collection.objects.link(o)
    bpy.context.view_layer.objects.active=o;o.select_set(True);bpy.ops.object.mode_set(mode='EDIT')
    root=a.edit_bones.new(bodyname);root.head=(0,0,0);root.tail=(0,0,1)
    child=a.edit_bones.new('Cloth');child.head=(0,0,1);child.tail=(0,0,2);child.parent=root
    control=a.edit_bones.new('UnusedControl');control.head=(0,0,0);control.tail=(0,0,1);control.parent=root
    bpy.ops.object.mode_set(mode='OBJECT');return o


def mesh(name,r,bodyname):
    m=bpy.data.meshes.new(name);m.from_pydata([(0,0,1),(1,0,1),(0,1,1)],[],[(0,1,2)])
    o=bpy.data.objects.new(name,m);bpy.context.collection.objects.link(o)
    o.modifiers.new('Armature','ARMATURE').object=r
    o.vertex_groups.new(name=bodyname).add([0,1,2],.6,'REPLACE')
    o.vertex_groups.new(name='Cloth').add([0,1,2],.4,'REPLACE');return o


srig=rig('source_rig','Torso');trig=rig('target_rig','Spine')
source=mesh('source',srig,'Torso');target=mesh('target',trig,'Spine');body=mesh('body',trig,'Spine')
trig.matrix_world=Matrix.Translation((4,2,1))@Matrix.Rotation(.4,4,'Z')@Matrix.Diagonal((1.5,.8,1.2,1))
target.matrix_world=trig.matrix_world.copy();body.matrix_world=trig.matrix_world.copy()
target.data.vertices[1].co.z+=.15
bpy.context.view_layer.update()
before=wf.stamp(target)
pose={'name':'bend','kind':'holdout','weight':0,'controls':[{'source':[('Torso',1)],'target':[('Spine',1)],'axis':[0,1,0],'degrees':25}]}
a,m=api.export_context(source,target,body,roles={'Torso':'BODY','Cloth':'DYNAMIC'},bone_map={'Torso':'Spine'},
    source_regions={'Torso':'TORSO'},target_regions={'Spine':'TORSO'},
    finger_policy={'source_fingers':{},'target_fingers':{},'enabled':[]},poses=[pose],reviewed_patterns='uniform')
assert before==wf.stamp(target)
# Source evidence must include every weighted deform bone, including a helper
# that is a sibling of the wrist rather than a child following wrist rotation.
source.vertex_groups.new(name='UnusedControl').add([0,1,2],.3,'REPLACE')
args=dict(roles={'Torso':'BODY','Cloth':'DYNAMIC','UnusedControl':'DROP'},bone_map={'Torso':'Spine'},
    source_regions={'Torso':'TORSO'},target_regions={'Spine':'TORSO'},
    finger_policy={'source_fingers':{},'target_fingers':{},'enabled':[]},poses=[pose],reviewed_patterns='uniform')
try:api.export_context(source,target,body,**args)
except ValueError as error:assert 'discard' in str(error).lower()
else:raise AssertionError('Effective source helper silently dropped')
source.vertex_groups.remove(source.vertex_groups['UnusedControl'])
for k,mat in enumerate(a['source_matrices']):
    basis=np.einsum('bij,vj->vbi',mat[:,:3,:3],a['source_rest'])+mat[None,:,:3,3]
    assert np.max(abs(np.einsum('vb,vbc->vc',a['source_weights'],basis)-a['actual_source'][k]))<2e-6
local_policy={'region_bones':{'TORSO':['Spine']},'delta_limits':{'0':.05},
              'pose_bones':{'source':['Torso'],'target':['Spine']}}
la,lm=api.export_context(source,target,body,roles={'Torso':'BODY','Cloth':'DYNAMIC'},bone_map={'Torso':'Spine'},
    source_regions={'Torso':'TORSO'},target_regions={'Spine':'TORSO'},
    finger_policy={'source_fingers':{},'target_fingers':{},'enabled':[]},poses=[pose],reviewed_patterns='uniform',
    selected=[0],local_refinement=local_policy)
assert la['delta_limits'].tolist()==[.05,0.,0.]
assert lm['local_refinement']['pose_bones']['source']==['Torso']
assert la['fixed'][:,lm['target_names'].index('Cloth')].all()
assert before==wf.stamp(target)
for p,mat in enumerate(a['target_matrices']):
    basis=np.einsum('bij,vj->vbi',mat[:,:3,:3],a['target_rest'])+mat[None,:,:3,3]
    computed=np.einsum('vb,vbc->vc',a['initial'],basis)
    assert np.max(abs(computed-a['actual_target'][p]))<2e-6
validation={'accepted':True,'context_id':m['context_id'],'candidate_digest':core.digest(a['initial'].tolist())}
plan=api.prepare_optimized_plan(target,a,m,a['initial'],validation)
duplicate=target.copy();duplicate.data=target.data.copy();bpy.context.collection.objects.link(duplicate)
bpy.context.view_layer.update()
copy_plan=api.prepare_optimized_plan(target,a,m,a['initial'],validation,destination=duplicate)
wf.apply_plan(duplicate,copy_plan)
assert wf.stamp(target)==before
assert duplicate.data!=target.data
duplicate.data.vertices[0].co.z+=.01
try:api.prepare_optimized_plan(target,a,m,a['initial'],validation,destination=duplicate)
except ValueError:pass
else:raise AssertionError('Altered duplicate accepted')
wf.apply_plan(target,plan)
source.data.vertices[0].co.x+=.01
try:wf.apply_plan(target,plan)
except ValueError:pass
else:raise AssertionError('Stale source accepted at writeback')
source.data.vertices[0].co.x-=.01
bad=dict(validation,context_id='wrong')
try:api.prepare_optimized_plan(target,a,m,a['initial'],bad)
except ValueError:pass
else:raise AssertionError('Wrong validation context accepted')
# Face crossing with every cloth vertex on/outside the open surface: triangle
# intersection must be tested in addition to vertex sample statistics.
cloth=np.array([[-1.,0,1],[1,0,1],[0,0,-1]])
surface=np.array([[-2.,-2,0],[2,-2,0],[0,2,0]])
report=check_surface(cloth,np.array([[0,1,2]]),surface,np.array([[0,1,2]]))
assert report['intersecting_triangle_pairs']>0
pure=check_surface(cloth,np.array([[0,1,2]]),surface,np.array([[0,1,2]]),excluded=np.ones(3,bool))
assert pure['in_scope']['intersecting_triangle_pairs']==0
assert pure['excluded']['intersecting_triangle_pairs']==report['intersecting_triangle_pairs']
mixed=check_surface(cloth,np.array([[0,1,2]]),surface,np.array([[0,1,2]]),excluded=np.array([True,True,False]))
assert mixed['in_scope']['intersecting_triangle_pairs']>0
# A frozen exterior collision is diagnostic in a local stage, but still fails
# a whole-body stage. Faces touching any selected vertex stay in scope above.
points=np.array([[0.,0,1],[.2,0,1],[0,.2,1],[0,0,-.1],[.2,0,-.1],[0,.2,-.1]])
aa={'initial':np.ones((6,1)),'target_rest':points,'target_matrices':np.broadcast_to(np.eye(4),(2,1,4,4)).copy(),
    'triangles':np.array([[0,1,2],[3,4,5]]),'body_poses':np.stack([surface,surface]),'body_triangles':np.array([[0,1,2]]),
    'budgets':np.tile([1.,0,0,0,0,0],(6,1)),'regions':np.array([0]),'fixed':np.zeros((6,1),bool),'selected':np.array([0,1,2])}
cc={'weights':aa['initial'].copy(),'positions':np.stack([points,points]),'reference':np.stack([points,points])}
aa.update(source_rest=points.copy(),source_weights=aa['initial'].copy(),
          source_matrices=aa['target_matrices'].copy(),actual_source=cc['positions'].copy())
mm={'poses':[{'name':'rest','kind':'common'},{'name':'test','kind':'holdout'}],
    'target_names':['Spine'],'allowed_body_bones':['Spine'],'retained_dynamic_bones':[],
    'local_refinement':{'stage':'local_test'},'arrays_digest':core.digest({k:v.tolist() for k,v in aa.items()})}
mm['context_id']=core.digest(mm)
rr={'status':'solved','context_id':mm['context_id'],'candidate_digest':core.digest(cc['weights'].tolist()),'reference_digest':core.digest(cc['reference'].tolist())}
assert validate(aa,mm,cc,rr)['accepted']
mm.pop('local_refinement');mm.pop('context_id');mm['context_id']=core.digest(mm);rr['context_id']=mm['context_id']
assert not validate(aa,mm,cc,rr)['accepted']
from kk_vrc_cloth_tools.optimizer_scope import check_source_deformation
bad_source={**aa,'actual_source':aa['actual_source']+.01}
try:check_source_deformation(bad_source)
except ValueError:pass
else:raise AssertionError('Corrupted source motion evidence accepted')
repair_copy=target.copy();repair_copy.data=target.data.copy();bpy.context.collection.objects.link(repair_copy)
repair_copy.vertex_groups['Spine'].add([0,1,2],.5,'REPLACE')
repair_copy.vertex_groups.new(name='UnusedControl').add([0,1,2],.1,'REPLACE')
bpy.context.view_layer.update()
assert 'UnusedControl' not in wf.body_weight_support(body,repair_copy)
repair=wf.prepare_supported_initial(repair_copy,body,{'UnusedControl':'TORSO','Spine':'TORSO'},['Cloth'],{'UnusedControl':'Spine'})
wf.apply_plan(repair_copy,repair)
assert all(row.get('UnusedControl',0)==0 for row in wf.read_weights(repair_copy))
assert all(abs(row['Spine']-.6)<1e-7 and abs(row['Cloth']-.4)<1e-7 for row in wf.read_weights(repair_copy))
repair_copy.vertex_groups['UnusedControl'].add([0],.1,'REPLACE')
try:wf.prepare_supported_initial(repair_copy,body,{'Spine':'TORSO','UnusedControl':'ARM_L'},['Cloth'],{'UnusedControl':'Spine'})
except ValueError:pass
else:raise AssertionError('Unsupported/cross-region replacement accepted')
print('BLENDER_OPTIMIZER_CHECKS_OK: transformed coordinates, sculpt, pose restore, LBS, plan guard, face collision')
