import bpy,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import kk_vrc_cloth_tools as addon
from kk_vrc_cloth_tools import workflow as w
from mathutils import Matrix

def make_rig(name):
    a=bpy.data.armatures.new(name);o=bpy.data.objects.new(name,a);bpy.context.collection.objects.link(o)
    bpy.context.view_layer.objects.active=o;o.select_set(True);bpy.ops.object.mode_set(mode='EDIT')
    coords={'Spine':(0,0,1),'Chest':(0,0,1.3),'Neck':(0,0,1.5),'Upper_arm.L':(.2,0,1.4),'Upper_arm.R':(-.2,0,1.4),'Lower_arm.L':(.5,0,1.4),'Lower_arm.R':(-.5,0,1.4),'Hand.L':(.8,0,1.4),'Hand.R':(-.8,0,1.4)}
    for n,co in coords.items():
        b=a.edit_bones.new(n);b.head=co;b.tail=(co[0],co[1],co[2]+.1)
    b=a.edit_bones.new('cf_j_spine02');b.head=(0,0,1.2);b.tail=(0,0,1.3)
    c=a.edit_bones.new('cf_j_spine03');c.head=(0,0,1.3);c.tail=(0,0,1.4);c.parent=b
    bpy.ops.object.mode_set(mode='OBJECT');return o

def mesh(name,r):
    m=bpy.data.meshes.new(name);m.from_pydata([(0,0,0),(.1,0,0),(0,.1,0)],[],[(0,1,2)])
    o=bpy.data.objects.new(name,m);bpy.context.collection.objects.link(o);o.modifiers.new('rig','ARMATURE').object=r;return o

addon.register();p=bpy.context.scene.kkvrc_weight_workflow
sr=make_rig('source');tr=make_rig('target');tr.matrix_world=Matrix.Rotation(.7,4,'Z')
p.source=mesh('original',sr);p.target=mesh('fitted',tr);p.body=mesh('body',tr)
for n in ['Spine','Chest','Neck','Upper_arm.L','Upper_arm.R','Lower_arm.L','Lower_arm.R','Hand.L','Hand.R']:
    x=p.bones.add();x.name=n;x.role='BODY';x.semantic=w.vr.VRC_MOTION_SEMANTICS[n];x.pose_target='cf_j_spine03' if n=='Chest' else n
p.motion_preset='UPPER';w.generate_motions(p);assert len(p.motions)==9
chest=next(x for x in p.motions if x.source=='Chest')
assert [(part.name,part.factor) for part in chest.target_parts]==[('cf_j_spine02',.5),('cf_j_spine03',.5)]
assert tuple(chest.axis)!=tuple(chest.target_axis)
chest.angle=11;w.generate_motions(p);assert len(p.motions)==9 and chest.angle==11
p.motion_preset='WRIST';w.generate_motions(p);assert len(p.motions)==15
twist=next(x for x in p.motions if x.endpoint and x.angle==50);assert twist.extra_angle==30
local=w.poses(p,True);assert any(abs(x['controls'][0]['degrees'])==30 for x in local)
assert all(all(n.startswith('Hand.') for n,f in ctrl['source']) for pose in local for ctrl in pose['controls'])
addon.unregister();print('MOTION_PRESETS_BLENDER_OK: templates, source/target axes, split spine, dedup, wrist scope')
