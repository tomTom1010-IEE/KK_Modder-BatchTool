"""Opt-in, read-only archive smoke test. Never writes to the input directory.

Run: python tests/test_influence_archived_context.py CONTEXT_DIR OUTPUT_DIR
"""
import json,sys,time
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'kk_vrc_cloth_tools'))
import influence_policy as ip
import weight_optimizer as opt
import weight_features as core

if __name__=='__main__':
    source,output=map(Path,sys.argv[1:])
    if source.resolve()==output.resolve():raise ValueError('Use a separate output directory')
    with np.load(source/'context.npz') as z:a={k:z[k] for k in z.files}
    m=json.loads((source/'context.json').read_text(encoding='utf-8'))
    if m['arrays_digest']!=core.digest({k:v.tolist() for k,v in a.items()}):raise ValueError('Archive arrays changed')
    train=np.array([i for i,spec in enumerate(m['poses']) if spec['kind']!='holdout'])
    posed=opt.skin(a['source_rest'],a['source_matrices'],a['source_weights'])
    prior=(a['target_frames'][0,:,:3,:3]@np.swapaxes(a['source_frames'][0,:,:3,:3],-1,-2))*a['anchor_length_ratio'][:,None,None]
    jac,_=opt.fit_rest_transport(a['source_rest'],a['target_rest'],a['edges'],a['triangles'],prior)
    reference=opt.motion_reference(a['source_rest'],a['target_rest'],posed,a['source_frames'],a['target_frames'],jac)
    pw=np.array([(.2 if m['poses'][i]['kind']=='random' else 1.)/sum(m['poses'][j]['kind']==m['poses'][i]['kind'] for j in train) for i in train])
    start=time.perf_counter()
    w,report=opt.solve_limited(a['target_rest'],a['target_matrices'][train],a['initial'],reference[train],
        a['regions'],a['budgets'],a['fixed'],a['candidates'],a.get('smooth_edges',a['edges']),pw,
        influence_policy={'max_influences':4},selected=a['selected'],delta_limits=a.get('delta_limits'),
        progress=lambda event:print(json.dumps(event),flush=True))
    verdict=ip.validate_result(a['initial'],w,a['regions'],a['budgets'],a['fixed'],a['candidates'],{'max_influences':4},
                               selected=a['selected'],delta_limits=a.get('delta_limits'))
    holdout=np.array([i for i,spec in enumerate(m['poses']) if spec['kind']=='holdout'])
    mask=a['budgets'][:,:5].sum(1)>0
    before=opt.skin(a['target_rest'],a['target_matrices'][holdout],a['initial'])
    after=opt.skin(a['target_rest'],a['target_matrices'][holdout],w)
    report.update(source=str(source),seconds=time.perf_counter()-start,independent_constraints=verdict,
                  holdout_before_rms=float(np.sqrt(np.mean(np.sum((before[:,mask]-reference[holdout][:,mask])**2,axis=2)))),
                  holdout_after_rms=float(np.sqrt(np.mean(np.sum((after[:,mask]-reference[holdout][:,mask])**2,axis=2)))),
                  collision_validation='NOT_RUN',runtime_validation='NOT_TESTED')
    output.mkdir(parents=True,exist_ok=True)
    np.savez_compressed(output/'candidate.npz',weights=w)
    (output/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k not in ['influence_support','independent_constraints']},indent=2))
    print(json.dumps(dict(over_limit=len(verdict['over_limit_vertices']),constraints_ok=verdict['constraints_ok'])))
    if report['status']!='solved' or not verdict['constraints_ok']:raise SystemExit(1)
