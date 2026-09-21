"""Flat shoe conditional BODY fields. NumPy only; no spatial weight transfer here.

Optimizes proportions, never BODY/DYNAMIC budgets. Graph edges must already be
restricted to the same anatomical side and nonzero BODY scope by the adapter.
"""
import numpy as np


def simplex(x, allowed=None):
    """Euclidean projection of each row onto the probability simplex."""
    if allowed is not None:
        if np.any(~np.any(allowed,axis=1)):raise ValueError('Empty candidate set')
        x=np.where(allowed,x,-1e20)
    u = np.sort(x, axis=1)[:, ::-1]
    css = np.cumsum(u, axis=1) - 1
    j = np.arange(1, x.shape[1] + 1)
    rho = (u - css / j > 0).sum(axis=1) - 1
    theta = css[np.arange(len(x)), rho] / (rho + 1)
    return np.maximum(x - theta[:, None], 0)


def smooth(initial, edges, confidence, strength=1., iterations=300, tolerance=1e-7, allowed=None):
    """Convex graph/data energy, positive conductances, no cross-layer KNN.

Convex-combination Jacobi updates preserve simplex constraints exactly. Isolated
components still have positive data anchors; no global constant-field nullspace.
"""
    p = np.asarray(initial, float).copy()
    if not np.isfinite(p).all() or np.any(p < 0) or not np.allclose(p.sum(1), 1):
        raise ValueError('Invalid conditional BODY distribution')
    c = np.asarray(confidence, float)
    if np.any(c <= 0) or not np.isfinite(c).all():
        raise ValueError('Every disconnected component requires reliable data anchors')
    edges = np.asarray(edges, int).reshape(-1, 2)
    a, b = edges.T
    degree = np.bincount(edges.ravel(), minlength=len(p))
    for step in range(iterations):
        accum = np.zeros_like(p)
        np.add.at(accum, a, p[b]); np.add.at(accum, b, p[a])
        new = (c[:, None]*initial + strength*accum)/(c+strength*degree)[:, None]
        if allowed is not None:new=simplex(new,allowed)
        delta = float(np.max(abs(new-p))); p = new
        if delta < tolerance: break
    return p, {'iterations':step+1, 'max_delta':delta, 'converged':delta<tolerance}


def optimize(initial, H, rhs, edges, prior=0.05, smoothness=0.02,
             iterations=600, tolerance=2e-7, allowed=None):
    """Projected gradient on a convex fixed-reference gap/offset quadratic.

H/rhs include pose terms. Bound step size uses a safe symmetric row-sum bound.
This is not a nonlinear closest-surface or collision certificate.
"""
    edges = np.asarray(edges, int).reshape(-1, 2); a,b = edges.T
    degree = np.bincount(edges.ravel(), minlength=len(initial))
    H = np.asarray(H,float).copy(); rhs = np.asarray(rhs,float).copy()
    H += prior*np.eye(initial.shape[1])[None,:,:]; rhs += prior*initial
    bound = float(np.max(np.sum(abs(H),axis=2).max(axis=1)+2*smoothness*degree))
    if not np.isfinite(bound) or bound<=0:raise ValueError('Invalid quadratic')
    p = initial.copy()
    for step in range(iterations):
        lap = degree[:,None]*p
        np.add.at(lap,a,-p[b]);np.add.at(lap,b,-p[a])
        grad = np.einsum('vij,vj->vi',H,p)-rhs+smoothness*lap
        new = simplex(p-grad/bound,allowed)
        delta = float(np.max(abs(new-p)));p=new
        if delta<tolerance:break
    return p, {'iterations':step+1,'max_delta':delta,'converged':delta<tolerance,
               'simplex_error':float(np.max(abs(p.sum(1)-1)))}
