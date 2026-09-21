"""Reviewed flat-shoe migration: native sampling, extension, field, gap A/B.

Explicit config rather than implicit bone-name or material classification.
All durable writes are new mesh copies; source, target and body are stamped.
"""
import json
import math
from pathlib import Path
import bpy
import numpy as np
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree
from . import shoe_field as field, weights_features as wf
from . import shoe_presets
from . import weights_optimization as kin, weights_transfer as transfer
from .optimizer_validation import check_surface


def clone(obj, name):
    out=obj.copy();out.data=obj.data.copy();out.name=name
    bpy.context.collection.objects.link(out);out.hide_viewport=False;out.hide_set(True)
    return out


def remove_temp(obj):
    mesh=obj.data;bpy.data.objects.remove(obj,do_unlink=True)
    if not mesh.users:bpy.data.meshes.remove(mesh)


def write(obj,names,w):
    if any(g.lock_weight for g in obj.vertex_groups):raise ValueError('Locked groups')
    if not np.isfinite(w).all() or np.min(w)<-1e-9 or np.max(abs(w.sum(1)-1))>1e-6:
        raise ValueError('Invalid normalized output')
    obj.vertex_groups.clear()
    for j,n in enumerate(names):
        group=obj.vertex_groups.new(name=n)
        for i in np.flatnonzero(w[:,j]>0):group.add([int(i)],float(w[i,j]),'REPLACE')


def barycentric(p,t):
    v0,v1,v2=t[1]-t[0],t[2]-t[0],p-t[0]
    a,b,c,d,e=v0@v0,v0@v1,v1@v1,v2@v0,v2@v1
    den=a*c-b*b
    if den<1e-22:raise ValueError('Degenerate reference triangle')
    y,z=(c*d-b*e)/den,(a*e-b*d)/den
    return np.array([1-y-z,y,z])


def frames(tri):
    x=tri[:,1]-tri[:,0];x/=np.maximum(np.linalg.norm(x,axis=1)[:,None],1e-15)
    z=np.cross(x,tri[:,2]-tri[:,0]);z/=np.maximum(np.linalg.norm(z,axis=1)[:,None],1e-15)
    y=np.cross(z,x)
    return np.stack([x,y,z],axis=2)


def posed(rig, poses, callback):
    saved={b.name:(b.rotation_mode,list(b.location),list(b.rotation_euler),list(b.rotation_quaternion),list(b.rotation_axis_angle),list(b.scale)) for b in rig.pose.bones}
    mode=rig.data.pose_position
    try:
        for spec in poses:
            rig.data.pose_position='POSE'
            for b in rig.pose.bones:b.matrix_basis=Matrix.Identity(4)
            for control in spec.get('controls',[]):
                n=control['bone'];axis=Vector(control['axis']).normalized()
                local=(rig.matrix_world@rig.data.bones[n].matrix_local).to_3x3().inverted()@axis
                rig.pose.bones[n].matrix_basis @= Matrix.Rotation(math.radians(control['degrees']),4,local.normalized())
            bpy.context.view_layer.update();callback(spec)
    finally:
        for b in rig.pose.bones:
            m,l,e,q,a,s=saved[b.name];b.rotation_mode=m;b.location=l;b.rotation_euler=e;b.rotation_quaternion=q;b.rotation_axis_angle=a;b.scale=s
        rig.data.pose_position=mode;bpy.context.view_layer.update()


def skin_basis(rig,names,xyz):
    mat=kin._matrices(rig,names)
    return np.einsum('bij,vj->vbi',mat[:,:3,:3],xyz)+mat[None,:,:3,3]


def run(source,target,body,config,directory,field_only=False):
    """Run explicit reviewed configuration, write A and independently gated B.

config.sides: source_body, target_body, dynamic, foot, toes, forward, up.
Reviewed masks are exact source indices. Unknown source groups/overlaps abort.
"""
    config=shoe_presets.resolve(config)
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    def save(name,value):
        (directory/name).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
    def progress(message):save('progress.json',{'stage':message})
    progress('preflight')
    if not config.get('reviewed_dynamic_policy'):raise ValueError('Agent/manual dynamic review required')
    sr,tr,br=kin._rig(source),kin._rig(target),kin._rig(body)
    if tr!=br or sr==tr:raise ValueError('Invalid source/target armature assignment')
    if wf.topology(source)!=wf.topology(target):raise ValueError('Index/topology mismatch')
    stamps={o.name:wf.stamp(o) for o in [source,target,body]}
    save('config.json',config);save('before.json',{'stamps':stamps,'source':wf.read_weights(source),'target':wf.read_weights(target)})
    rows=wf.read_weights(source);support=wf.body_weight_support(body,target)
    bodyrows=wf.read_weights(body);xyz=kin._world_vertices(target);bodyxyz=kin._world_vertices(body)
    body.data.calc_loop_triangles();target.data.calc_loop_triangles()
    bt=np.array([t.vertices[:] for t in body.data.loop_triangles],int)
    ct=np.array([t.vertices[:] for t in target.data.loop_triangles],int)
    edges=np.array([e.vertices[:] for e in target.data.edges],int)
    specified=[n for side in config['sides'] for n in side['source_body']+side['dynamic']]
    used={n for row in rows for n,w in row.items() if w>0}
    if len(specified)!=len(set(specified)) or used-set(specified):raise ValueError('Overlapping or unclassified source groups')
    if any(n not in sr.data.bones or not sr.data.bones[n].use_deform for n in used):
        raise ValueError('Source contains unbound/nondeforming influences; review roles explicitly')
    names=[n for side in config['sides'] for n in side['target_body']+side['dynamic']]
    if len(names)!=len(set(names)):raise ValueError('Overlapping target side groups')
    for side in config['sides']:
        if set(side['target_body'])-support:raise ValueError('Target candidates lack actual body weights')
        if any(n not in tr.data.bones or not tr.data.bones[n].use_deform for n in side['dynamic']):raise ValueError('Unbound dynamics')
    total=np.array([sum(r.values()) for r in rows])
    if np.any(total<=0):raise ValueError('Unweighted source')
    output=np.zeros((len(rows),len(names)));budgets=[];contexts=[];audit=[]
    # Sample rest mesh explicitly; do not sample a posed body against rest shoes.
    tempbody=clone(body,'__shoe_rest_body');tempbody.modifiers.clear();tempbody.hide_set(False)
    probe=clone(target,'__shoe_native_probe');probe.modifiers.clear();probe.hide_set(False)
    try:
        for side in config['sides']:
            progress('native sampling and field: '+side['name'])
            bs=np.array([sum(r.get(n,0) for n in side['source_body']) for r in rows])/total
            ds=np.array([sum(r.get(n,0) for n in side['dynamic']) for r in rows])/total
            budgets.append(bs);ids=np.flatnonzero(bs>0);sideids=np.flatnonzero(bs+ds>1e-8)
            j=[names.index(n) for n in side['target_body']]
            for n in side['dynamic']:output[:,names.index(n)]=np.array([r.get(n,0) for r in rows])/total
            forward=np.array(side['forward'],float)
            if forward.shape!=(3,) or not np.isfinite(forward).all() or np.linalg.norm(forward)<1e-8:
                raise ValueError('Explicit finite nonzero anatomical forward vector required')
            forward/=np.linalg.norm(forward)
            origin=np.array(tr.matrix_world@tr.data.bones[side['foot']].head_local)
            footmass=np.array([sum(r.get(n,0) for n in side['target_body']) for r in bodyrows])
            footverts=np.flatnonzero(footmass>.5)
            if len(footverts)<10:raise ValueError('Insufficient body foot support')
            # Front limit comes from weighted body geometry, not toe bone length.
            longitudinal=(bodyxyz-origin)@forward;cap=float(np.max(longitudinal[footverts]))
            scale=max(float(np.linalg.norm(np.array(tr.matrix_world@tr.data.bones[side['toes']].head_local)-origin)),1e-5)
            ext=np.maximum(0,(xyz[ids]-origin)@forward-cap) if config.get("extend_toe",True) else np.zeros(len(ids))
            query=xyz.copy();query[ids]-=ext[:,None]*forward
            inv=probe.matrix_world.inverted()
            for v,p in zip(probe.data.vertices,query):v.co=inv@Vector(p)
            probe.data.update()
            sampled=transfer.transfer_source_body_weights_to_target(tempbody,probe,set(side['target_body']))
            s=np.array([[sampled[i].get(n,0) for n in side['target_body']] for i in ids]);mass=s.sum(1)
            if np.any(mass<config.get('minimum_sample_mass',.01)):
                raise ValueError('Untrusted sample mass requires explicit proximal/side extension; no silent zero fill')
            p=s/mass[:,None]
            # Spatial reference restricted to body triangles dominated by this side.
            tris=bt[np.min(footmass[bt],axis=1)>.25]
            bvh=BVHTree.FromPolygons(bodyxyz.tolist(),tris.tolist(),all_triangles=True)
            refs=[];bc=[];dist=[]
            for pos in xyz[ids]:
                hit,normal,index,d=bvh.find_nearest(Vector(pos))
                if hit is None:raise ValueError('Missing body reference')
                refs.append(tris[index]);bc.append(barycentric(np.array(hit),bodyxyz[tris[index]]));dist.append(d)
            refs=np.array(refs);bc=np.array(bc);dist=np.array(dist)
            conf=np.maximum(.05,1/(1+(dist/(.35*scale))**2))
            remap=np.full(len(rows),-1,int);remap[ids]=np.arange(len(ids))
            ee=edges[(remap[edges]>=0).all(1)];ee=remap[ee]
            # Local robust disagreement lowers fidelity only on outliers.
            acc=np.zeros_like(p);degree=np.bincount(ee.ravel(),minlength=len(ids))
            np.add.at(acc,ee[:,0],p[ee[:,1]]);np.add.at(acc,ee[:,1],p[ee[:,0]])
            disagreement=np.linalg.norm(p-acc/np.maximum(degree,1)[:,None],axis=1)
            conf/=1+(disagreement/.25)**2
            allowed=p>0
            for _ in range(config.get('candidate_rings',2)):
                previous=allowed.copy()
                np.logical_or.at(allowed,ee[:,0],previous[ee[:,1]])
                np.logical_or.at(allowed,ee[:,1],previous[ee[:,0]])
            smooth,report=field.smooth(p,ee,conf,config.get('smoothing',.7),allowed=allowed)
            if not report['converged']:raise ValueError('Field smoothing did not converge')
            output[np.ix_(ids,j)]=smooth*bs[ids,None]
            resttri=bodyxyz[refs];anchor=np.einsum('vi,vic->vc',bc,resttri)
            frame=frames(resttri);offset=np.einsum('vji,vj->vi',frame,xyz[ids]-anchor)
            contexts.append(dict(ids=ids,j=j,budget=bs[ids],p=smooth,edges=ee,refs=refs,bc=bc,offset=offset,scale=scale,dist=dist,confidence=conf,allowed=allowed))
            audit.append({'side':side['name'],'body_vertices':len(ids),'extended_vertices':int(sum(ext>1e-8)),
                          'sample_mass_min':float(mass.min()),'scale':scale,'smoothing':report,
                          'roughness_before':float(np.mean((p[ee[:,0]]-p[ee[:,1]])**2)),
                          'roughness_after':float(np.mean((smooth[ee[:,0]]-smooth[ee[:,1]])**2))})
    finally:remove_temp(probe);remove_temp(tempbody)
    if np.max(abs(output.sum(1)-1))>1e-6:raise ValueError('Source budget coverage mismatch')
    baseline=clone(target,config.get('prefix','Shoes.Flat')+'.A.Field');write(baseline,names,output)
    baseline.hide_set(False)
    np.savez_compressed(directory/'initial.npz',weights=output,names=names)
    checkpoint={"config":config,"names":names,"audit":audit,"stamps":stamps,
                "baseline":baseline.name,"baseline_stamp":wf.stamp(baseline)}
    arrays={"output":output,"xyz":xyz,"bt":bt,"ct":ct,"budgets":np.array(budgets)}
    for i,ctx in enumerate(contexts):
        for key,value in ctx.items():arrays[f"ctx_{i}_{key}"]=np.asarray(value)
    np.savez_compressed(directory/'field-context.npz',**arrays)
    import hashlib
    checkpoint['arrays_sha256']=hashlib.sha256((directory/'field-context.npz').read_bytes()).hexdigest()
    save('field-context.json',checkpoint)
    if field_only:
        report={'baseline':baseline.name,'optimized':None,'accepted':False,'stage':'FIELD',
                'field':audit,'protected_unchanged':all(wf.stamp(bpy.data.objects[n])==v for n,v in stamps.items())}
        if not report['protected_unchanged']:raise ValueError('Protected state changed')
        save('report.json',report);progress('field complete');return report
    return _finish(source,target,body,config,directory,baseline,output,names,xyz,bt,ct,budgets,contexts,audit,stamps)


def resume_gap(source,target,body,config,directory):
    import hashlib
    directory=Path(directory)
    meta=json.loads((directory/'field-context.json').read_text(encoding='utf-8'))
    if hashlib.sha256((directory/'field-context.npz').read_bytes()).hexdigest()!=meta['arrays_sha256']:
        raise ValueError('Field checkpoint changed')
    config=shoe_presets.resolve(config)
    flexible={'poses','pose_preset','pose_preset_resolved','optimize_gap','prior','prefix'}
    if {k:v for k,v in config.items() if k not in flexible}!={k:v for k,v in meta['config'].items() if k not in flexible}:
        raise ValueError('Sampling or region configuration changed; regenerate A')
    if [o.name for o in [source,target,body]]!=[meta['config'][k] for k in ['source','target','body']]:
        raise ValueError('Input objects changed')
    baseline=bpy.data.objects.get(meta['baseline'])
    if baseline is None or wf.stamp(baseline)!=meta['baseline_stamp']:raise ValueError('A copy or pose changed; regenerate A')
    if any(wf.stamp(bpy.data.objects[n])!=v for n,v in meta['stamps'].items()):raise ValueError('Input mesh, weights, or pose changed; regenerate A')
    with np.load(directory/'field-context.npz',allow_pickle=False) as data:
        contexts=[]
        for i in range(len(config['sides'])):
            prefix=f'ctx_{i}_';contexts.append({k[len(prefix):]:data[k] for k in data.files if k.startswith(prefix)})
        return _finish(source,target,body,config,directory,baseline,data['output'],meta['names'],data['xyz'],data['bt'],data['ct'],data['budgets'],contexts,meta['audit'],meta['stamps'])


def _finish(source,target,body,config,directory,baseline,output,names,xyz,bt,ct,budgets,contexts,audit,stamps):
    def save(name,value):(directory/name).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
    def progress(message):save('progress.json',{'stage':message})
    save('optimization-config.json',config)
    tr=kin._rig(target);rows=wf.read_weights(source);total=np.array([sum(r.values()) for r in rows])
    trained=[];validation=[];max_lbs=0.
    progress('pose sampling')
    def sample(spec):
        nonlocal max_lbs
        basis=skin_basis(tr,names,xyz);actual=kin._world_vertices(baseline,True)
        predicted=np.einsum('vb,vbc->vc',output,basis)
        error=float(np.max(abs(predicted-actual)));max_lbs=max(max_lbs,error)
        if error>2e-5:raise ValueError('Blender/LBS mismatch '+str(error))
        record={'spec':spec,'basis':basis,'body':kin._world_vertices(body,True)}
        (validation if spec.get('validation') else trained).append(record)
    posed(tr,config['poses'],sample)
    optimized=output.copy();solver=[];optimize_gap=bool(config.get('optimize_gap',True))
    for ctx in (contexts if optimize_gap else []):
        progress('gap quadratic')
        ids,j=ctx['ids'],ctx['j'];N,K=len(ids),len(j);H=np.zeros((N,K,K));rhs=np.zeros((N,K))
        for record in trained:
            bodypose=record['body'];tri=bodypose[ctx['refs']];frame=frames(tri)
            anchor=np.einsum('vi,vic->vc',ctx['bc'],tri)
            goal=anchor+np.einsum('vij,vj->vi',frame,ctx['offset'])
            basis=record['basis'][ids];fixed=np.einsum('vb,vbc->vc',output[ids],basis)-np.einsum('vb,vbc->vc',output[np.ix_(ids,j)],basis[:,j])
            D=basis[:,j]*ctx['budget'][:,None,None]
            D=np.einsum('vci,vkc->vik',frame,D)/ctx['scale']
            y=np.einsum('vci,vc->vi',frame,goal-fixed)/ctx['scale']
            # On the simplex, subtracting a common column is exact and removes
            # large world-coordinate/common-motion terms from the Hessian.
            y-=D[:,:,0];D-=D[:,:,0,None].copy()
            # Small tangential term prevents sliding; reduced trust on remote tips.
            axisw=np.array([.03,.03,1.])*float(record['spec'].get('weight',1))
            confidence=1/(1+(ctx['dist']/ctx['scale'])**2)
            H+=np.einsum('vik,vil,i,v->vkl',D,D,axisw,confidence)
            rhs+=np.einsum('vik,vi,i,v->vk',D,y,axisw,confidence)
        pp,rep=field.optimize(ctx['p'],H,rhs,ctx['edges'],prior=config.get('prior',.1),iterations=1500,allowed=ctx['allowed'])
        optimized[np.ix_(ids,j)]=pp*ctx['budget'][:,None];solver.append(rep)
    # Independent pose metrics use actual closest-surface distance and full faces.
    def metrics(w,records):
        gap=[];collisions=[]
        excluded=np.sum(budgets,axis=0)<=1e-8
        for record in records:
            progress('independent validation: '+record['spec']['name'])
            pos=np.einsum('vb,vbc->vc',w,record['basis']);bvh=BVHTree.FromPolygons(record['body'].tolist(),bt.tolist(),all_triangles=True)
            for ctx in contexts:
                for i,d0 in zip(ctx['ids'],ctx['dist']):
                    hit,normal,index,d=bvh.find_nearest(Vector(pos[i]));gap.append((d-d0)**2)
            col=check_surface(pos,ct,record['body'],bt,excluded=excluded)['in_scope']
            col.pop('triangle_pairs',None);collisions.append({'pose':record['spec']['name'],**col})
        return {'distance_rms':float(np.sqrt(np.mean(gap))),'collisions':collisions}
    if not trained or not validation:raise ValueError('Training and independent validation poses required')
    ma=metrics(output,validation);mb=metrics(optimized,validation) if optimize_gap else ma
    accepted=optimize_gap and all(r['converged'] for r in solver) and mb['distance_rms']<=ma['distance_rms']+1e-7
    for a,b in zip(ma['collisions'],mb['collisions']):
        accepted &= b['intersecting_triangle_pairs']<=a['intersecting_triangle_pairs'] and b['penetrating_samples']<=a['penetrating_samples'] and b['max_oriented_depth']<=a['max_oriented_depth']+1e-5
    result={'schema':1,'native_method':'POLYINTERP_NEAREST','baseline':baseline.name,'optimized':None,'accepted':bool(accepted),
            'optimize_gap':optimize_gap,
            'field':audit,'solver':solver,'lbs_error':max_lbs,'baseline_validation':ma,'optimized_validation':mb,
            'limitations':['Discrete poses only; no continuous collision guarantee','No shoe self-collision or other clothing collision','Fixed reference quadratic, not exact nonlinear distance minimization']}
    if accepted:
        candidate=clone(target,config.get('prefix','Shoes.Flat')+'.B.Gap');write(candidate,names,optimized)
        # Actual Blender evaluation after float32 writeback, not just numerical LBS.
        actual_error=[]
        candidate.hide_set(False)
        def verify(spec):
            predicted=np.einsum('vb,vbc->vc',optimized,skin_basis(tr,names,xyz))
            actual_error.append(float(np.max(abs(predicted-kin._world_vertices(candidate,True)))))
        posed(tr,config['poses'],verify)
        if max(actual_error)>2e-5:remove_temp(candidate);raise ValueError('Candidate writeback evaluation mismatch')
        result['optimized']=candidate.name;result['writeback_lbs_error']=max(actual_error)
        baseline.hide_set(True)
    result['protected_unchanged']=all(wf.stamp(bpy.data.objects[n])==s for n,s in stamps.items())
    if not result['protected_unchanged']:raise ValueError('Protected scene state changed')
    result['actual_writeback']={}
    for object_name in [baseline.name]+([result['optimized']] if result['optimized'] else []):
        obj=bpy.data.objects[object_name];actual=kin._dense(wf.read_weights(obj),names)
        expected_dynamic={n:np.array([r.get(n,0) for r in rows])/total for side in config['sides'] for n in side['dynamic']}
        errors={'sum':float(np.max(abs(actual.sum(1)-1))),
                'budget':max(float(np.max(abs(actual[:,[names.index(n) for n in side['target_body']]].sum(1)-bs))) for side,bs in zip(config['sides'],budgets)),
                'dynamic':max(float(np.max(abs(actual[:,names.index(n)]-w))) for n,w in expected_dynamic.items()) if expected_dynamic else 0.,
                'geometry':float(np.max(abs(kin._world_vertices(obj)-xyz)))}
        if max(errors.values())>1e-6:raise ValueError('Actual writeback invariant failed: '+str(errors))
        result['actual_writeback'][object_name]=errors
    for label,w in [('A',output),('B',optimized)]:
        result[label+'_sum_error']=float(np.max(abs(w.sum(1)-1)))
        result[label+'_budget_error']=max(float(np.max(abs(w[:,[names.index(n) for n in side['target_body']]].sum(1)-bs))) for side,bs in zip(config['sides'],budgets))
        dyn=[names.index(n) for s in config['sides'] for n in s['dynamic']]
        result[label+'_dynamic_error']=float(np.max(abs(w[:,dyn]-output[:,dyn]))) if dyn else 0.
    np.savez_compressed(directory/'candidate.npz',weights=optimized,names=names)
    save('report.json',result)
    progress('complete')
    return result


class KKVRC_OT_flat_shoe_config(bpy.types.Operator):
    bl_idname='kkvrc.flat_shoe_config'
    bl_label='Load reviewed configuration and generate flat-shoe A/B copies'
    bl_description='Read bones, lace reviews, directions, and poses from JSON; preserve originals and output comparison copies'
    filepath:bpy.props.StringProperty(subtype='FILE_PATH')
    filter_glob:bpy.props.StringProperty(default='*.json',options={'HIDDEN'})
    pose_mode:bpy.props.EnumProperty(name='Shoe poses',items=[('FLAT_SHOE_V1','Flat-shoe standard + random auxiliary poses','7 standard training poses and 4 held-out validation poses'),('CONFIG','Use pose settings from file','Preserve poses or pose_preset from JSON')],default='FLAT_SHOE_V1')
    random_enabled:bpy.props.BoolProperty(name='Low-weight random auxiliary poses',default=True)
    random_count:bpy.props.IntProperty(name='Random pose count',default=6,min=0,max=64)
    random_weight:bpy.props.FloatProperty(name='Relative weight per pose',default=.15,min=.001,max=.99)
    seed:bpy.props.IntProperty(name='Random seed',default=20260919,min=0)
    def draw(self,context):
        layout=self.layout;layout.prop(self,'pose_mode')
        if self.pose_mode=='FLAT_SHOE_V1':
            layout.prop(self,'random_enabled')
            col=layout.column();col.enabled=self.random_enabled
            for prop in ['random_count','random_weight','seed']:col.prop(self,prop)
            layout.label(text='Total random weight is capped at 20% of standard pose weight')
    def invoke(self,context,event):
        context.window_manager.fileselect_add(self);return {'RUNNING_MODAL'}
    def execute(self,context):
        from datetime import datetime
        try:
            config=json.loads(Path(self.filepath).read_text(encoding='utf-8-sig'))
            if self.pose_mode=='FLAT_SHOE_V1':
                config['pose_preset']={'id':self.pose_mode,'random_enabled':self.random_enabled,
                    'random_count':self.random_count,'random_weight':self.random_weight,'seed':self.seed}
            if context.mode!='OBJECT':bpy.ops.object.mode_set(mode='OBJECT')
            source,target,body=[bpy.data.objects[config[k]] for k in ['source','target','body']]
            directory=Path(self.filepath).parent/('run-'+datetime.now().strftime('%Y%m%d-%H%M%S'))
            result=run(source,target,body,config,directory)
            obj=bpy.data.objects[result['optimized'] or result['baseline']]
            bpy.ops.object.select_all(action='DESELECT');target.hide_set(True)
            obj.hide_set(False);obj.select_set(True);context.view_layer.objects.active=obj
            self.report({'INFO'},'Flat-shoe results: '+obj.name+'; report: '+str(directory))
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'},str(e));return {'CANCELLED'}


class KKVRC_PT_flat_shoe(bpy.types.Panel):
    bl_label='Complex Flat Shoes (Reviewed Configuration)'
    bl_idname='KKVRC_PT_flat_shoe'
    bl_space_type='VIEW_3D';bl_region_type='UI';bl_category='KK/VRC Tools'
    bl_options={'DEFAULT_CLOSED'}
    def draw(self,context):
        self.layout.label(text='Native sampling → extension → continuity → gap comparison')
        self.layout.label(text='Review lace and bone settings first; high heels are not supported')
        self.layout.operator('kkvrc.flat_shoe_config')


CLASSES=(KKVRC_OT_flat_shoe_config,)
