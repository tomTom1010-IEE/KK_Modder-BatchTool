"""Real table recognition, frozen fitted reference, collision save and rollback."""
import runpy, json, os, subprocess, tempfile
from pathlib import Path
ns=runpy.run_path(str(Path(__file__).with_name('test_workflow_blender.py')))
bpy=ns['bpy'];addon=ns['addon'];w=ns['w'];wf=ns['wf']
from kk_vrc_cloth_tools import mmd_weight_profiles as profiles
table,asset,digest=profiles.load('MMD_LIV')
records=[{'name':'腕.L','name_j':'左腕','parent':'肩C.L'},
         {'name':'左腕','name_j':'左腕','parent':'肩C.L'},
         {'name':'custom_physics','name_j':'','parent':None}]
classified=profiles.recognize(records,table,asset)
assert all(x['role']=='REVIEW' for x in classified.values())
assert profiles.recognize([{'name':'親指０.L','parent':'手首.L'}],table)['親指０.L']['kind']=='FINGER'
addon.register();p=bpy.context.scene.kkvrc_weight_workflow
for name in ('bones','targets','regions','motions'):getattr(p,name).clear()
p.initial=None;p.macro=None;p.final=None;p.local_vertices='';p.local_topology=''
sr=ns['rig']('MMDTestSource','上半身');tr=ns['rig']('MMDTestTarget','Spine')
p.source=ns['mesh']('MMDSource',sr,'上半身');p.target=ns['mesh']('MMDFitted',tr,'Spine');p.body=ns['mesh']('MMDBody',tr,'Spine',True)
for vertex in p.body.data.vertices:vertex.co.z=1.02
p.source_profile='MMD_LIV';p.reference_mode='FITTED';p.source_sampling='EVALUATED'
w.scan(p)
assert p.bones['上半身'].role=='BODY' and p.bones['Cloth'].role=='REVIEW'
assert p.profile_digest==digest
x=p.bones['上半身'];x.weight_target='Spine';x.pose_target='Spine'
p.bones['Cloth'].role='DYNAMIC'
for x in p.targets:x.region='TORSO';x.reviewed=True
p.regions.clear();r=p.regions.add();r.name='confirmed';r.root='Cloth';r.mode='UNIFORM';w.confirm_region(p)
motion=p.motions.add();motion.source='上半身';motion.target='Spine';motion.angle=5
p.initial_mode='MAP';p.output=tempfile.mkdtemp(prefix='mmd-weight-workflow-')
settings=w.dump_settings(p);assert settings['reference_mode']=='FITTED' and settings['source_profile']=='MMD_LIV'
before=wf.stamp(p.source);w.prepare(p)
assert p.reference and p.reference.data!=p.source.data and w.rig(p.reference).data!=sr.data
w.write_initial(p);path=w.export_stage(p,'macro')
assert json.loads((path/'context.json').read_text())['reference_mode']=='FITTED'
proc=subprocess.run([os.environ['KKVRC_TEST_PYTHON'],str(Path(w.__file__).with_name('optimizer_cli.py')),str(path)],capture_output=True,text=True)
assert proc.returncode==0,proc.stderr
w.validate_stage(p,'macro');report=json.loads((path/'validation.json').read_text())
assert report['non_contact_ok'] and not report['accepted'] and report['collision_review_vertices']
w.write_stage(p,'macro')
assert p.macro and (path/'result.blend').is_file()
assert p.macro['kkvrc_collision_review']=='PENDING'
assert any(v.select for v in p.macro.data.vertices)
assert wf.stamp(p.source)==before
original=p.initial;candidate=p.macro;w.review_result(p,True)
assert not p.macro and candidate.hide_get() and not original.hide_get()
# Frozen reference tampering must not silently redefine the motion objective.
p.reference.data.vertices[0].co.z+=.001
try:w.export_stage(p,'macro')
except ValueError as e:assert 'Frozen' in str(e)
else:raise AssertionError('Changed frozen source accepted')
addon.unregister()
print('MMD_WORKFLOW_INTEGRATION_OK')
