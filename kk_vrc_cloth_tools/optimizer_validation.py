"""Blender-only independent collision/quality validation of offline candidates.

No scene mutation. Triangle crossings plus vertex, edge-midpoint and face-center
side tests; not a continuous-time collision certificate or proof for all poses.
"""
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.geometry import intersect_ray_tri
from . import weight_features as core
from .optimizer_scope import pure_dynamic_vertices, check_body_admission, check_source_deformation


def _crosses(a,b,eps):
    a,b=[Vector(v) for v in a],[Vector(v) for v in b]
    for tri,other in ((a,b),(b,a)):
        for k in range(3):
            origin=tri[k];direction=tri[(k+1)%3]-origin
            hit=intersect_ray_tri(other[0],other[1],other[2],direction,origin,True)
            if hit is not None and direction.length_squared>eps*eps:
                t=(hit-origin).dot(direction)/direction.length_squared
                if eps<t<1-eps:return True
    return False


def check_surface(cloth,cloth_triangles,body,body_triangles,tolerance=1e-4,excluded=None):
    excluded=np.zeros(len(cloth),bool) if excluded is None else np.asarray(excluded,bool)
    if excluded.shape!=(len(cloth),):raise ValueError('Invalid scope mask')
    face_scope=np.any(~excluded[cloth_triangles],axis=1)
    bt=BVHTree.FromPolygons(body.tolist(),body_triangles.tolist(),all_triangles=True)
    ct=BVHTree.FromPolygons(cloth.tolist(),cloth_triangles.tolist(),all_triangles=True)
    pairs=ct.overlap(bt)
    intersections=[];ambiguous=0;scoped_ambiguous=0;ambiguous_vertices=set()
    for i,j in pairs:
        a,b=cloth[cloth_triangles[i]],body[body_triangles[j]]
        if _crosses(a,b,1e-8):intersections.append((i,j))
        else:
            na=np.cross(a[1]-a[0],a[2]-a[0]);nb=np.cross(b[1]-b[0],b[2]-b[0])
            norm=np.linalg.norm(na)*np.linalg.norm(nb)
            if norm>1e-20 and np.linalg.norm(np.cross(na,nb))<1e-8*norm:
                if abs((a[0]-b[0])@nb)/np.linalg.norm(nb)<tolerance:
                    ambiguous+=1;scoped_ambiguous+=int(face_scope[i])
                    if face_scope[i]:ambiguous_vertices.update(map(int,cloth_triangles[i]))
    triangles=cloth[cloth_triangles]
    samples=np.vstack([cloth,triangles.mean(axis=1),
        (triangles[:,0]+triangles[:,1])/2,(triangles[:,1]+triangles[:,2])/2,(triangles[:,2]+triangles[:,0])/2])
    sample_scope=np.concatenate([~excluded,face_scope,
        np.any(~excluded[cloth_triangles[:,[0,1]]],axis=1),
        np.any(~excluded[cloth_triangles[:,[1,2]]],axis=1),
        np.any(~excluded[cloth_triangles[:,[2,0]]],axis=1)])
    count=0;depth=0.;scoped_count=0;scoped_depth=0.;problem_vertices=set(ambiguous_vertices)
    for sample_id,(point,in_scope) in enumerate(zip(samples,sample_scope)):
        hit,normal,index,distance=bt.find_nearest(Vector(point))
        if hit is None:raise ValueError('Collision query failed')
        side=(Vector(point)-hit).dot(normal)
        if side < -tolerance:
            count+=1;depth=max(depth,-side)
            if in_scope:
                scoped_count+=1;scoped_depth=max(scoped_depth,-side)
                if sample_id<len(cloth):problem_vertices.add(sample_id)
                else:problem_vertices.update(map(int,cloth_triangles[(sample_id-len(cloth))%len(cloth_triangles)]))
    scoped_pairs=[pair for pair in intersections if face_scope[pair[0]]]
    for i,j in scoped_pairs:problem_vertices.update(map(int,cloth_triangles[i]))
    return {'intersecting_triangle_pairs':len(intersections),'first_triangle_pairs':intersections[:20],'triangle_pairs':intersections,
            'ambiguous_coplanar_pairs':ambiguous,'penetrating_samples':count,'max_oriented_depth':depth,
            'sample_count':len(samples),
            'in_scope':{'intersecting_triangle_pairs':len(scoped_pairs),'triangle_pairs':scoped_pairs,
                        'ambiguous_coplanar_pairs':scoped_ambiguous,'penetrating_samples':scoped_count,
                        'max_oriented_depth':scoped_depth,'problem_vertices':sorted(problem_vertices)},
            'excluded':{'intersecting_triangle_pairs':len(intersections)-len(scoped_pairs),
                        'ambiguous_coplanar_pairs':ambiguous-scoped_ambiguous,'penetrating_samples':count-scoped_count}}


def validate(arrays,metadata,candidate,report,tolerance=1e-4):
    check_body_admission(metadata)
    if metadata['context_id']!=core.digest({k:v for k,v in metadata.items() if k!='context_id'}):raise ValueError('Context metadata changed')
    if metadata['arrays_digest']!=core.digest({k:v.tolist() for k,v in arrays.items()}):raise ValueError('Context arrays changed')
    source_lbs_error=check_source_deformation(arrays)
    if metadata['context_id']!=report['context_id']:raise ValueError('Wrong report context')
    weights=np.asarray(candidate['weights'])
    if report['candidate_digest']!=core.digest(weights.tolist()):raise ValueError('Candidate weights changed')
    # Recompute positions: do not trust candidate-provided positions or metrics.
    def skin(w):
        out=[]
        for mat in arrays['target_matrices']:
            basis=np.einsum('bij,vj->vbi',mat[:,:3,:3],arrays['target_rest'])+mat[None,:,:3,3]
            out.append(np.einsum('vb,vbc->vc',w,basis))
        return np.array(out)
    positions=skin(weights);baseline=skin(arrays['initial'])
    if not np.allclose(positions,candidate['positions'],atol=1e-7):raise ValueError('Candidate positions changed')
    excluded=pure_dynamic_vertices(arrays['budgets'])
    contact_excluded=excluded.copy()
    outside=~np.isin(np.arange(len(weights)),arrays['selected'])
    if metadata.get('local_refinement'):contact_excluded |= outside
    exterior_geometry_unchanged=bool(np.max(abs(positions[:,outside]-baseline[:,outside]),initial=0)<1e-8)
    per_pose=[]
    for k,spec in enumerate(metadata['poses']):
        before=check_surface(baseline[k],arrays['triangles'],arrays['body_poses'][k],arrays['body_triangles'],tolerance,contact_excluded)
        after=check_surface(positions[k],arrays['triangles'],arrays['body_poses'][k],arrays['body_triangles'],tolerance,contact_excluded)
        per_pose.append({'name':spec['name'],'kind':spec['kind'],'before':before,'after':after})
    contact_ok=all(all(item['after']['in_scope'][key]==0 for key in ['intersecting_triangle_pairs','penetrating_samples','ambiguous_coplanar_pairs']) for item in per_pose)
    holdout=[i for i,s in enumerate(metadata['poses']) if s['kind']=='holdout']
    ref=candidate['reference']
    if report.get('reference_digest')!=core.digest(ref.tolist()):raise ValueError('Reference changed or obsolete report')
    if not holdout:raise ValueError('Independent holdout poses required')
    if np.all(excluded):raise ValueError('No body-influenced vertices to optimize')
    motion_scope=~excluded
    if metadata.get('local_refinement'):motion_scope &= np.isin(np.arange(len(excluded)),arrays['selected'])
    old=np.linalg.norm((baseline[holdout]-ref[holdout])[:,motion_scope],axis=2);new=np.linalg.norm((positions[holdout]-ref[holdout])[:,motion_scope],axis=2)
    motion_ok=bool(np.mean(new*new)<=np.mean(old*old)+1e-12 and new.max()<=old.max()+tolerance)
    fixed_ok=bool(np.max(abs(weights[arrays['fixed']]-arrays['initial'][arrays['fixed']]),initial=0)<1e-8)
    local_ok=bool(np.array_equal(weights[outside],arrays['initial'][outside]))
    if 'delta_limits' in arrays:local_ok &= bool(np.all(abs(weights-arrays['initial'])<=arrays['delta_limits'][:,None]+1e-7))
    budget_error=max(float(np.max(abs(weights[:,arrays['regions']==r].sum(axis=1)-arrays['budgets'][:,r]))) for r in range(6))
    dynamic_unchanged=bool(np.max(abs(positions[:,excluded]-baseline[:,excluded]),initial=0)<1e-8)
    # Revalidate earlier candidates without rewriting their original solve reports.
    conflicts=report.get('fixed_contact_conflicts',[])
    legacy_excluded=(report['status']=='fixed_contact_conflict' and bool(conflicts)
        and bool(report.get('history')) and all(h['status']=='solved' for h in report['history'])
        and all(np.all(excluded[np.asarray(c['vertices'],int)[np.asarray(c['barycentric'])>0]]) for c in conflicts))
    non_contact_ok=(report['status']=='solved' or legacy_excluded) and motion_ok and fixed_ok and dynamic_unchanged and local_ok and exterior_geometry_unchanged and budget_error<1e-6
    accepted=non_contact_ok and contact_ok
    return {'schema':2,'context_id':metadata['context_id'],'candidate_digest':core.digest(weights.tolist()),
        'accepted':accepted,'non_contact_ok':bool(non_contact_ok),'contact_ok':contact_ok,'holdout_motion_ok':motion_ok,'fixed_ok':fixed_ok,
        'collision_review_vertices':sorted({i for p in per_pose for i in p['after']['in_scope']['problem_vertices']}),
        'collision_changes':[{'pose':p['name'],
            'new_triangle_pairs':sorted(set(map(tuple,p['after']['in_scope']['triangle_pairs']))-set(map(tuple,p['before']['in_scope']['triangle_pairs']))),
            'sample_count_delta':p['after']['in_scope']['penetrating_samples']-p['before']['in_scope']['penetrating_samples'],
            'max_depth_delta':p['after']['in_scope']['max_oriented_depth']-p['before']['in_scope']['max_oriented_depth']} for p in per_pose],
        'body_admission_ok':True,
        'source_reference_ok':True,'source_lbs_max_error':source_lbs_error,
        'local_limits_ok':local_ok,'motion_scope_vertices':int(motion_scope.sum()),
        'scope':'selected body-influenced vertices and boundary faces; immutable exterior diagnostic only' if metadata.get('local_refinement') else 'body-influenced vertices; pure dynamic geometry diagnostic only',
        'exterior_geometry_unchanged':exterior_geometry_unchanged,
        'excluded_pure_dynamic_vertices':int(excluded.sum()),'dynamic_geometry_unchanged':dynamic_unchanged,
        'legacy_conflicts_outside_scope':bool(legacy_excluded),
        'holdout_body_rms_before':float(np.sqrt(np.mean(old*old))),
        'holdout_body_rms_after':float(np.sqrt(np.mean(new*new))),
        'max_region_error':budget_error,'tolerance_world_units':tolerance,'poses':per_pose,
        'limitations':['oriented side tests require trustworthy body normals','no continuous-time guarantee',
                       'self-collision and other layered garments require separate validation'],
        'complete_garment_acceptance':False}
