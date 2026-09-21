import runpy
from pathlib import Path
ns=runpy.run_path(str(Path(__file__).with_name('test_optimizer_blender.py')))
globals().update({k:v for k,v in ns.items() if not k.startswith('__')})
sr=rig('constraint_source','Torso');tr=rig('constraint_target','Spine')
s=mesh('constraint_source_mesh',sr,'Torso');t=mesh('constraint_target_mesh',tr,'Spine');b=mesh('constraint_body',tr,'Spine')
c=sr.pose.bones['Torso'].constraints.new('LIMIT_ROTATION');c.owner_space='LOCAL';c.use_limit_z=True;c.min_z=-.1;c.max_z=.1
s.vertex_groups.new(name='mmd_edge_scale').add([0,1,2],2,'REPLACE');t.vertex_groups.new(name='mmd_edge_scale').add([0,1,2],2,'REPLACE')
args=dict(roles={'Torso':'BODY','Cloth':'DYNAMIC','mmd_edge_scale':'IGNORE'},bone_map={'Torso':'Spine'},source_regions={'Torso':'TORSO'},target_regions={'Spine':'TORSO'},finger_policy={'source_fingers':{},'target_fingers':{},'enabled':[]},poses=[{'name':'limit','kind':'holdout','controls':[{'source':[('Torso',1)],'target':[('Spine',1)],'axis':[0,0,1],'degrees':30}]}],reviewed_patterns='uniform')
try:api.export_context(s,t,b,**args)
except ValueError:pass
else:raise AssertionError('Implicit constraints accepted')
contract=api.source_pose_contract(s);a,m=api.export_context(s,t,b,source_contract=contract,**args)
assert check_source_deformation(a)<1e-6
assert 'mmd_edge_scale' not in m['target_names']
assert c.max_z<.101 and sr.pose.bones['Torso'].rotation_quaternion.angle==0
validation={'accepted':True,'context_id':m['context_id'],'candidate_digest':core.digest(a['initial'].tolist())}
plan=api.prepare_optimized_plan(t,a,m,a['initial'],validation)
c.max_z=.2
try:wf.apply_plan(t,plan)
except ValueError:pass
else:raise AssertionError('Changed constraints accepted by weight writeback')
try:api.export_context(s,t,b,source_contract=contract,**args)
except ValueError:pass
else:raise AssertionError('Stale constraint contract accepted')
c2=sr.pose.bones['Cloth'].constraints.new('COPY_TRANSFORMS');c2.target=tr;c2.subtarget='Spine'
try:api.source_pose_contract(s)
except ValueError:pass
else:raise AssertionError('External dependency accepted')
print('CONSTRAINED_SOURCE_CONTRACT_OK')
