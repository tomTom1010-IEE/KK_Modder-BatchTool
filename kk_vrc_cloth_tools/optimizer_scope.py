"""Shared scope policy; NumPy only so it is also usable inside Blender."""
import numpy as np


def check_body_admission(metadata):
    if set(metadata['target_names'])&set(metadata.get('excluded_body_groups',())):
        raise ValueError('Excluded body candidates')
    if 'allowed_body_bones' not in metadata or 'retained_dynamic_bones' not in metadata:
        raise ValueError('Missing actual target-body support contract; re-export context')
    bad=set(metadata['target_names'])-set(metadata['allowed_body_bones'])-set(metadata['retained_dynamic_bones'])
    if bad:raise ValueError('Unsupported body candidates: '+str(sorted(bad)))


def check_source_deformation(arrays, tolerance=1e-5):
    """Compare the full source reference LBS with evaluated Blender evidence."""
    needed={'actual_source','source_rest','source_weights','source_matrices'}
    if not needed.issubset(arrays):
        raise ValueError('Missing Blender source-deformation evidence; re-export context')
    positions=[]
    for mat in arrays['source_matrices']:
        basis=np.einsum('bij,vj->vbi',mat[:,:3,:3],arrays['source_rest'])+mat[None,:,:3,3]
        positions.append(np.einsum('vb,vbc->vc',arrays['source_weights'],basis))
    positions=np.asarray(positions)
    actual=arrays['actual_source']
    if positions.shape!=actual.shape or not np.isfinite(positions).all() or not np.isfinite(actual).all():
        raise ValueError('Invalid source deformation evidence')
    error=float(np.linalg.norm(positions-actual,axis=2).max())
    if error>tolerance:raise ValueError(f'Source reference differs from Blender deformation: {error}')
    return error


def pure_dynamic_vertices(budgets):
    budgets = np.asarray(budgets, float)
    if budgets.ndim != 2 or budgets.shape[1] != 6 or not np.isfinite(budgets).all():
        raise ValueError('Expected finite six-region budgets')
    # Do not exclude mixed attachment vertices or simply frozen body vertices.
    return (np.abs(budgets[:, :5]).sum(axis=1) <= 1e-8) & (budgets[:, 5] > 0)
