"""Offline CLI: python optimizer_cli.py CONTEXT_DIR [--contacts] [--vertex-only]."""
import argparse
import json
from pathlib import Path
import time
import numpy as np
import weight_optimizer as opt
import weight_features as core
from optimizer_profiles import MACRO
from optimizer_scope import pure_dynamic_vertices, check_body_admission, check_source_deformation


def run(directory, contacts=False, vertex_only=False):
    start=time.perf_counter();directory=Path(directory)
    with np.load(directory/'context.npz') as z:a={k:z[k] for k in z.files}
    m=json.loads((directory/'context.json').read_text(encoding='utf-8'))
    check_body_admission(m)
    if m['arrays_digest']!=core.digest({k:v.tolist() for k,v in a.items()}):raise ValueError('Context arrays changed')
    if m['context_id']!=core.digest({k:v for k,v in m.items() if k!='context_id'}):raise ValueError('Context metadata changed')
    target_baseline=opt.skin(a['target_rest'],a['target_matrices'],a['initial'])
    lbs_error=float(np.linalg.norm(target_baseline-a['actual_target'],axis=2).max())
    if lbs_error>1e-5:raise ValueError(f'Blender LBS mismatch {lbs_error}')
    source_posed=opt.skin(a['source_rest'],a['source_matrices'],a['source_weights'])
    source_lbs_error=check_source_deformation(a)
    rs=a['source_frames'][0,:,:3,:3];rt=a['target_frames'][0,:,:3,:3]
    prior=(rt@np.swapaxes(rs,-1,-2))*a.get('anchor_length_ratio',np.ones(len(rs)))[:,None,None]
    jac,fallback=opt.fit_rest_transport(a['source_rest'],a['target_rest'],a['edges'],a['triangles'],prior)
    reference=opt.motion_reference(a['source_rest'],a['target_rest'],source_posed,a['source_frames'],a['target_frames'],jac)
    train=np.array([i for i,p in enumerate(m['poses']) if p['kind']!='holdout'])
    holdout=np.array([i for i,p in enumerate(m['poses']) if p['kind']=='holdout'])
    if not len(holdout):raise ValueError('Independent holdout poses required')
    weights=[]
    for i in train:
        kind=m['poses'][i]['kind']
        group=[float(m['poses'][j].get('weight',1.)) for j in train if m['poses'][j]['kind']==kind]
        if any(w<0 or not np.isfinite(w) for w in group) or sum(group)<=0:raise ValueError('Invalid pose importance')
        weights.append((.2 if kind=='random' else 1.)*float(m['poses'][i].get('weight',1.))/sum(group))
    surfaces={}
    if contacts:
        surfaces={k:opt.TriangleSurface(a['body_poses'][i],a['body_triangles']) for k,i in enumerate(train)}
    extra_samples={}
    seed_path=directory/'validation.json'
    if contacts and seed_path.exists():
        seed=json.loads(seed_path.read_text(encoding='utf-8'))
        if seed['context_id']!=m['context_id']:raise ValueError('Stale contact validation seed')
        for k,i in enumerate(train):
            item=seed['poses'][int(i)]
            ids=sorted({pair[0] for stage in ['before','after'] for pair in item[stage].get('triangle_pairs',item[stage]['first_triangle_pairs'])})
            if ids:
                tri=a['triangles'][ids]
                extra_samples[k]=(np.repeat(tri,4,axis=0),np.tile([[1/3]*3,[.5,.5,0],[0,.5,.5],[.5,0,.5]],(len(tri),1)))
    _,area=opt.surface_geometry(a['target_rest'],a['triangles'])
    excluded=pure_dynamic_vertices(a['budgets'])
    local=m.get('local_refinement',{})
    if local:
        selected_mask=np.isin(np.arange(len(area)),a['selected'])
        area*=selected_mask
        excluded |= ~selected_mask
    out,report=opt.solve(a['target_rest'],a['target_matrices'][train],a['initial'],reference[train],
        a['regions'],a['budgets'],a['fixed'],a['candidates'],a.get('smooth_edges',a['edges']),weights,
        selected=a['selected'],surfaces=surfaces,smooth=0 if vertex_only else local.get('smooth',MACRO['smooth']),prior=local.get('prior',MACRO['prior']),vertex_weights=area,
        delta_limits=a.get('delta_limits'),residual_scale=local.get('residual_scale'),
        trust=local.get('trust',MACRO['trust']),max_contact_steps=local.get('max_contact_steps',MACRO['max_contact_steps']),
        contact_samples=extra_samples,contact_excluded=excluded,progress=lambda event:print(json.dumps(event),flush=True))
    posed=opt.skin(a['target_rest'],a['target_matrices'],out)
    error=np.linalg.norm(posed-reference,axis=2);old_error=np.linalg.norm(target_baseline-reference,axis=2)
    def metrics(e,ids):
        x=e[ids]
        if local:x=x[:,a['selected']]
        return {'rms':float(np.sqrt(np.mean(x*x))),'p95':float(np.quantile(x,.95)),'max':float(x.max())}
    report.update(context_id=m['context_id'],candidate_digest=core.digest(out.tolist()),reference_digest=core.digest(reference.tolist()),
        solver='OSQP',elapsed_seconds=time.perf_counter()-start,lbs_max_error=lbs_error,
        source_lbs_max_error=source_lbs_error,
        transport_fallback_vertices=len(fallback),train_before=metrics(old_error,train),train_after=metrics(error,train),
        holdout_before=metrics(old_error,holdout),holdout_after=metrics(error,holdout),
        rest_reference_error=float(np.linalg.norm(reference[0]-a['target_rest'],axis=1).max()),
        collision_validation='pending Blender face-level and sampled-surface validation',accepted=False,
        enabled_contact_iterations=contacts,pose_names=[p['name'] for p in m['poses']],
        max_region_error=max(float(np.max(abs(out[:,a['regions']==r].sum(axis=1)-a['budgets'][:,r]))) for r in range(6)))
    prefix='contact_' if contacts else ''
    np.savez_compressed(directory/(prefix+'candidate.npz'),weights=out,positions=posed,reference=reference,baseline=target_baseline)
    (directory/(prefix+'report.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('directory');parser.add_argument('--contacts',action='store_true');parser.add_argument('--vertex-only',action='store_true')
    args=parser.parse_args();run(args.directory,args.contacts,args.vertex_only)
