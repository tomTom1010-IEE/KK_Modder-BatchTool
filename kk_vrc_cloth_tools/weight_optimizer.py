"""Offline sparse QP optimizer. Optional numpy/scipy/osqp dependencies, no bpy.

Inputs are world-space rest vertices and fixed pose matrices. This module never
changes scene data and does not silently accept unsupported physical/rig models.
"""
import numpy as np
from scipy import sparse
from scipy.spatial import cKDTree
import osqp


def transform(m, x):
    return np.einsum('...ij,...j->...i', m[..., :3, :3], x) + m[..., :3, 3]


def skin(rest, matrices, weights):
    return np.einsum('vb,pvbc->pvc', weights,
                     np.einsum('pbij,vj->pvbi', matrices[..., :3, :3], rest)
                     + matrices[:, None, :, :3, 3])


def surface_geometry(rest, triangles):
    t = rest[triangles]
    crosses = np.cross(t[:, 1]-t[:, 0], t[:, 2]-t[:, 0])
    normals = np.zeros_like(rest)
    area = np.zeros(len(rest))
    for j in range(3):
        np.add.at(normals, triangles[:, j], crosses)
        np.add.at(area, triangles[:, j], np.linalg.norm(crosses, axis=1)/6)
    normals /= np.maximum(np.linalg.norm(normals, axis=1, keepdims=True), 1e-15)
    return normals, area


def fit_rest_transport(source, target, edges, triangles, prior=None):
    """Fit local sculpt/scale Jacobians using *paired garment* rest coordinates.

    The surface has rank two; normal correspondences regularize thickness.
    Invalid/reflecting/extreme local maps fall back to explicit skeleton prior.
    """
    source, target = np.asarray(source, float), np.asarray(target, float)
    if source.shape != target.shape or source.ndim != 2 or source.shape[1] != 3:
        raise ValueError('Paired rest vertices must have identical N x 3 shape')
    n = len(source)
    prior = np.broadcast_to(np.eye(3), (n, 3, 3)).copy() if prior is None else np.asarray(prior, float)
    ns, _ = surface_geometry(source, triangles)
    nt, _ = surface_geometry(target, triangles)
    adj = [set() for _ in range(n)]
    for a, b in edges:
        adj[a].add(b); adj[b].add(a)
    out, fallback = prior.copy(), []
    for i, neighbors in enumerate(adj):
        js = sorted(neighbors)
        if len(js) < 2:
            fallback.append(i); continue
        x, y = source[js]-source[i], target[js]-target[i]
        length = np.median(np.linalg.norm(x, axis=1))
        if length < 1e-12 or np.linalg.norm(ns[i]) < .5 or np.linalg.norm(nt[i]) < .5:
            fallback.append(i); continue
        x /= length; y /= length
        scale = np.median(np.linalg.norm(y, axis=1)/np.maximum(np.linalg.norm(x, axis=1), 1e-12))
        x = np.vstack([x, ns[i]])
        y = np.vstack([y, nt[i]*scale])
        ridge = .05
        j = np.linalg.solve(x.T@x+ridge*np.eye(3), x.T@y+ridge*prior[i].T).T
        sv = np.linalg.svd(j, compute_uv=False)
        if np.linalg.det(j) <= 0 or sv.min() < .2 or sv.max() > 5:
            fallback.append(i)
        else:
            out[i] = j
    return out, fallback


def motion_reference(source_rest, target_rest, source_posed, source_frames,
                     target_frames, jacobians):
    """Frame 0 is rest; all frames are fixed, rigid world-space transforms.

    Preserves exact sculpted target rest positions; transports only source local
    motion residuals. Skeleton rotations/lengths are not confused with mesh scale.
    """
    hs, ht = np.asarray(source_frames), np.asarray(target_frames)
    for h in (hs, ht):
        r = h[..., :3, :3]
        if not np.allclose(np.swapaxes(r, -1, -2)@r, np.eye(3), atol=1e-5):
            raise ValueError('Reference frames must be rigid; put scale in transport')
    qs = transform(np.linalg.inv(hs), source_posed)
    qt0 = transform(np.linalg.inv(ht[0]), target_rest)
    local_j = np.swapaxes(ht[0, :, :3, :3], -1, -2) @ jacobians @ hs[0, :, :3, :3]
    dq = np.einsum('vij,pvj->pvi', local_j, qs-qs[0])
    ref = transform(ht, qt0[None]+dq)
    if not np.allclose(ref[0], target_rest, atol=1e-7):
        raise ValueError('Rest reference mismatch')
    return ref


class TriangleSurface:
    """Exact nearest triangle search with conservative centroid radius bounds.

    Signed side is based on closest face normal, NOT a watertight inside test.
    Results are contact proxies; independent face-level validation is mandatory.
    """
    def __init__(self, vertices, triangles):
        self.t = np.asarray(vertices)[np.asarray(triangles)]
        cross = np.cross(self.t[:,1]-self.t[:,0], self.t[:,2]-self.t[:,0])
        valid = np.linalg.norm(cross, axis=1) > 1e-14
        self.t, cross = self.t[valid], cross[valid]
        if not len(self.t):
            raise ValueError('Empty collision surface')
        self.normals = cross/np.linalg.norm(cross, axis=1)[:,None]
        self.centers = self.t.mean(axis=1)
        self.radii = np.linalg.norm(self.t-self.centers[:,None], axis=2).max(axis=1)
        self.radius = self.radii.max()
        self.tree = cKDTree(self.centers)
        # Radius buckets avoid making every query pay for one unusually large face.
        bins=np.floor(np.log2(np.maximum(self.radii,1e-12))).astype(int)
        self.buckets=[]
        for label in np.unique(bins):
            ids=np.where(bins==label)[0]
            self.buckets.append((ids,cKDTree(self.centers[ids]),self.radii[ids].max()))

    def nearest(self, points):
        points = np.asarray(points)
        if len(points)>512:
            chunks=[self.nearest(points[i:i+512]) for i in range(0,len(points),512)]
            return tuple(np.concatenate([c[k] for c in chunks]) for k in range(3))
        d, nearest_id = self.tree.query(points)
        upper=d+self.radii[nearest_id]
        choices=[[] for _ in points]
        for ids,tree,radius in self.buckets:
            hits=tree.query_ball_point(points,upper+radius+1e-10)
            for i,hit in enumerate(hits):choices[i].extend(ids[hit])
        owner = np.repeat(np.arange(len(points)), [len(c) for c in choices])
        ids = np.concatenate(choices).astype(int)
        p, tri = points[owner], self.t[ids]
        a, b, c = tri[:,0], tri[:,1], tri[:,2]
        ab, ac, ap = b-a, c-a, p-a
        dot = lambda x,y: np.einsum('ij,ij->i',x,y)
        aa, bb, cc = dot(ab,ab), dot(ab,ac), dot(ac,ac)
        den = aa*cc-bb*bb
        v = (cc*dot(ap,ab)-bb*dot(ap,ac))/den
        w = (aa*dot(ap,ac)-bb*dot(ap,ab))/den
        projection = a+v[:,None]*ab+w[:,None]*ac
        best = projection.copy()
        distance = np.where((v>=0)&(w>=0)&(v+w<=1), dot(p-best,p-best), np.inf)
        for u,z in ((a,b),(b,c),(c,a)):
            edge = z-u
            f = np.clip(dot(p-u,edge)/np.maximum(dot(edge,edge),1e-30),0,1)
            q = u+f[:,None]*edge
            dd = dot(p-q,p-q)
            take = dd<distance
            best[take], distance[take] = q[take], dd[take]
        order = np.lexsort((distance,owner))
        first = order[np.r_[True, np.diff(owner[order])!=0]]
        q, normal = best[first], self.normals[ids[first]]
        signed = dot(points-q,normal)
        return q, normal, signed


def solve(rest, matrices, initial, reference, regions, budgets, fixed_mask,
          candidates, edges, pose_weights, selected=None, surfaces=None,
          prior=.02, smooth=.01, clearance=0., contact_tolerance=1e-4,
          trust=.15, max_contact_steps=4, time_limit=120., vertex_weights=None,
          contact_samples=None, progress=None, contact_excluded=None, delta_limits=None, residual_scale=None):
    """Sparse regional QP + sequential linearized contact constraints.

    regions: bone -> integer region; budgets: vertex x region.
    Fixed dynamic/finger weights are eliminated, never optimized or renormalized.
    Acceptance is deliberately separate from solving and Blender writeback.
    """
    rest=np.asarray(rest,float); matrices=np.asarray(matrices,float)
    w0=np.asarray(initial,float); reference=np.asarray(reference,float)
    regions=np.asarray(regions,int); budgets=np.asarray(budgets,float)
    fixed=np.asarray(fixed_mask,bool); allowed=np.asarray(candidates,bool)
    n,b=w0.shape; p=len(matrices)
    excluded=np.zeros(n,bool) if contact_excluded is None else np.asarray(contact_excluded,bool)
    if excluded.shape!=(n,):raise ValueError('Invalid contact exclusion mask')
    if fixed.shape!=(n,b) or allowed.shape!=(n,b) or reference.shape!=(p,n,3):
        raise ValueError('Array shape mismatch')
    if not all(np.isfinite(a).all() for a in [rest,matrices,w0,reference,budgets]):
        raise ValueError('Nonfinite input')
    if np.any(w0<0) or np.max(abs(w0.sum(axis=1)-1))>1e-6:
        raise ValueError('Initial weights must be effective normalized weights')
    for r in range(budgets.shape[1]):
        if np.max(abs(w0[:,regions==r].sum(axis=1)-budgets[:,r]))>1e-6:
            raise ValueError('Initial regional budget mismatch')
    active=np.ones(n,bool) if selected is None else np.isin(np.arange(n),selected)
    free=allowed & ~fixed & active[:,None] & (budgets[:,regions]>0)
    if np.any((w0>0)&~(free|fixed)&active[:,None]):
        raise ValueError('Positive initial influence excluded without preservation policy')
    vi,bi=np.where(free); count=len(vi)
    limits=np.ones(n) if delta_limits is None else np.asarray(delta_limits,float)
    if limits.shape!=(n,) or not np.isfinite(limits).all() or np.any(limits<0) or np.any(limits>1):raise ValueError('Invalid correction limits')
    if not count:
        return w0.copy(), {'status':'no_free_variables','accepted':False}
    index=np.full((n,b),-1,int);index[vi,bi]=np.arange(count)
    frozen=w0.copy();frozen[free]=0
    basis=np.einsum('pbij,vj->pvbi',matrices[...,:3,:3],rest)+matrices[:,None,:,:3,3]
    constant=np.einsum('vb,pvbc->pvc',frozen,basis)
    # Every residual row corresponds to one pose/vertex/coordinate.
    rr=[]; cols=[]; vals=[]
    pw=np.asarray(pose_weights,float)
    if pw.shape!=(p,) or np.any(pw<0) or pw.sum()<=0:raise ValueError('Invalid pose weights')
    pw=pw/pw.sum()
    vw=np.ones(n) if vertex_weights is None else np.asarray(vertex_weights,float)
    if vw.shape!=(n,) or not np.isfinite(vw).all() or np.any(vw<0) or vw.sum()<=0:
        raise ValueError('Invalid vertex area weights')
    vw=vw/vw.mean()
    span=np.linalg.norm(np.ptp(rest,axis=0))
    scale=span if span>1e-6 else 1.
    if residual_scale is not None:
        scale=float(residual_scale)
        if not np.isfinite(scale) or scale<=0:raise ValueError('Invalid residual scale')
    for pose in range(p):
        for axis in range(3):
            rr.append((pose*n+vi)*3+axis);cols.append(np.arange(count))
            vals.append(basis[pose,vi,bi,axis]*np.sqrt(pw[pose]*vw[vi])/scale)
    design=sparse.coo_matrix((np.concatenate(vals),(np.concatenate(rr),np.concatenate(cols))),shape=(p*n*3,count)).tocsc()
    rhs=((reference-constant)*np.sqrt(pw[:,None]*vw[None,:])[:,:,None]/scale).ravel()
    x0=w0[vi,bi]
    # Smooth *corrections*, with fixed exterior correction zero.
    er=[];ec=[];ev=[];nr=0
    for u,v in edges:
        for bone in np.union1d(np.where(free[u])[0],np.where(free[v])[0]):
            for vert,sign in ((u,1),(v,-1)):
                j=index[vert,bone]
                if j>=0:er.append(nr);ec.append(j);ev.append(sign)
            nr+=1
    lap=sparse.coo_matrix((ev,(er,ec)),shape=(nr,count)).tocsc()
    h=design.T@design+prior*sparse.eye(count,format='csc')+smooth*(lap.T@lap)
    q=-2*(design.T@rhs+prior*x0+smooth*(lap.T@(lap@x0)))
    ar=[];ac=[];av=[];budget_rhs=[]
    for v in np.where(active)[0]:
        for region in range(budgets.shape[1]):
            js=index[v,(regions==region)&free[v]]
            target=budgets[v,region]-frozen[v,regions==region].sum()
            if len(js):
                ar.extend([len(budget_rhs)]*len(js));ac.extend(js);av.extend([1.]*len(js));budget_rhs.append(target)
            elif abs(target)>1e-6:raise ValueError('Positive budget with no candidates')
    eq=sparse.coo_matrix((av,(ar,ac)),shape=(len(budget_rhs),count)).tocsc()
    ident=sparse.eye(count,format='csc')
    x=x0.copy();history=[];surfaces=surfaces or {};contact_samples=contact_samples or {}
    fixed_conflicts=[]
    samples_by_pose={}
    for pose in surfaces:
        svi=np.repeat(np.arange(n)[:,None],3,axis=1);sc=np.tile([1.,0,0],(n,1))
        if pose in contact_samples:
            extra_vi,extra_c=contact_samples[pose]
            extra_vi=np.asarray(extra_vi,int);extra_c=np.asarray(extra_c,float)
            if extra_vi.shape!=extra_c.shape or extra_vi.shape[1]!=3 or np.any(extra_vi<0) or np.any(extra_vi>=n) or np.any(extra_c<0) or not np.allclose(extra_c.sum(axis=1),1):
                raise ValueError('Invalid barycentric contact samples')
            svi=np.vstack([svi,extra_vi]);sc=np.vstack([sc,extra_c])
        in_scope=np.any((sc>0)&~excluded[svi],axis=1)
        svi,sc=svi[in_scope],sc[in_scope]
        samples_by_pose[pose]=(svi,sc)
    for iteration in range(max_contact_steps if surfaces else 1):
        if progress:progress({'phase':'contact_search','iteration':iteration})
        current=frozen.copy();current[vi,bi]=x
        positions=np.einsum('vb,pvbc->pvc',current,basis)
        cr=[];cc=[];cv=[];cl=[];unadjustable=0
        for pose,surface in surfaces.items():
            svi,sc=samples_by_pose[pose]
            if not len(svi):continue
            pts=np.sum(positions[pose,svi]*sc[:,:,None],axis=1)
            near,normal,d=surface.nearest(pts)
            for sample in np.where(d<clearance+contact_tolerance)[0]:
                row_indices=[];row_values=[]
                for v,factor in zip(svi[sample],sc[sample]):
                    if not factor:continue
                    bones=np.where(free[v])[0]
                    row_indices.extend(index[v,bones]);row_values.extend(factor*(basis[pose,v,bones]@normal[sample]))
                if not row_indices:
                    if d[sample]<clearance-contact_tolerance:
                        unadjustable+=1
                        if iteration==0:fixed_conflicts.append({'pose':int(pose),'vertices':svi[sample].tolist(),'barycentric':sc[sample].tolist(),'oriented_distance':float(d[sample])})
                    continue
                const=np.sum(constant[pose,svi[sample]]*sc[sample,:,None],axis=0)
                cr.extend([len(cl)]*len(row_indices));cc.extend(row_indices);cv.extend(row_values)
                cl.append(clearance+near[sample]@normal[sample]-const@normal[sample])
        contact=sparse.coo_matrix((cv,(cr,cc)),shape=(len(cl),count)).tocsc()
        a=sparse.vstack([eq,ident,contact],format='csc')
        lower=np.maximum(0,x0-limits[vi]);upper=np.minimum(1,x0+limits[vi])
        if surfaces:lower=np.maximum(lower,x-trust);upper=np.minimum(upper,x+trust)
        lo=np.r_[budget_rhs,lower,cl]
        hi=np.r_[budget_rhs,upper,np.full(len(cl),np.inf)]
        solver=osqp.OSQP();solver.setup(P=sparse.triu(2*h,format='csc'),q=q,A=a,l=lo,u=hi,
            eps_abs=1e-8,eps_rel=1e-8,max_iter=20000,polishing=True,verbose=False,time_limit=time_limit)
        solver.warm_start(x=x)
        if progress:progress({'phase':'qp_solve','iteration':iteration,'variables':count,'contacts':len(cl)})
        solution=solver.solve(raise_error=False)
        history.append({'iteration':iteration,'status':solution.info.status,'iterations':solution.info.iter,
                        'contact_constraints':len(cl),'unadjustable_contact_vertices':unadjustable})
        if solution.info.status_val!=1:
            return current,{'status':'subproblem_failed','accepted':False,'history':history}
        # Tiny numerical residuals are repaired only within the same free category.
        x=np.maximum(solution.x,0)
        for v in np.where(active)[0]:
            for region in range(budgets.shape[1]):
                js=index[v,(regions==region)&free[v]]
                if len(js):
                    mass=budgets[v,region]-frozen[v,regions==region].sum()
                    if x[js].sum()>0:x[js]*=mass/x[js].sum()
        if not surfaces:break
        # These samples have no optimizable weight at any supporting vertex.
        # More iterations cannot move them; preserve constraints and report it.
        if fixed_conflicts:break
        candidate=frozen.copy();candidate[vi,bi]=x
        pos=skin(rest,matrices,candidate)
        if all(not len(samples_by_pose[k][0]) or np.min(sf.nearest(np.sum(pos[k,samples_by_pose[k][0]]*samples_by_pose[k][1][:,:,None],axis=1))[2])>=clearance-contact_tolerance for k,sf in surfaces.items()):break
    out=frozen.copy();out[vi,bi]=x
    if np.max(abs(out[fixed]-w0[fixed]),initial=0)>1e-12:raise RuntimeError('Fixed weights changed')
    for r in range(budgets.shape[1]):
        if np.max(abs(out[:,regions==r].sum(axis=1)-budgets[:,r]))>1e-6:raise RuntimeError('Budget drift')
    posed=skin(rest,matrices,out);baseline=skin(rest,matrices,w0)
    metric=lambda a:float(np.sqrt(np.sum(pw[:,None]*vw[None,:]*np.sum((a-reference)**2,axis=2))/n))
    contacts={str(k):{'min_oriented_distance':float(sf.nearest(posed[k,~excluded])[2].min()) if np.any(~excluded) else None} for k,sf in surfaces.items()}
    return out,{'status':'fixed_contact_conflict' if fixed_conflicts else 'solved','accepted':False,'requires_independent_validation':True,
                'fixed_contact_conflicts':fixed_conflicts,
                'excluded_contact_vertices':int(excluded.sum()),
                'variables':count,'history':history,'baseline_rms':metric(baseline),'candidate_rms':metric(posed),
                'contact_proxy':contacts,'max_weight_change':float(np.max(abs(out-w0)))}
