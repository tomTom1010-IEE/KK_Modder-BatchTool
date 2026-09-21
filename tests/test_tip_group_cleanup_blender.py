import bpy,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from kk_vrc_cloth_tools import bone_cleanup as bc
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
a=bpy.data.armatures.new('test');r=bpy.data.objects.new('test',a);bpy.context.collection.objects.link(r)
r.select_set(True);bpy.context.view_layer.objects.active=r;bpy.ops.object.mode_set(mode='EDIT')
for i,n in enumerate(['parent','empty_tip','weighted_tip','root_tip','legacy_tip']):
 b=a.edit_bones.new(n);b.head=(i,0,0);b.tail=(i,0,1)
 if n not in ['parent','root_tip']:b.parent=a.edit_bones['parent']
bpy.ops.object.mode_set(mode='OBJECT')
meshes=[]
for name in ['one','two']:
 d=bpy.data.meshes.new(name);d.from_pydata([(0,0,0)],[],[])
 o=bpy.data.objects.new(name,d);bpy.context.collection.objects.link(o);o.parent=r;meshes.append(o)
 for n,w in [('parent',.5),('empty_tip',0),('weighted_tip',.2),('root_tip',.3),('legacy_tip',0)]:
  g=o.vertex_groups.new(name=n);g.add([0],w,'REPLACE')
p=bc.cleanup_hair_tip_placeholders(r,['empty_tip','weighted_tip','root_tip'],False,'SUBTREE_TO_PARENT',False,True)
assert p['deleted_bones']==['empty_tip'] and len(p['vertex_groups_to_remove'])==2
assert 'empty_tip' in a.bones and all('empty_tip' in o.vertex_groups for o in meshes)
bc.cleanup_hair_tip_placeholders(r,['empty_tip','weighted_tip','root_tip'],False,'SUBTREE_TO_PARENT',True,True)
assert 'empty_tip' not in a.bones and all('empty_tip' not in o.vertex_groups for o in meshes)
assert 'weighted_tip' in a.bones and 'root_tip' in a.bones
bc.cleanup_hair_tip_placeholders(r,['weighted_tip','root_tip'],True,'SUBTREE_TO_PARENT',True,True)
assert 'weighted_tip' not in a.bones and 'root_tip' in a.bones
for o in meshes:
 assert 'weighted_tip' not in o.vertex_groups
 assert abs(o.vertex_groups['parent'].weight(0)-.7)<1e-6
bc.cleanup_hair_tip_placeholders(r,['legacy_tip'],False,'SUBTREE_TO_PARENT',True)
assert all('legacy_tip' in o.vertex_groups for o in meshes)
print('PASS: preview, two meshes, zero memberships, protected weighted/root tips, parent merge, legacy default')
